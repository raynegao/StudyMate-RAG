from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
import re

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
    token_count: Callable[[str], int] | None = None,
    max_tokens: int | None = None,
    sentence_boundaries: bool = False,
) -> list[DocumentChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0。")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size。")
    if token_count is not None and (max_tokens is None or max_tokens <= 0):
        raise ValueError("token_count 需要正数 max_tokens")

    chunks: list[DocumentChunk] = []
    for page in pages:
        start = 0
        page_chunk_index = 0
        text = " ".join(page.text.split())

        while start < len(text):
            end = min(start + chunk_size, len(text))
            if token_count is not None:
                # Never silently lose the tail of a chunk inside the embedding model.
                while token_count(text[start:end]) > max_tokens:
                    end = start + (end - start) // 2
                    if end == start:
                        raise ValueError("单个字符已超过 token 预算")
            if sentence_boundaries and end < len(text):
                boundaries = list(re.finditer(r"[。！？；]|[.!?;](?=\s)", text[start:end]))
                if boundaries and boundaries[-1].end() >= 0.9 * (end - start):
                    end = start + boundaries[-1].end()
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
            start = max(start + 1, end - chunk_overlap)
            page_chunk_index += 1

    return chunks
