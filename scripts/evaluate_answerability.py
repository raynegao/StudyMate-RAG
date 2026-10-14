#!/usr/bin/env python3
"""Measure missing-evidence refusal and held-out answers on public fictional PDFs."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.rag_service import answer_from_chunks, filter_relevant_chunks  # noqa: E402
from scripts.evaluate_rag import (  # noqa: E402
    as_retrieved_chunk, build_chunks, dataset_sha256, embed_texts, git_revision,
    is_relevant, keywords_present, load_benchmark, rank_chunks,
)

MANIFEST = ROOT_DIR / "evaluation/answerability_benchmark.json"
OUTPUT = ROOT_DIR / "output/evaluation/answerability-results.json"
REPORT = ROOT_DIR / "docs/answerability-evaluation.md"


def run(with_llm: bool) -> dict:
    if with_llm and (not settings.deepseek_api_key or settings.chat_mode != "generation"):
        raise RuntimeError("--with-llm requires a configured generation-mode public benchmark")
    questions = json.loads(MANIFEST.read_text(encoding="utf-8"))["questions"]
    chunks = build_chunks(load_benchmark(), chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
    vectors = embed_texts([c.text for c in chunks])
    query_vectors = embed_texts([q["question"] for q in questions])
    calibration_questions = load_benchmark()["questions"]
    calibration_scores = [
        rank_chunks(chunks, vectors, v)[0][1]
        for v in embed_texts([q["question"] for q in calibration_questions])
    ]
    records = []
    for q, vector in zip(questions, query_vectors):
        ranked = rank_chunks(chunks, vectors, vector)
        retrieved = [as_retrieved_chunk(c, s) for c, s in ranked[:settings.default_top_k]]
        retained = filter_relevant_chunks(retrieved)
        positive = q["kind"] == "answerable"
        record = {
            "id": q["id"], "question": q["question"], "split": q["split"], "kind": q["kind"],
            "top_similarity": ranked[0][1], "gate_rejected": not retained,
            "retrieval_has_evidence": any(is_relevant(c, q) for c in retained) if positive else False,
            "answer_correct": None, "refusal_correct": None, "citation_evidence_precision": None,
            "external_llm_called": with_llm and bool(retained),
        }
        if with_llm:
            response = answer_from_chunks(q["question"], retrieved)
            cited = [s for s in response["sources"] if s["cited"]]
            supported = sum(
                s["filename"] == q.get("gold_document") and s["page_number"] == q.get("gold_page")
                for s in cited
            )
            record.update({
                "answer": response["answer"], "status": response["status"],
                "answer_correct": response["status"] == "answered" and keywords_present(response["answer"], q["answer_keywords"]) if positive else None,
                "refusal_correct": response["status"] == "insufficient_evidence" and not cited if not positive else None,
                "citation_evidence_precision": supported / len(cited) if cited else 0.0,
            })
        records.append(record)
        print(f"{q['id']}: gate_rejected={not retained}, status={record.get('status', 'retrieval_only')}", flush=True)
    groups = {}
    for split in ("calibration", "held_out"):
        group = [r for r in records if r["split"] == split]
        negatives = [r for r in group if r["kind"] != "answerable"]
        positives = [r for r in group if r["kind"] == "answerable"]
        groups[split] = {
            "unanswerable_count": len(negatives), "answerable_count": len(positives),
            "refusal_accuracy": sum(r["refusal_correct"] for r in negatives) / len(negatives) if with_llm and negatives else None,
            "answer_accuracy": sum(r["answer_correct"] for r in positives) / len(positives) if with_llm and positives else None,
            "retrieval_evidence_recall": sum(r["retrieval_has_evidence"] for r in positives) / len(positives) if positives else None,
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "git_revision": git_revision(),
        "benchmark_sha256": dataset_sha256(MANIFEST), "public_pdf_manifest_sha256": dataset_sha256(),
        "all_content_fictional": True, "with_llm": with_llm,
        "configuration": {"chunk_size":settings.chunk_size,"overlap":settings.chunk_overlap,"top_k":settings.default_top_k,"min_similarity":settings.min_retrieval_similarity},
        "method": "Separate retrieval page evidence, keyword answer correctness and cited-page support; citation syntax alone is not semantic support. Fixed splits; no held-out threshold tuning.",
        "groups": groups, "records": records,
        "calibration": {
            "positive_source": "original 30-question public benchmark",
            "positive_min_top_similarity": min(calibration_scores),
            "positive_gate_acceptance": sum(s >= settings.min_retrieval_similarity for s in calibration_scores) / len(calibration_scores),
            "out_of_domain_max_top_similarity": max(r["top_similarity"] for r in records if r["split"] == "calibration" and r["kind"] == "out_of_domain"),
            "selection_rule": "Conservative threshold within the calibration gap; held-out cases are regression checks, not a blind generalization claim.",
        },
    }


def render_report(result: dict) -> str:
    rows = []
    for r in result["records"]:
        outcome = r["answer_correct"] if r["kind"] == "answerable" else r["refusal_correct"]
        rows.append(f"| {r['id']} | {r['split']} | {r['kind']} | {r['top_similarity']:.3f} | {r['gate_rejected']} | {outcome} |")
    return "\n".join([
        "# Answerability evaluation", "",
        "18 additional questions over the public fictional PDFs: 6 held-out answerable paraphrases and 12 unanswerable questions (6 calibration, 6 held-out). Missing-fact negatives share the document's topic but ask for facts that are absent.", "",
        f"Generated: {result['generated_at']}; real LLM evaluation: {result['with_llm']}.", "",
        "The serving relevance gate and answer/citation guard are used unchanged. A low similarity can reject irrelevant context locally; high similarity does not establish answerability. Related missing-fact questions are tested through real generation. The threshold is selected using the original 30 answerable questions and calibration negatives. The held-out split is a development regression set, not a blind generalization claim.", "",
        "```json", json.dumps(result["calibration"], ensure_ascii=False, indent=2), "```", "",
        "```json", json.dumps(result["groups"], ensure_ascii=False, indent=2), "```", "",
        "| Case | Split | Kind | Top cosine | Gate rejected | Answer/refusal correct |",
        "| --- | --- | --- | ---: | --- | --- |", *rows, "",
        "## Reproduce", "",
        "Load `.env.local`, then run `.venv/bin/python scripts/evaluate_answerability.py --with-llm`. Omit the flag for local retrieval checks only.", "",
        "## Limits", "",
        "Gold-page support and keyword correctness are auditable proxies, not a semantic entailment judge. The small synthetic set cannot prove universal refusal reliability. True/False outcomes require `with_llm=true`; a retrieval-only run leaves them null.", "",
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-llm", action="store_true")
    args = parser.parse_args()
    result = run(args.with_llm)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(render_report(result), encoding="utf-8")
    print(json.dumps(result["groups"], ensure_ascii=False))
