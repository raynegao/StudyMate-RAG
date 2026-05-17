from inspect import isawaitable
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.schemas import (
    DeleteDocumentResponse,
    DocumentSummary,
    DocumentsResponse,
    UploadResponse,
)

router = APIRouter(prefix="/api", tags=["documents"])


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
    is_pdf = file.content_type == "application/pdf" or filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported.",
        )

    try:
        from app.services.document_service import index_uploaded_pdf

        result = index_uploaded_pdf(file)
        if isawaitable(result):
            result = await result
        return _upload_response_from_raw(result, file.filename)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is not available yet.",
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


@router.get("/documents", response_model=DocumentsResponse)
async def list_documents() -> DocumentsResponse:
    try:
        from app.services.document_service import list_indexed_documents

        documents = list_indexed_documents()
        if isawaitable(documents):
            documents = await documents
        if isinstance(documents, dict):
            documents = documents.get("documents", [])
        documents = documents or []
        return DocumentsResponse(
            documents=[_document_from_raw(document) for document in documents]
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is not available yet.",
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


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(document_id: str) -> DeleteDocumentResponse:
    try:
        from app.services.document_service import delete_indexed_document

        result = delete_indexed_document(document_id)
        if isawaitable(result):
            result = await result
        if isinstance(result, DeleteDocumentResponse):
            return result
        if isinstance(result, dict):
            return DeleteDocumentResponse(
                document_id=str(result.get("document_id") or document_id),
                status=result.get("status") or "deleted",
                message=result.get("message"),
            )
        return DeleteDocumentResponse(document_id=document_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document service is not available yet.",
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
