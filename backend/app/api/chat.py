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


SOURCE_FIELDS = {"citation_id", "document_id", "filename", "page_number", "chunk_id", "distance", "cited", "text"}


def _source_from_raw(raw: dict[str, Any]) -> Source:
    return Source(
        citation_id=raw.get("citation_id"),
        document_id=raw.get("document_id"),
        filename=raw.get("filename"),
        page=raw.get("page_number"),
        chunk_id=raw.get("chunk_id"),
        distance=raw.get("distance"),
        cited=bool(raw.get("cited", False)),
        text=raw.get("text"),
        metadata={key: value for key, value in raw.items() if key not in SOURCE_FIELDS},
    )


def _chat_response_from_raw(raw: dict[str, Any]) -> ChatResponse:
    if not raw.get("answer"):
        raise ValueError("RAG service response is missing answer")
    return ChatResponse(
        answer=raw["answer"],
        sources=[_source_from_raw(source) for source in raw.get("sources") or []],
        status=raw.get("status", "answered"),
        metadata=raw.get("metadata", {}),
    )


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
        args = (request.question, request.top_k)
        # Preserve the existing unscoped contract and service adapters.
        if request.document_id is not None or request.mode != "auto":
            args += (request.document_id, request.mode)
        result = await _call_service(answer_question, *args)
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
