from __future__ import annotations

from dataclasses import dataclass

from app.services.pdf_parser import PageText


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str


def split_pages_into_chunks(
    pages: list[PageText],
    *,
    document_id: str,
    filename: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0。")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size。")

    chunks: list[DocumentChunk] = []
    for page in pages:
        start = 0
        page_chunk_index = 0
        text = " ".join(page.text.split())

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = f"{document_id}:p{page.page_number}:c{page_chunk_index}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        filename=filename,
                        page_number=page.page_number,
                        chunk_index=page_chunk_index,
                        text=chunk_text,
                    )
                )

            if end == len(text):
                break
            start = end - chunk_overlap
            page_chunk_index += 1

    return chunks
