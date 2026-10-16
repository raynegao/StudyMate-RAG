#!/usr/bin/env python3
"""Check the configured answer model (DeepSeek or Gemini) through the serving paths.

Sends two short, fully fictional prompts: one scoped question through the answer path
and one whole-document summary over two fictional chunks. No uploaded file, index or
private text is read. The result is written to output/e2e/ without any key.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.errors import ServiceError  # noqa: E402
from app.services import rag_service, summary_service  # noqa: E402
from app.services.vector_store import RetrievedChunk  # noqa: E402

DOCUMENT_ID = "e" * 32
FILENAME = "public-fictional-check.pdf"
CHUNKS = [
    RetrievedChunk(f"{DOCUMENT_ID}:p1:c0", DOCUMENT_ID, FILENAME, 1, 0,
                   "蓝色令牌是虚构星港课程中的通行凭证，有效期为三个星港周期，到期后必须重新申请，不能顺延。", 0.2),
    RetrievedChunk(f"{DOCUMENT_ID}:p2:c0", DOCUMENT_ID, FILENAME, 2, 0,
                   "绿色令牌只用于货运闸口，每次使用后需要等待两个星港周期才能再次激活。", 0.3),
]


def timed(step: str, check) -> dict:
    started = time.perf_counter()
    try:
        record = {"ok": True, **check()}
    except ServiceError as exc:
        record = {"ok": False, "error_code": exc.code}
    record["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    print(f"{step}: {json.dumps(record, ensure_ascii=False)}", flush=True)
    return record


def check_question() -> dict:
    response = rag_service.answer_from_chunks("蓝色令牌的有效期是多少？", CHUNKS)
    return {
        "status": response["status"],
        "keyword_found": "三个星港周期" in response["answer"],
        "cited": [source["citation_id"] for source in response["sources"] if source["cited"]],
    }


def check_summary() -> dict:
    summary_service.get_document_chunks = lambda document_id: CHUNKS  # fictional chunks only
    response = summary_service.summarize_document(DOCUMENT_ID, "请概括这份资料的主要内容。")
    return {
        "status": response["status"],
        "cited_sources": sum(source["cited"] for source in response["sources"]),
        "batches": response["metadata"]["batches"],
    }


def main() -> int:
    if settings.chat_mode != "generation":
        raise SystemExit("STUDYMATE_CHAT_MODE must be generation for this check.")
    if not settings.llm_api_key:
        raise SystemExit(f"No API key for provider {settings.llm_provider}. Load .env.local first.")
    print(f"provider={settings.llm_provider} model={settings.llm_model}", flush=True)
    question = timed("question", check_question)
    summary = timed("summary", check_summary)
    passed = (
        question["ok"] and question["status"] == "answered" and question["keyword_found"] and bool(question["cited"])
        and summary["ok"] and summary["status"] == "answered" and summary["cited_sources"] > 0
    )
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "llm_provider": settings.llm_provider, "llm_model": settings.llm_model,
        "all_content_fictional": True, "storage_index_read": False,
        "question": question, "summary": summary, "passed": passed,
    }
    output = ROOT / "output" / "e2e" / f"llm-provider-{settings.llm_provider}-result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
