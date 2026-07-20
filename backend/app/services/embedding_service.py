from __future__ import annotations

import os
import logging
from functools import lru_cache

from app.core.config import settings
from app.core.errors import EmbeddingServiceError

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        logger.exception("embedding_dependency_unavailable")
        raise EmbeddingServiceError() from exc

    kwargs = {}
    if settings.embedding_device:
        kwargs["device"] = settings.embedding_device
    try:
        return SentenceTransformer(settings.embedding_model, **kwargs)
    except Exception as exc:
        logger.exception(
            "embedding_model_load_failed",
            extra={"model": settings.embedding_model},
        )
        raise EmbeddingServiceError() from exc


def embed_texts(texts: list[str]) -> list[list[float]]:
    cleaned_texts = [text.strip() for text in texts if text and text.strip()]
    if not cleaned_texts:
        return []

    model = _get_embedding_model()
    try:
        embeddings = model.encode(
            cleaned_texts,
            batch_size=max(settings.embedding_batch_size, 1),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
    except Exception as exc:
        logger.exception("embedding_generation_failed")
        raise EmbeddingServiceError() from exc
