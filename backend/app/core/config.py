from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("STUDYMATE_APP_NAME", "StudyMate RAG API")
    app_version: str = os.getenv("STUDYMATE_APP_VERSION", "0.3.0")
    log_level: str = os.getenv("STUDYMATE_LOG_LEVEL", "INFO").upper()
    frontend_api_base_url: str = os.getenv(
        "STUDYMATE_API_BASE_URL", "http://127.0.0.1:8000"
    )

    upload_dir: Path = Path(os.getenv("STUDYMATE_UPLOAD_DIR", "data/uploads"))
    chroma_dir: Path = Path(os.getenv("STUDYMATE_CHROMA_DIR", "data/chroma_db"))
    chroma_collection: str = os.getenv(
        "STUDYMATE_CHROMA_COLLECTION", "studymate_documents"
    )
    knowledge_base_name: str = os.getenv("STUDYMATE_KNOWLEDGE_BASE_NAME", "默认资料库")
    chat_mode: str = os.getenv("STUDYMATE_CHAT_MODE", "generation")

    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    embedding_model: str = os.getenv(
        "STUDYMATE_LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    llm_model: str = os.getenv("STUDYMATE_LLM_MODEL", "deepseek-v4-flash")
    llm_temperature: float = _float_env("STUDYMATE_LLM_TEMPERATURE", 0.0)
    llm_timeout_seconds: float = _float_env("STUDYMATE_LLM_TIMEOUT", 30.0)
    embedding_device: str | None = os.getenv("STUDYMATE_EMBEDDING_DEVICE") or None

    chunk_size: int = _int_env("STUDYMATE_CHUNK_SIZE", 300)
    chunk_overlap: int = _int_env("STUDYMATE_CHUNK_OVERLAP", 60)
    chunk_max_tokens: int = _int_env("STUDYMATE_CHUNK_MAX_TOKENS", 384)
    default_top_k: int = _int_env("STUDYMATE_TOP_K", 6)
    min_retrieval_similarity: float = _float_env("STUDYMATE_MIN_RETRIEVAL_SIMILARITY", 0.35)
    embedding_batch_size: int = _int_env("STUDYMATE_EMBEDDING_BATCH_SIZE", 64)
    max_upload_size_mb: int = _int_env("STUDYMATE_MAX_UPLOAD_SIZE_MB", 25)

    def __post_init__(self) -> None:
        if self.chat_mode not in {"generation", "retrieval_only"}:
            raise ValueError("STUDYMATE_CHAT_MODE 必须是 generation 或 retrieval_only")
        if self.llm_timeout_seconds <= 0 or not 1 <= self.default_top_k <= 10:
            raise ValueError("LLM timeout 必须大于 0，top_k 必须在 1 到 10 之间")
        if self.chunk_max_tokens < 8 or not 0 <= self.min_retrieval_similarity <= 1:
            raise ValueError("chunk token 上限至少为 8，相似度阈值须在 0 到 1 之间")

    @property
    def chat_request_timeout_seconds(self) -> float:
        # Allow time for local embedding and HTTP connection setup. No SDK retries.
        return max(60.0, self.llm_timeout_seconds + 30.0)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def summary_request_timeout_seconds(self) -> float:
        # At most eight section calls and one synthesis call, with no SDK retries.
        return max(self.chat_request_timeout_seconds, 9 * self.llm_timeout_seconds + 60)


settings = Settings()
