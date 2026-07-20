from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.errors import VectorStoreError
from app.services.chunking import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    text: str
    distance: float | None = None

    @property
    def source(self) -> str:
        return f"{self.filename} p.{self.page_number}"


def _collection():
    try:
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        return client.get_or_create_collection(name=settings.chroma_collection)
    except Exception as exc:
        logger.exception("chroma_connection_failed")
        raise VectorStoreError() from exc


def add_chunks(chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
    if not chunks:
        raise ValueError("没有可索引的文本 chunk。")
    if len(chunks) != len(embeddings):
        raise ValueError("chunks 和 embeddings 数量不一致。")

    try:
        indexed_at = datetime.now(timezone.utc).isoformat()
        collection = _collection()
        logger.info("chroma_add_started", extra={"chunk_count": len(chunks)})
        collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "filename": chunk.filename,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "indexed_at": indexed_at,
                }
                for chunk in chunks
            ],
        )
        logger.info("chroma_add_finished", extra={"chunk_count": len(chunks)})
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("chroma_add_failed")
        raise VectorStoreError() from exc


def has_documents() -> bool:
    try:
        return _collection().count() > 0
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("chroma_count_failed")
        raise VectorStoreError() from exc


def query_chunks(query_embedding: list[float], top_k: int) -> list[RetrievedChunk]:
    if top_k <= 0:
        raise ValueError("top_k 必须大于 0。")

    try:
        collection = _collection()
        if collection.count() == 0:
            return []

        logger.info("chroma_query_started", extra={"top_k": top_k})
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        chunks = _parse_query_result(result)
        logger.info("chroma_query_finished", extra={"result_count": len(chunks)})
        return chunks
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("chroma_query_failed")
        raise VectorStoreError() from exc


def list_documents() -> list[dict[str, Any]]:
    try:
        collection = _collection()
        result = collection.get(include=["metadatas"])
        documents: dict[str, dict[str, Any]] = {}

        for metadata in result.get("metadatas") or []:
            document_id = str(metadata["document_id"])
            entry = documents.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "filename": metadata.get("filename"),
                    "pages": set(),
                    "chunk_count": 0,
                    "indexed_at": metadata.get("indexed_at"),
                },
            )
            entry["chunk_count"] += 1
            entry["pages"].add(int(metadata.get("page_number", 0)))
            indexed_at = metadata.get("indexed_at")
            if indexed_at and (
                entry["indexed_at"] is None or indexed_at < entry["indexed_at"]
            ):
                entry["indexed_at"] = indexed_at

        normalized = []
        for entry in documents.values():
            pages = sorted(page for page in entry.pop("pages") if page > 0)
            entry["page_count"] = len(pages)
            entry["pages"] = pages
            normalized.append(entry)

        return sorted(
            normalized,
            key=lambda item: item.get("indexed_at") or "",
            reverse=True,
        )
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("chroma_list_failed")
        raise VectorStoreError() from exc


def delete_document(document_id: str) -> bool:
    try:
        collection = _collection()
        existing = collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        ids = existing.get("ids") or []
        if not ids:
            return False

        collection.delete(where={"document_id": document_id})
        return True
    except VectorStoreError:
        raise
    except Exception as exc:
        logger.exception("chroma_delete_failed")
        raise VectorStoreError() from exc


def _parse_query_result(result: dict[str, Any]) -> list[RetrievedChunk]:
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    chunks: list[RetrievedChunk] = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=str(metadata["document_id"]),
                filename=str(metadata["filename"]),
                page_number=int(metadata["page_number"]),
                chunk_index=int(metadata["chunk_index"]),
                text=text,
                distance=float(distance) if distance is not None else None,
            )
        )
    return chunks
