from __future__ import annotations

import logging
from inspect import isawaitable, iscoroutinefunction
from typing import Any

from fastapi import APIRouter, File, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError, service_error
from app.models.schemas import (
    DeleteDocumentResponse,
    DocumentSummary,
    DocumentsResponse,
    UploadResponse,
)
from app.utils.file_utils import validate_document_id

router = APIRouter(prefix="/api", tags=["documents"])
logger = logging.getLogger(__name__)


async def _call_service(function, *args):
    if iscoroutinefunction(function):
        return await function(*args)
    result = await run_in_threadpool(function, *args)
    if isawaitable(result):
        return await result
    return result


def _document_from_raw(raw: Any) -> DocumentSummary:
    if isinstance(raw, DocumentSummary):
        return raw
    if isinstance(raw, dict):
        document_id = raw.get("document_id") or raw.get("id")
        if not document_id:
            raise ValueError("Document item is missing document_id")
        known_keys = {"document_id", "id", "filename", "chunk_count", "created_at"}
        metadata = raw.get("metadata") or {
            key: value for key, value in raw.items() if key not in known_keys
        }
        return DocumentSummary(
            document_id=str(document_id),
            filename=raw.get("filename") or raw.get("name"),
            chunk_count=raw.get("chunk_count"),
            created_at=raw.get("created_at"),
            metadata=metadata,
        )
    return DocumentSummary(document_id=str(raw))


def _upload_response_from_raw(raw: Any, filename: str | None) -> UploadResponse:
    if isinstance(raw, UploadResponse):
        return raw
    if isinstance(raw, dict):
        document_id = raw.get("document_id") or raw.get("id")
        if not document_id:
            raise ValueError("Upload result is missing document_id")
        known_keys = {"document_id", "id", "filename", "status", "chunk_count"}
        metadata = raw.get("metadata") or {
            key: value for key, value in raw.items() if key not in known_keys
        }
        return UploadResponse(
            document_id=str(document_id),
            filename=raw.get("filename") or filename,
            status=raw.get("status") or "indexed",
            chunk_count=raw.get("chunk_count"),
            metadata=metadata,
        )
    return UploadResponse(document_id=str(raw), filename=filename)


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    filename = file.filename or ""
    is_pdf = filename.lower().endswith(".pdf")
    if not is_pdf:
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="unsupported_file_type",
            message="目前只支持上传 PDF 文件。",
            details={"filename": filename, "content_type": file.content_type},
        )

    try:
        from app.services.document_service import index_uploaded_pdf

        logger.info("upload_started", extra={"file_name": filename})
        result = await _call_service(index_uploaded_pdf, file)
        response = _upload_response_from_raw(result, file.filename)
        logger.info(
            "upload_indexed",
            extra={
                "document_id": response.document_id,
                "file_name": response.filename,
                "chunk_count": response.chunk_count,
            },
        )
        return response
    except ImportError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="document_service_unavailable",
            message="文档服务暂不可用。",
        ) from exc
    except Exception as exc:
        raise service_error(exc) from exc


@router.get("/documents", response_model=DocumentsResponse)
async def list_documents() -> DocumentsResponse:
    try:
        from app.services.document_service import list_indexed_documents

        documents = await _call_service(list_indexed_documents)
        if isinstance(documents, dict):
            documents = documents.get("documents", [])
        documents = documents or []
        return DocumentsResponse(
            documents=[_document_from_raw(document) for document in documents]
        )
    except ImportError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="document_service_unavailable",
            message="文档服务暂不可用。",
        ) from exc
    except Exception as exc:
        raise service_error(exc) from exc


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(document_id: str) -> DeleteDocumentResponse:
    try:
        from app.services.document_service import delete_indexed_document

        safe_document_id = validate_document_id(document_id)
        logger.info(
            "delete_document_started",
            extra={"document_id": safe_document_id},
        )
        result = await _call_service(delete_indexed_document, safe_document_id)
        if isinstance(result, DeleteDocumentResponse):
            return result
        if isinstance(result, dict):
            deleted = bool(result.get("deleted"))
            logger.info(
                "delete_document_finished",
                extra={"document_id": document_id, "deleted": deleted},
            )
            return DeleteDocumentResponse(
                document_id=str(result.get("document_id") or safe_document_id),
                status=result.get("status") or ("deleted" if deleted else "not_found"),
                message=result.get("message"),
            )
        return DeleteDocumentResponse(document_id=safe_document_id)
    except ImportError as exc:
        raise AppError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="document_service_unavailable",
            message="文档服务暂不可用。",
        ) from exc
    except Exception as exc:
        raise service_error(exc) from exc
