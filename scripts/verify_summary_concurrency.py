#!/usr/bin/env python3
"""Compare sequential and concurrent whole-document summaries with real DeepSeek calls.

Uses a generated, fully fictional multi-batch document; no uploaded file, index or
private text is read. Both runs go through the serving summary path, including the
batch budget check and citation validation.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.errors import LLMServiceError, LLMTimeoutError, SummaryCitationError  # noqa: E402
from app.services import summary_service  # noqa: E402
from app.services.vector_store import RetrievedChunk  # noqa: E402

DOCUMENT_ID = "f" * 32
TRIALS = 3
STATIONS = ("青石", "白桦", "赤岩", "雾港", "松涛", "银滩", "落霞", "望川")


def fictional_chunks() -> list[RetrievedChunk]:
    chunks = []
    for page, station in enumerate(STATIONS, start=1):
        for part in range(30):
            code = page * 100 + part
            text = (
                f"{station}气象站第 {part + 1} 节：虚构传感器 {station}-{code} 每 {part + 3} 分钟上报一次读数，"
                f"读数超过 {40 + part} 个单位时转入人工复核，复核记录保留 {page * 7} 天。"
                f"传感器更换后需要静置 {part + 2} 小时再接入主链路，静置期间只记录状态摘要。"
                f"该站与相邻站点每天在第 {part % 6 + 1} 个整点交换一次校准表，交换失败时沿用前一日校准表。"
            ) * 2
            chunks.append(RetrievedChunk(f"{DOCUMENT_ID}:p{page}:c{part}", DOCUMENT_ID, "public-fictional-stations.pdf",
                                         page, part, text))
    return chunks


def labels(text: str) -> set[str]:
    return {f"S{int(n)}" for n in re.findall(r"\[S(\d+)\]", text)}


def run_once(chunks: list[RetrievedChunk], concurrency: int, real_complete) -> dict:
    """One serving-path summary; on a citation failure, record which step and why."""
    outputs: list[tuple[str, str]] = []

    def spy(prompt: str) -> str:
        answer = real_complete(prompt)
        outputs.append(("synthesis" if "<不可信摘要>" in prompt else "section", answer))
        return answer

    summary_service.settings = replace(settings, summary_concurrency=concurrency)
    summary_service.get_document_chunks = lambda document_id: chunks
    summary_service.complete_answer = spy
    started = time.perf_counter()
    try:
        result = summary_service.summarize_document(DOCUMENT_ID, "请概括这份资料的主要内容和关键数字。")
        record = {"status": result["status"], "batches": result["metadata"]["batches"],
                  "cited_sources": sum(source["cited"] for source in result["sources"])}
    except SummaryCitationError:
        notes = [answer for kind, answer in outputs if kind == "section"]
        synthesis = [answer for kind, answer in outputs if kind == "synthesis"]
        allowed = set().union(*(set(re.findall(r"S\d+", note)) for note in notes)) if notes else set()
        record = {"status": "summary_citations_invalid",
                  "failed_step": "synthesis" if synthesis else "section",
                  "synthesis_citations": len(labels(synthesis[0])) if synthesis else None,
                  "synthesis_citations_not_in_section_notes": len(labels(synthesis[0]) - allowed) if synthesis else None}
    except (LLMServiceError, LLMTimeoutError) as exc:
        # Provider failures (balance, rate limit, network) are not summary results.
        record = {"status": exc.code, "provider_error": True}
    record.update({"summary_concurrency": concurrency, "elapsed_seconds": round(time.perf_counter() - started, 2)})
    return record


def main() -> None:
    if not settings.deepseek_api_key or settings.chat_mode != "generation":
        raise SystemExit("Load .env.local first: DEEPSEEK_API_KEY and generation mode are required.")
    chunks = fictional_chunks()
    real_complete = summary_service.complete_answer
    runs, aborted = [], None
    for trial in range(TRIALS):
        # Alternate the order so provider load drifts do not favour one mode.
        for concurrency in ((1, 4) if trial % 2 == 0 else (4, 1)):
            runs.append(run_once(chunks, concurrency, real_complete))
            print(json.dumps(runs[-1], ensure_ascii=False), flush=True)
            if runs[-1].get("provider_error"):
                aborted = f"provider error {runs[-1]['status']} on run {len(runs)}; no further requests sent"
                break
        if aborted:
            break

    def median_success(concurrency: int) -> float | None:
        times = [r["elapsed_seconds"] for r in runs
                 if r["summary_concurrency"] == concurrency and r["status"] == "answered"]
        return round(statistics.median(times), 2) if times else None

    sequential, concurrent = median_success(1), median_success(4)
    result = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "llm_model": settings.llm_model, "all_content_fictional": True,
        "storage_index_read": False, "document_characters": sum(len(c.text) for c in chunks),
        "llm_timeout_seconds": settings.llm_timeout_seconds, "trials_per_mode": TRIALS,
        "runs": runs,
        "median_seconds_successful": {"sequential": sequential, "concurrency_4": concurrent},
        "speedup": round(sequential / concurrent, 2) if sequential and concurrent else None,
        "citation_failures": sum(r["status"] == "summary_citations_invalid" for r in runs),
        "aborted": aborted,
        "note": "Small sample; provider latency varies, so the speedup is indicative, not a benchmark. "
                "Citation failures are the designed guard rejecting labels that are not in the section notes.",
    }
    output = ROOT / "output/e2e/summary-concurrency-result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
