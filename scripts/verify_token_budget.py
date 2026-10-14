#!/usr/bin/env python3
"""Verify long public synthetic text with the real local BGE tokenizer and encoder."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.errors import EmbeddingInputTooLongError  # noqa: E402
from app.services.embedding_service import (  # noqa: E402
    _get_embedding_model, chunk_pages_for_embedding, embed_texts,
)
from app.services.pdf_parser import PageText  # noqa: E402


def verify() -> dict:
    model = _get_embedding_model()
    prefix = "本段介绍公开虚构课程的基础概念。" * 40
    tails = ["尾部令牌有效期为九十天。", "尾部令牌有效期为三天。"]
    texts = [prefix + tail for tail in tails]
    rejected = False
    try:
        embed_texts([texts[0]])
    except EmbeddingInputTooLongError:
        rejected = True
    assert rejected, "Fixture must exceed the real model's input window"
    groups = [
        chunk_pages_for_embedding(
            [PageText(1, text)], document_id="a" * 32, filename="public-token-fixture.pdf",
            chunk_size=1000, chunk_overlap=60,
        )
        for text in texts
    ]
    lengths = model.tokenizer([c.text for group in groups for c in group], truncation=False, return_length=True)["length"]
    limit = min(settings.chunk_max_tokens, model.max_seq_length)
    assert max(lengths) <= limit
    assert all(group[-1].text.endswith(tail) for group, tail in zip(groups, tails))
    vectors = embed_texts([group[-1].text for group in groups])
    delta = max(abs(a - b) for a, b in zip(*vectors))
    assert delta > 1e-6, "Different tails must reach the encoder"
    return {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.embedding_model, "all_content_fictional": True,
        "external_llm_called": False, "storage_index_read": False,
        "fixture_characters": [len(t) for t in texts],
        "oversized_unsplit_input_rejected": rejected,
        "chunk_counts": [len(g) for g in groups], "max_actual_tokens": max(lengths),
        "token_budget": limit, "tail_preserved": True, "tail_embedding_max_abs_difference": delta,
    }


if __name__ == "__main__":
    result = verify()
    output = ROOT / "output/e2e/token-budget-result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
