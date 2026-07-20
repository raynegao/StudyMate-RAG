from __future__ import annotations

import logging
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.errors import UnsupportedFileTypeError
from app.services.chunking import split_pages_into_chunks
from app.services.embedding_service import embed_texts
from app.services.pdf_parser import extract_pdf_pages
from app.services.vector_store import add_chunks, delete_document, list_documents
from app.utils.file_utils import (
    sanitize_filename,
    save_upload_file,
    validate_document_id,
)

logger = logging.getLogger(__name__)


async def index_uploaded_pdf(upload_file) -> dict:
    filename = sanitize_filename(upload_file.filename or "document.pdf")
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError()

    document_id = uuid4().hex
    stored_filename = f"{document_id}_{filename}"
    pdf_path = settings.upload_dir / stored_filename
    await save_upload_file(
        upload_file,
        pdf_path,
        max_bytes=settings.max_upload_size_bytes,
    )

    try:
        page_count, chunk_count = await run_in_threadpool(
            _index_saved_pdf,
            pdf_path,
            document_id,
            filename,
        )
    except Exception:
        pdf_path.unlink(missing_ok=True)
        logger.exception("document_index_failed", extra={"document_id": document_id})
        raise

    return {
        "document_id": document_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "page_count": page_count,
        "chunk_count": chunk_count,
    }


def _index_saved_pdf(pdf_path, document_id: str, filename: str) -> tuple[int, int]:
    logger.info(
        "pdf_parse_started",
        extra={"document_id": document_id, "file_name": filename},
    )
    pages = extract_pdf_pages(pdf_path)
    logger.info(
        "pdf_parse_finished",
        extra={"document_id": document_id, "page_count": len(pages)},
    )
    chunks = split_pages_into_chunks(
        pages,
        document_id=document_id,
        filename=filename,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    logger.info(
        "chunking_finished",
        extra={"document_id": document_id, "chunk_count": len(chunks)},
    )
    embeddings = embed_texts([chunk.text for chunk in chunks])
    add_chunks(chunks, embeddings)
    logger.info(
        "document_indexed",
        extra={"document_id": document_id, "chunk_count": len(chunks)},
    )
    return len(pages), len(chunks)


def list_indexed_documents() -> list[dict]:
    logger.info("list_documents_started")
    return list_documents()


def delete_indexed_document(document_id: str) -> dict:
    safe_document_id = validate_document_id(document_id)
    deleted_from_index = delete_document(safe_document_id)
    deleted_files: list[str] = []

    prefix = f"{safe_document_id}_"
    if settings.upload_dir.exists():
        for pdf_path in settings.upload_dir.iterdir():
            if pdf_path.name.startswith(prefix) and pdf_path.is_file():
                pdf_path.unlink()
                deleted_files.append(pdf_path.name)

    return {
        "document_id": safe_document_id,
        "deleted": deleted_from_index or bool(deleted_files),
        "deleted_from_index": deleted_from_index,
        "deleted_files": deleted_files,
        "message": "文档已删除。" if deleted_from_index or deleted_files else "未找到该文档。",
    }
