from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import settings

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@lru_cache(maxsize=1)
def _get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "缺少 sentence-transformers 依赖，无法使用本地 BGE embedding。"
        ) from exc

    kwargs = {}
    if settings.embedding_device:
        kwargs["device"] = settings.embedding_device
    return SentenceTransformer(settings.embedding_model, **kwargs)


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
    except Exception as exc:
        raise RuntimeError(f"BGE embedding 生成失败：{exc}") from exc

    return embeddings.tolist()
