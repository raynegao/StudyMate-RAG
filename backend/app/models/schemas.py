from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    service: str = Field(..., examples=["studymate-rag-api"])


class UploadResponse(BaseModel):
    document_id: str
    filename: str | None = None
    status: str = "indexed"
    chunk_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=10)


class Source(BaseModel):
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    score: float | None = None
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    document_id: str
    filename: str | None = None
    chunk_count: int | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary] = Field(default_factory=list)


class DeleteDocumentResponse(BaseModel):
    document_id: str
    status: str = "deleted"
    message: str | None = None
