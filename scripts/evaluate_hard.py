#!/usr/bin/env python3
"""Evaluate harder question types with the same document-scoped retrieval the app uses.

Public part: three fictional hard PDFs (original pages plus a page of confusable entities),
optionally with answers from the configured model provider. Real-course part: retrieval-only over the anonymous course
PDFs listed in the git-ignored private source map; only IDs, types and ranks are written.
The original 30 public and 15 real-course questions are re-measured with the same method as
a reference, so the difficulty gap is comparable. Question sets are fixed before running.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
for path in (ROOT_DIR, ROOT_DIR / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.core.config import settings  # noqa: E402
from app.services.rag_service import answer_from_chunks  # noqa: E402
from scripts import evaluate_real_course as real  # noqa: E402
from scripts.evaluate_rag import (  # noqa: E402
    as_retrieved_chunk,
    build_chunks,
    character_ngrams,
    dataset_sha256,
    embed_texts,
    git_revision,
    keywords_present,
    lexical_rank_chunks,
    load_benchmark,
    package_version,
    rank_chunks,
)

HARD_PATH = ROOT_DIR / "evaluation" / "hard_benchmark.json"
REAL_HARD_PATH = ROOT_DIR / "evaluation" / "real_course_hard_benchmark.json"
RESULT_PATH = ROOT_DIR / "output" / "evaluation" / "hard-results.json"
REPORT_PATH = ROOT_DIR / "docs" / "hard-evaluation.md"
TOP_K_VALUES = (1, 3, 6)
PUBLIC_TYPES = {"paraphrase", "distractor", "boundary", "multi_page"}
REAL_TYPES = {"paraphrase", "numeric", "distractor", "condition", "multi_page"}
RETRIEVERS = ("bge", "lexical")
SCOPES = ("document", "global")


def _validate_questions(questions: list[dict[str, Any]], types: set[str], pages: dict[str, int]) -> None:
    if len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Hard question IDs must be unique.")
    for question in questions:
        if question["type"] not in types:
            raise ValueError(f"Unknown type for {question['id']}: {question['type']}")
        if question["gold_document"] not in pages:
            raise ValueError(f"Unknown document for {question['id']}.")
        groups = question.get("evidence") or []
        if not groups or (question["type"] == "multi_page") != (len(groups) > 1):
            raise ValueError(f"Evidence groups do not match the type of {question['id']}.")
        for group in groups:
            if not group.get("pages") or not group.get("keywords"):
                raise ValueError(f"Empty evidence group in {question['id']}.")
            if any(not isinstance(p, int) or not 1 <= p <= pages[question["gold_document"]] for p in group["pages"]):
                raise ValueError(f"Evidence page out of range in {question['id']}.")


def load_hard(path: Path = HARD_PATH) -> dict[str, Any]:
    hard = json.loads(path.read_text(encoding="utf-8"))
    base = {d["filename"]: d for d in load_benchmark()["documents"]}
    pages = {}
    for document in hard["documents"]:
        if document["base_document"] not in base:
            raise ValueError(f"Unknown base document for {document['filename']}.")
        # Cover page + unchanged base pages + extra confusable pages.
        pages[document["filename"]] = 1 + len(base[document["base_document"]]["pages"]) + len(document["extra_pages"])
    _validate_questions(hard["questions"], PUBLIC_TYPES, pages)
    for question in hard["questions"]:
        if not question.get("answer_keywords"):
            raise ValueError(f"Missing answer keywords for {question['id']}.")
    return hard


def load_real_hard(path: Path = REAL_HARD_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    hard = json.loads(path.read_text(encoding="utf-8"))
    base = real.load_manifest(path.parent / hard["base_manifest"])
    pages = {d["filename"]: d["page_count"] for d in base["documents"]}
    _validate_questions(hard["questions"], REAL_TYPES, pages)
    return hard, base


def as_evidence(question: dict[str, Any]) -> list[dict[str, Any]]:
    """Original single-page questions expressed as one evidence group."""
    return question.get("evidence") or [
        {"pages": question.get("accepted_pages", [question["gold_page"]])}
    ]


def coverage_rank(ranked: list, question: dict[str, Any]) -> int | None:
    """Rank at which every evidence group has a retrieved chunk on one of its pages."""
    remaining = list(range(len(as_evidence(question))))
    groups = as_evidence(question)
    for rank, (chunk, _) in enumerate(ranked, start=1):
        if chunk.filename != question["gold_document"]:
            continue
        remaining = [i for i in remaining if chunk.page_number not in groups[i]["pages"]]
        if not remaining:
            return rank
    return None


def rank_everything(questions: list[dict[str, Any]], chunks: list) -> tuple[dict, dict]:
    """Return per-question ranks and the document-scoped BGE ranking used for answers."""
    vectors = embed_texts([chunk.text for chunk in chunks])
    query_vectors = embed_texts([question["question"] for question in questions])
    grams = [character_ngrams(chunk.text) for chunk in chunks]
    ranks, answer_rankings = {}, {}
    for question, query_vector in zip(questions, query_vectors):
        rankings = {
            "bge": rank_chunks(chunks, vectors, query_vector),
            "lexical": lexical_rank_chunks(chunks, grams, question["question"]),
        }
        ranks[question["id"]] = {}
        for retriever, ranked in rankings.items():
            scoped = [item for item in ranked if item[0].filename == question["gold_document"]]
            ranks[question["id"]][retriever] = {
                "document": coverage_rank(scoped, question),
                "global": coverage_rank(ranked, question),
            }
            if retriever == "bge":
                answer_rankings[question["id"]] = scoped
    return ranks, answer_rankings


def summarize(questions: list[dict[str, Any]], ranks: dict) -> dict[str, Any]:
    def recall(items: list[dict[str, Any]], retriever: str, scope: str) -> dict[str, float]:
        values = [ranks[q["id"]][retriever][scope] for q in items]
        return {f"recall_at_{k}": statistics.fmean(v is not None and v <= k for v in values) for k in TOP_K_VALUES}

    groups = {"all": questions}
    for question_type in sorted({q.get("type", "original") for q in questions}):
        groups[question_type] = [q for q in questions if q.get("type", "original") == question_type]
    return {
        name: {
            "question_count": len(items),
            **{f"{retriever}_{scope}": recall(items, retriever, scope) for retriever in RETRIEVERS for scope in SCOPES},
        }
        for name, items in groups.items()
    }


def evaluate_answers(questions: list[dict[str, Any]], rankings: dict) -> dict[str, Any]:
    if not settings.llm_api_key or settings.chat_mode != "generation":
        raise RuntimeError(f"--with-llm needs an API key for {settings.llm_provider} and generation mode. Load .env.local first.")
    records, latencies = [], []
    for index, question in enumerate(questions, start=1):
        retrieved = [as_retrieved_chunk(chunk, score) for chunk, score in rankings[question["id"]][: settings.default_top_k]]
        started = time.perf_counter()
        response = answer_from_chunks(question["question"], retrieved)
        latencies.append((time.perf_counter() - started) * 1000)
        answer = response["answer"]
        evidence_pages = {page for group in question["evidence"] for page in group["pages"]}
        cited = [source for source in response["sources"] if source["cited"]]
        supported = sum(source["page_number"] in evidence_pages for source in cited)
        forbidden = [k for k in question.get("forbidden_answer_keywords", []) if keywords_present(answer, [k])]
        correct = response["status"] == "answered" and keywords_present(answer, question["answer_keywords"]) and not forbidden
        records.append({
            "id": question["id"], "type": question["type"], "status": response["status"], "answer": answer,
            "answer_correct": correct, "forbidden_keywords_found": forbidden,
            "citation_support": supported / len(cited) if cited else 0.0, "latency_ms": latencies[-1],
        })
        print(f"[{index:02d}/{len(questions)}] {question['id']} answer={'ok' if correct else 'miss'}", flush=True)

    def rate(items: list[dict[str, Any]], key: str) -> float:
        return statistics.fmean(float(item[key]) for item in items)

    by_type = {}
    for question_type in sorted({r["type"] for r in records}):
        items = [r for r in records if r["type"] == question_type]
        by_type[question_type] = {"question_count": len(items), "answer_accuracy": rate(items, "answer_correct"),
                                  "citation_support": rate(items, "citation_support")}
    return {
        "llm_provider": settings.llm_provider, "llm_model": settings.llm_model,
        "top_k": settings.default_top_k, "scope": "document",
        "answer_accuracy": rate(records, "answer_correct"), "citation_support": rate(records, "citation_support"),
        "answered_rate": statistics.fmean(r["status"] == "answered" for r in records),
        "generation_latency_mean_ms": statistics.fmean(latencies),
        "by_type": by_type, "questions": records,
    }


def run(*, with_llm: bool, include_real: bool) -> dict[str, Any]:
    embed_texts(["StudyMate hard benchmark warmup"])
    size, overlap = settings.chunk_size, settings.chunk_overlap
    hard = load_hard()
    original = load_benchmark()
    public_chunks = build_chunks(hard, chunk_size=size, chunk_overlap=overlap)
    hard_ranks, answer_rankings = rank_everything(hard["questions"], public_chunks)
    original_ranks, _ = rank_everything(original["questions"], build_chunks(original, chunk_size=size, chunk_overlap=overlap))
    result: dict[str, Any] = {
        "benchmark": {
            "public_hard": {"name": hard["name"], "version": hard["version"], "dataset_sha256": dataset_sha256(HARD_PATH),
                            "question_count": len(hard["questions"]), "all_content_fictional": True},
            "questions_frozen_before_first_run": True,
        },
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(), "git_revision": git_revision(),
            "embedding_model": settings.embedding_model, "sentence_transformers": package_version("sentence-transformers"),
            "torch": package_version("torch"), "chunk_size": size, "chunk_overlap": overlap,
            "chunk_max_tokens": settings.chunk_max_tokens, "top_k_values": list(TOP_K_VALUES),
        },
        "method": (
            "A question counts as retrieved at K only when every evidence group has a chunk from one of its pages "
            "in the top K. Document scope ranks only chunks of the gold document, as the app does for a selected PDF; "
            "global scope ranks the whole corpus. The original questions are re-measured with the same rule."
        ),
        "public": {
            "hard": {"retrieval": summarize(hard["questions"], hard_ranks),
                     "questions": [{"id": q["id"], "type": q["type"], "ranks": hard_ranks[q["id"]]} for q in hard["questions"]],
                     "answer_evaluation": evaluate_answers(hard["questions"], answer_rankings) if with_llm else None},
            "original_reference": {"retrieval": summarize(original["questions"], original_ranks)},
        },
        "real_course": None,
    }
    if include_real:
        real_hard, base = load_real_hard()
        sources = real.load_source_map(real.SOURCE_MAP_PATH, {d["filename"] for d in base["documents"]})
        page_text = real.validate_sources(base, sources)
        for question in real_hard["questions"]:
            for group in question["evidence"]:
                for page in group["pages"]:
                    if not keywords_present(page_text[question["gold_document"]][page], group["keywords"]):
                        raise ValueError(f"Evidence keywords not found for {question['id']} p.{page}.")
        chunks = real.build_chunks(base, sources, chunk_size=size, chunk_overlap=overlap)
        real_ranks, _ = rank_everything(real_hard["questions"], chunks)
        base_ranks, _ = rank_everything(base["questions"], chunks)
        result["benchmark"]["real_course_hard"] = {
            "name": real_hard["name"], "version": real_hard["version"], "dataset_sha256": dataset_sha256(REAL_HARD_PATH),
            "question_count": len(real_hard["questions"]), "all_content_fictional": False,
            "source_hashes_verified": True, "evidence_keywords_verified": True,
        }
        result["real_course"] = {
            "hard": {"retrieval": summarize(real_hard["questions"], real_ranks),
                     "questions": [{"id": q["id"], "type": q["type"], "ranks": real_ranks[q["id"]]} for q in real_hard["questions"]]},
            "original_reference": {"retrieval": summarize(base["questions"], base_ranks)},
            "privacy": {"source_files_committed": False, "source_paths_in_output": False,
                        "source_text_in_output": False, "external_llm_calls": False},
        }
    return result


def percent(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


def render_report(result: dict[str, Any]) -> str:
    def overview_row(label: str, summary: dict[str, Any]) -> str:
        overall = summary["all"]
        bge, lex, glob = overall["bge_document"], overall["lexical_document"], overall["bge_global"]
        return (f"| {label} | {overall['question_count']} | {percent(bge['recall_at_1'])} | {percent(bge['recall_at_3'])} | "
                f"{percent(bge['recall_at_6'])} | {percent(lex['recall_at_1'])} | {percent(lex['recall_at_6'])} | "
                f"{percent(glob['recall_at_1'])} |")

    def type_rows(summary: dict[str, Any]) -> list[str]:
        return [
            f"| {name} | {item['question_count']} | {percent(item['bge_document']['recall_at_1'])} | "
            f"{percent(item['bge_document']['recall_at_6'])} | {percent(item['lexical_document']['recall_at_1'])} | "
            f"{percent(item['lexical_document']['recall_at_6'])} |"
            for name, item in summary.items() if name != "all"
        ]

    def question_rows(questions: list[dict[str, Any]], answers: dict[str, Any] | None) -> list[str]:
        rows = []
        for q in questions:
            answer = answers.get(q["id"]) if answers else None
            outcome = "-" if answer is None else ("correct" if answer["answer_correct"] else f"miss ({answer['status']})")
            rows.append(f"| {q['id']} | {q['type']} | {q['ranks']['bge']['document'] or '>all'} | "
                        f"{q['ranks']['lexical']['document'] or '>all'} | {outcome} |")
        return rows

    public, real_course, run_info = result["public"], result["real_course"], result["run"]
    overview = [overview_row("Public original (30)", public["original_reference"]["retrieval"]),
                overview_row("Public hard", public["hard"]["retrieval"])]
    if real_course:
        overview += [overview_row("Real course original (15)", real_course["original_reference"]["retrieval"]),
                     overview_row("Real course hard", real_course["hard"]["retrieval"])]
    answers = public["hard"]["answer_evaluation"]
    answer_lookup = {r["id"]: r for r in answers["questions"]} if answers else None
    lines = [
        "# Hard-question evaluation", "",
        "Generated by `scripts/evaluate_hard.py`. The original benchmarks saturate (every retriever finds almost every gold page), "
        "so they cannot show whether a change helps or hurts. This set adds harder question types and re-measures the original "
        "questions with the same rule as a reference. Questions were fixed before the first run and are not tuned to results.", "",
        f"Measured at `{run_info['generated_at']}` with `{run_info['embedding_model']}`, chunk size {run_info['chunk_size']}, "
        f"overlap {run_info['chunk_overlap']}, {run_info['chunk_max_tokens']}-token chunk budget.", "",
        "## Method", "",
        "- **Document scope** ranks only the chunks of the gold PDF, which is how the app retrieves for a selected document. "
        "**Global scope** ranks every chunk in the corpus and is shown for comparison.",
        "- A question counts as retrieved at K only when every evidence group has a chunk from one of its pages in the top K. "
        "Multi-page questions therefore need all of their pages.",
        "- Public hard PDFs keep the original pages 2-4 unchanged and add page 5 with confusable entities that differ only in "
        "name and value, plus procedures that point back to earlier pages.",
        "- Question types: **paraphrase** avoids the source's named entities; **distractor** has a confusable entity in the same "
        "document; **boundary** and **condition** ask about an edge value or rule; **numeric** asks for a specific number; "
        "**multi_page** needs several pages.", "",
        "## Overview", "",
        "| Set | Questions | BGE R@1 | BGE R@3 | BGE R@6 | n-gram R@1 | n-gram R@6 | BGE global R@1 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |", *overview, "",
        "R@K is document-scoped unless marked global. The app uses BGE with top 6.", "",
        "## Public hard set by type", "",
        "| Type | Questions | BGE R@1 | BGE R@6 | n-gram R@1 | n-gram R@6 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |", *type_rows(public["hard"]["retrieval"]), "",
    ]
    if answers:
        lines += [
            "## Public hard set answers", "",
            f"Answers come from `{answers['llm_model']}` through the serving answer path (relevance gate, citation guard and refusal) "
            f"with document-scoped BGE top {answers['top_k']}. An answer is correct only when it is answered, contains every answer "
            "keyword and contains none of the distractor values listed for that question. Citation support is the share of cited "
            "sources that lie on an evidence page.", "",
            "| Type | Questions | Answer accuracy | Citation support |", "| --- | ---: | ---: | ---: |",
            *[f"| {name} | {item['question_count']} | {percent(item['answer_accuracy'])} | {percent(item['citation_support'])} |"
              for name, item in answers["by_type"].items()],
            f"| all | {len(answers['questions'])} | {percent(answers['answer_accuracy'])} | {percent(answers['citation_support'])} |", "",
        ]
    lines += [
        "## Public hard questions", "",
        "Rank is the document-scoped rank at which all evidence was retrieved; `>all` means never within the document.", "",
        "| ID | Type | BGE rank | n-gram rank | Answer |", "| --- | --- | ---: | ---: | --- |",
        *question_rows(public["hard"]["questions"], answer_lookup), "",
    ]
    if real_course:
        lines += [
            "## Real-course hard set by type", "",
            "Retrieval only and run locally. Only IDs, types and ranks are published; source PDFs, paths, text and answers are not.", "",
            "| Type | Questions | BGE R@1 | BGE R@6 | n-gram R@1 | n-gram R@6 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |", *type_rows(real_course["hard"]["retrieval"]), "",
            "| ID | Type | BGE rank | n-gram rank | Answer |", "| --- | --- | ---: | ---: | --- |",
            *question_rows(real_course["hard"]["questions"], None), "",
        ]
    lines += [
        "## Reproduce", "",
        "```bash",
        ".venv/bin/python scripts/generate_evaluation_assets.py",
        ".venv/bin/python scripts/evaluate_hard.py            # public + local real-course retrieval",
        "set -a && source .env.local && set +a",
        ".venv/bin/python scripts/evaluate_hard.py --with-llm # also model answers on the public hard set",
        ".venv/bin/python scripts/evaluate_hard.py --public-only",
        "```", "",
        "Machine-readable results: [hard-results.json](../output/evaluation/hard-results.json).", "",
        "## Limits", "",
        "- The sets are small (24 public and 15 real-course questions), so one question moves a rate by 4 to 7 points.",
        "- Keyword and forbidden-value checks are auditable proxies, not a semantic grader; a correct answer that also mentions "
        "the distractor value for contrast is counted as wrong.",
        "- The public hard pages were written to be confusable on purpose; they measure robustness, not typical document difficulty.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-llm", action="store_true", help="Call the configured answer model for the public hard set.")
    parser.add_argument("--public-only", action="store_true", help="Skip the local real-course PDFs.")
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    result = run(with_llm=args.with_llm, include_real=not args.public_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(render_report(result), encoding="utf-8")
    print(args.output)
    print(args.report)


if __name__ == "__main__":
    main()
