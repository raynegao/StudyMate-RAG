from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    service: str = Field(..., examples=["studymate-rag-api"])


class UploadResponse(BaseModel):
    document_id: str
    filename: Optional[str] = None
    status: str = "indexed"
    chunk_count: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=10)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question 不能为空。")
        return cleaned


class Source(BaseModel):
    document_id: Optional[str] = None
    filename: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    score: Optional[float] = None
    text: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    document_id: str
    filename: Optional[str] = None
    chunk_count: Optional[int] = None
    created_at: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary] = Field(default_factory=list)


class DeleteDocumentResponse(BaseModel):
    document_id: str
    status: str = "deleted"
    message: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody
