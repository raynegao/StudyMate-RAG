from __future__ import annotations

from uuid import uuid4

from app.core.config import settings
from app.services.chunking import split_pages_into_chunks
from app.services.embedding_service import embed_texts
from app.services.pdf_parser import extract_pdf_pages
from app.services.vector_store import add_chunks, delete_document, list_documents
from app.utils.file_utils import sanitize_filename, save_upload_file


async def index_uploaded_pdf(upload_file) -> dict:
    filename = sanitize_filename(upload_file.filename or "document.pdf")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("目前只支持上传 PDF 文件。")

    document_id = uuid4().hex
    stored_filename = f"{document_id}_{filename}"
    pdf_path = settings.upload_dir / stored_filename
    await save_upload_file(upload_file, pdf_path)

    try:
        pages = extract_pdf_pages(pdf_path)
        chunks = split_pages_into_chunks(
            pages,
            document_id=document_id,
            filename=filename,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        embeddings = embed_texts([chunk.text for chunk in chunks])
        add_chunks(chunks, embeddings)
    except Exception:
        if pdf_path.exists():
            pdf_path.unlink()
        raise

    return {
        "document_id": document_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "page_count": len(pages),
        "chunk_count": len(chunks),
    }


def list_indexed_documents() -> list[dict]:
    return list_documents()


def delete_indexed_document(document_id: str) -> dict:
    deleted_from_index = delete_document(document_id)
    deleted_files: list[str] = []

    for pdf_path in settings.upload_dir.glob(f"{document_id}_*"):
        if pdf_path.is_file():
            pdf_path.unlink()
            deleted_files.append(pdf_path.name)

    return {
        "document_id": document_id,
        "deleted": deleted_from_index or bool(deleted_files),
        "deleted_from_index": deleted_from_index,
        "deleted_files": deleted_files,
    }
