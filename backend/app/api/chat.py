from inspect import isawaitable
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ChatRequest, ChatResponse, Source

router = APIRouter(prefix="/api", tags=["chat"])


def _source_from_raw(raw: Any) -> Source:
    if isinstance(raw, Source):
        return raw
    if isinstance(raw, dict):
        known_keys = {
            "document_id",
            "filename",
            "source",
            "page",
            "page_number",
            "chunk_id",
            "chunk_index",
            "score",
            "distance",
            "text",
            "content",
        }
        metadata = raw.get("metadata") or {
            key: value for key, value in raw.items() if key not in known_keys
        }
        chunk_id = raw.get("chunk_id")
        if chunk_id is None and raw.get("chunk_index") is not None:
            chunk_id = str(raw["chunk_index"])
        return Source(
            document_id=raw.get("document_id"),
            filename=raw.get("filename") or raw.get("source"),
            page=raw.get("page") or raw.get("page_number"),
            chunk_id=chunk_id,
            score=raw.get("score") or raw.get("distance"),
            text=raw.get("text") or raw.get("content"),
            metadata=metadata,
        )
    return Source(text=str(raw))


def _chat_response_from_raw(raw: Any) -> ChatResponse:
    if isinstance(raw, ChatResponse):
        return raw
    if isinstance(raw, dict):
        answer = raw.get("answer") or raw.get("response") or raw.get("content")
        sources = raw.get("sources") or raw.get("citations") or []
        if not answer:
            raise ValueError("RAG service response is missing answer")
        return ChatResponse(
            answer=str(answer),
            sources=[_source_from_raw(source) for source in sources],
        )
    if isinstance(raw, tuple) and len(raw) == 2:
        answer, sources = raw
        return ChatResponse(
            answer=str(answer),
            sources=[_source_from_raw(source) for source in sources],
        )
    return ChatResponse(answer=str(raw), sources=[])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        from app.services.rag_service import answer_question

        result = answer_question(request.question, request.top_k)
        if isawaitable(result):
            result = await result
        return _chat_response_from_raw(result)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service is not available yet.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
