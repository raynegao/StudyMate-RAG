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
    app_version: str = os.getenv("STUDYMATE_APP_VERSION", "0.2.0")
    log_level: str = os.getenv("STUDYMATE_LOG_LEVEL", "INFO").upper()
    frontend_api_base_url: str = os.getenv(
        "STUDYMATE_API_BASE_URL", "http://127.0.0.1:8000"
    )

    upload_dir: Path = Path(os.getenv("STUDYMATE_UPLOAD_DIR", "data/uploads"))
    chroma_dir: Path = Path(os.getenv("STUDYMATE_CHROMA_DIR", "data/chroma_db"))
    chroma_collection: str = os.getenv(
        "STUDYMATE_CHROMA_COLLECTION", "studymate_documents"
    )

    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY") or os.getenv(
        "OPENAI_API_KEY"
    )
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    embedding_model: str = os.getenv(
        "STUDYMATE_LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    llm_model: str = os.getenv("STUDYMATE_LLM_MODEL", "deepseek-v4-flash")
    llm_temperature: float = _float_env("STUDYMATE_LLM_TEMPERATURE", 0.0)
    embedding_device: str | None = os.getenv("STUDYMATE_EMBEDDING_DEVICE") or None

    chunk_size: int = _int_env("STUDYMATE_CHUNK_SIZE", 1000)
    chunk_overlap: int = _int_env("STUDYMATE_CHUNK_OVERLAP", 150)
    default_top_k: int = _int_env("STUDYMATE_TOP_K", 4)
    embedding_batch_size: int = _int_env("STUDYMATE_EMBEDDING_BATCH_SIZE", 64)
    max_upload_size_mb: int = _int_env("STUDYMATE_MAX_UPLOAD_SIZE_MB", 25)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
