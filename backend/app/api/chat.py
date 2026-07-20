from __future__ import annotations

import logging
from inspect import isawaitable, iscoroutinefunction
from typing import Any

from fastapi import APIRouter, status
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError, service_error
from app.models.schemas import ChatRequest, ChatResponse, Source

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


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
            "citation_id",
            "cited",
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
        distance = raw.get("distance")
        if distance is None:
            distance = raw.get("score")
        return Source(
            citation_id=raw.get("citation_id"),
            document_id=raw.get("document_id"),
            filename=raw.get("filename") or raw.get("source"),
            page=raw.get("page") or raw.get("page_number"),
            chunk_id=chunk_id,
            distance=distance,
            cited=bool(raw.get("cited", False)),
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


async def _call_service(function, *args):
    if iscoroutinefunction(function):
        return await function(*args)
    result = await run_in_threadpool(function, *args)
    if isawaitable(result):
        return await result
    return result


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        from app.services.rag_service import answer_question

        logger.info("chat_started", extra={"top_k": request.top_k})
        result = await _call_service(
            answer_question,
            request.question,
            request.top_k,
        )
        response = _chat_response_from_raw(result)
        logger.info("chat_finished", extra={"source_count": len(response.sources)})
        return response
    except ImportError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="rag_service_unavailable",
            message="RAG 服务暂不可用。",
        ) from exc
    except Exception as exc:
        raise service_error(exc) from exc
