from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    service: str = Field(..., examples=["studymate-rag-api"])


class RuntimeConfigResponse(BaseModel):
    knowledge_base_name: str
    chat_mode: Literal["generation", "retrieval_only"]
    llm_provider: Literal["deepseek", "gemini"]
    max_upload_size_mb: int
    default_top_k: int
    chat_request_timeout_seconds: float
    summary_request_timeout_seconds: float


class UploadResponse(BaseModel):
    document_id: str
    filename: Optional[str] = None
    status: str = "indexed"
    chunk_count: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: Optional[int] = Field(default=None, ge=1, le=10)
    document_id: Optional[str] = Field(default=None, pattern=r"^[0-9a-fA-F]{32}$")
    mode: Literal["auto", "question", "summary"] = "auto"

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("question 不能为空。")
        return cleaned


class Source(BaseModel):
    citation_id: Optional[str] = None
    document_id: Optional[str] = None
    filename: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None
    distance: Optional[float] = None
    cited: bool = False
    text: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    status: Literal["answered", "insufficient_evidence", "empty", "retrieval_only"] = "answered"
    metadata: dict[str, Any] = Field(default_factory=dict)


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
