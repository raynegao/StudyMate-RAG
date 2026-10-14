#!/usr/bin/env python3
"""Check the prepared v2 course profile through the real API, without external generation."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from fastapi.testclient import TestClient  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.embedding_service import _get_embedding_model  # noqa: E402
from app.services.vector_store import _collection  # noqa: E402
from scripts.evaluate_real_course import load_manifest  # noqa: E402


def verify() -> dict:
    if settings.chroma_dir.resolve() != ROOT_DIR / "data/chroma_db/real-course-v2" or settings.chat_mode != "retrieval_only":
        raise RuntimeError("只验证显式准备的 v2 课程库；请用 scripts/run_real_course.sh verify")
    records = []
    with TestClient(create_app()) as client:
        config = client.get("/api/config").json()
        assert config["max_upload_size_mb"] == 70
        assert config["chat_mode"] == "retrieval_only"
        documents = client.get("/api/documents").json()["documents"]
        assert {d["filename"] for d in documents} == {"course-a.pdf", "course-b.pdf", "course-c.pdf"}
        for q in load_manifest()["questions"]:
            started = time.perf_counter()
            response = client.post("/api/chat", json={"question": q["question"]})
            response.raise_for_status()
            data = response.json()
            assert data["status"] == "retrieval_only"
            assert not any(s["cited"] for s in data["sources"])
            rank = next((i for i, s in enumerate(data["sources"], 1) if s["filename"] == q["gold_document"] and s["page"] in q.get("accepted_pages", [q["gold_page"]])), None)
            strict_rank = next((i for i, s in enumerate(data["sources"], 1) if s["filename"] == q["gold_document"] and s["page"] == q["gold_page"]), None)
            records.append({"id": q["id"], "gold_rank": rank, "original_page_rank": strict_rank, "latency_ms": (time.perf_counter()-started)*1000})
        refusal = client.post("/api/chat", json={"question": "昨天的网球决赛比分是多少？"}).json()
        assert refusal["status"] == "insufficient_evidence"
    model = _get_embedding_model()
    # This is the new v2 collection created by the preparation step, never a legacy index.
    texts = _collection().get(include=["documents"])["documents"]
    lengths = [len(model.tokenizer(t, truncation=False)["input_ids"]) for t in texts]
    assert max(lengths) <= min(settings.chunk_max_tokens, model.max_seq_length)
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(), "profile": "real-course-v2",
        "document_count": len(documents), "chunk_count": len(texts), "max_chunk_tokens": max(lengths),
        "runtime_config": config, "external_llm_calls": False, "legacy_index_read": False,
        "retrieval_recall": {str(k):sum(r["gold_rank"] is not None and r["gold_rank"] <= k for r in records)/len(records) for k in [1,3,5,6]},
        "original_page_recall_at_6": sum(r["original_page_rank"] is not None for r in records)/len(records),
        "out_of_domain_refused": True, "records": records,
    }
    output = ROOT_DIR / "output/e2e/real-course-local-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
