#!/usr/bin/env python3
"""Run the reproducible StudyMate retrieval and grounded-answer benchmark."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.chunking import DocumentChunk, split_pages_into_chunks  # noqa: E402
from app.services.embedding_service import embed_texts  # noqa: E402
from app.services.llm_service import complete_answer  # noqa: E402
from app.services.pdf_parser import extract_pdf_pages  # noqa: E402
from app.services.rag_service import build_prompt, extract_citation_ids  # noqa: E402
from app.services.vector_store import RetrievedChunk  # noqa: E402

BENCHMARK_PATH = ROOT_DIR / "evaluation" / "benchmark.json"
PDF_DIR = ROOT_DIR / "output" / "pdf" / "evaluation"
RESULT_PATH = ROOT_DIR / "output" / "evaluation" / "evaluation-results.json"
REPORT_PATH = ROOT_DIR / "docs" / "evaluation.md"
EXPERIMENTS = ((300, 60), (600, 100), (1000, 150))
TOP_K_VALUES = (1, 3, 5)
ANSWER_CHUNK_SIZE = 1000
ANSWER_OVERLAP = 150
ANSWER_TOP_K = 4


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        benchmark = json.load(file)

    questions = benchmark.get("questions") or []
    documents = benchmark.get("documents") or []
    if len(questions) != 30:
        raise ValueError(f"Expected 30 questions, found {len(questions)}.")
    if len({question["id"] for question in questions}) != len(questions):
        raise ValueError("Question IDs must be unique.")
    if len(documents) < 3:
        raise ValueError("The benchmark must contain at least three documents.")
    return benchmark


def dataset_sha256(path: Path = BENCHMARK_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document_id(filename: str) -> str:
    return hashlib.sha256(filename.encode("utf-8")).hexdigest()[:32]


def build_chunks(
    benchmark: dict[str, Any],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for document in benchmark["documents"]:
        pdf_path = PDF_DIR / document["filename"]
        if not pdf_path.exists():
            raise FileNotFoundError(
                f"Missing {pdf_path}. Run scripts/generate_evaluation_assets.py first."
            )
        pages = extract_pdf_pages(pdf_path)
        chunks.extend(
            split_pages_into_chunks(
                pages,
                document_id=document_id(document["filename"]),
                filename=document["filename"],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks


def dot_product(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def rank_chunks(
    chunks: list[DocumentChunk],
    chunk_embeddings: list[list[float]],
    query_embedding: list[float],
) -> list[tuple[DocumentChunk, float]]:
    scored = [
        (chunk, dot_product(query_embedding, embedding))
        for chunk, embedding in zip(chunks, chunk_embeddings)
    ]
    return sorted(scored, key=lambda item: item[1], reverse=True)


def character_ngrams(value: str) -> set[str]:
    normalized = normalized_text(value)
    return {
        normalized[index : index + size]
        for size in (2, 3)
        for index in range(max(len(normalized) - size + 1, 0))
    }


def lexical_rank_chunks(
    chunks: list[DocumentChunk],
    chunk_ngrams: list[set[str]],
    question: str,
) -> list[tuple[DocumentChunk, float]]:
    query_ngrams = character_ngrams(question)
    scored = []
    for chunk, grams in zip(chunks, chunk_ngrams):
        union = query_ngrams | grams
        score = len(query_ngrams & grams) / len(union) if union else 0.0
        scored.append((chunk, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)


def is_relevant(chunk: DocumentChunk | RetrievedChunk, question: dict[str, Any]) -> bool:
    page_number = getattr(chunk, "page_number")
    return (
        chunk.filename == question["gold_document"]
        and page_number == question["gold_page"]
    )


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[index]


def evaluate_retrieval(
    questions: list[dict[str, Any]],
    rankings: dict[str, list[tuple[DocumentChunk, float]]],
    *,
    top_k: int,
    retrieval_latencies_ms: list[float],
) -> dict[str, float]:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    for question in questions:
        ranked = rankings[question["id"]][:top_k]
        relevant_ranks = [
            rank
            for rank, (chunk, _) in enumerate(ranked, start=1)
            if is_relevant(chunk, question)
        ]
        recalls.append(1.0 if relevant_ranks else 0.0)
        reciprocal_ranks.append(1.0 / relevant_ranks[0] if relevant_ranks else 0.0)

    return {
        "recall_at_k": statistics.fmean(recalls),
        "mrr_at_k": statistics.fmean(reciprocal_ranks),
        "retrieval_latency_mean_ms": statistics.fmean(retrieval_latencies_ms),
        "retrieval_latency_p95_ms": percentile_95(retrieval_latencies_ms),
    }


def normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s，。；：、,.!?！？]", "", normalized)


def keywords_present(answer: str, keywords: list[str]) -> bool:
    normalized_answer = normalized_text(answer)
    return all(normalized_text(keyword) in normalized_answer for keyword in keywords)


def as_retrieved_chunk(chunk: DocumentChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        filename=chunk.filename,
        page_number=chunk.page_number,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        distance=1.0 - score,
    )


def evaluate_answers(
    questions: list[dict[str, Any]],
    rankings: dict[str, list[tuple[DocumentChunk, float]]],
) -> dict[str, Any]:
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is required for --with-llm. Load .env.local first."
        )

    records = []
    answer_latencies_ms: list[float] = []
    for index, question in enumerate(questions, start=1):
        retrieved = [
            as_retrieved_chunk(chunk, score)
            for chunk, score in rankings[question["id"]][:ANSWER_TOP_K]
        ]
        prompt = build_prompt(question["question"], retrieved)
        started = time.perf_counter()
        answer = complete_answer(prompt)
        latency_ms = (time.perf_counter() - started) * 1000
        answer_latencies_ms.append(latency_ms)

        citation_ids = sorted(
            extract_citation_ids(answer, source_count=len(retrieved)),
            key=lambda item: int(item[1:]),
        )
        cited_chunks = [retrieved[int(item[1:]) - 1] for item in citation_ids]
        relevant_citations = sum(
            is_relevant(chunk, question) for chunk in cited_chunks
        )
        citation_precision = (
            relevant_citations / len(cited_chunks) if cited_chunks else 0.0
        )
        answer_correct = keywords_present(answer, question["answer_keywords"])
        grounded = relevant_citations > 0
        records.append(
            {
                "id": question["id"],
                "question": question["question"],
                "answer": answer,
                "answer_keywords": question["answer_keywords"],
                "answer_correct": answer_correct,
                "citation_ids": citation_ids,
                "citation_precision": citation_precision,
                "has_relevant_citation": grounded,
                "latency_ms": latency_ms,
            }
        )
        print(
            f"[{index:02d}/{len(questions)}] {question['id']} "
            f"answer={'ok' if answer_correct else 'miss'} "
            f"citation={citation_precision:.2f}"
        )

    return {
        "configuration": {
            "chunk_size": ANSWER_CHUNK_SIZE,
            "chunk_overlap": ANSWER_OVERLAP,
            "top_k": ANSWER_TOP_K,
            "llm_model": settings.llm_model,
            "evaluation_method": "all gold keywords present; cited source matches gold document and page",
        },
        "answer_accuracy": statistics.fmean(
            float(record["answer_correct"]) for record in records
        ),
        "citation_accuracy": statistics.fmean(
            record["citation_precision"] for record in records
        ),
        "grounded_answer_rate": statistics.fmean(
            float(record["has_relevant_citation"]) for record in records
        ),
        "generation_latency_mean_ms": statistics.fmean(answer_latencies_ms),
        "generation_latency_p95_ms": percentile_95(answer_latencies_ms),
        "questions": records,
    }


def git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT_DIR,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def run_benchmark(*, with_llm: bool) -> dict[str, Any]:
    benchmark = load_benchmark()
    questions = benchmark["questions"]
    embed_texts(["StudyMate benchmark warmup"])
    query_embeddings = []
    query_embedding_latencies_ms = []
    for item in questions:
        started = time.perf_counter()
        query_embeddings.append(embed_texts([item["question"]])[0])
        query_embedding_latencies_ms.append(
            (time.perf_counter() - started) * 1000
        )
    retrieval_results = []
    answer_rankings = None

    for chunk_size, overlap in EXPERIMENTS:
        chunks = build_chunks(
            benchmark,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )
        index_started = time.perf_counter()
        chunk_embeddings = embed_texts([chunk.text for chunk in chunks])
        indexing_latency_ms = (time.perf_counter() - index_started) * 1000

        bge_rankings = {}
        bge_retrieval_latencies_ms = []
        for question, query_embedding, embedding_latency_ms in zip(
            questions,
            query_embeddings,
            query_embedding_latencies_ms,
        ):
            started = time.perf_counter()
            bge_rankings[question["id"]] = rank_chunks(
                chunks,
                chunk_embeddings,
                query_embedding,
            )
            bge_retrieval_latencies_ms.append(
                embedding_latency_ms + (time.perf_counter() - started) * 1000
            )

        lexical_index_started = time.perf_counter()
        chunk_ngrams = [character_ngrams(chunk.text) for chunk in chunks]
        lexical_indexing_latency_ms = (
            time.perf_counter() - lexical_index_started
        ) * 1000
        lexical_rankings = {}
        lexical_retrieval_latencies_ms = []
        for question in questions:
            started = time.perf_counter()
            lexical_rankings[question["id"]] = lexical_rank_chunks(
                chunks,
                chunk_ngrams,
                question["question"],
            )
            lexical_retrieval_latencies_ms.append(
                (time.perf_counter() - started) * 1000
            )

        for top_k in TOP_K_VALUES:
            for retriever, rankings, latencies, index_latency in (
                (
                    "BGE dense",
                    bge_rankings,
                    bge_retrieval_latencies_ms,
                    indexing_latency_ms,
                ),
                (
                    "character n-gram",
                    lexical_rankings,
                    lexical_retrieval_latencies_ms,
                    lexical_indexing_latency_ms,
                ),
            ):
                metrics = evaluate_retrieval(
                    questions,
                    rankings,
                    top_k=top_k,
                    retrieval_latencies_ms=latencies,
                )
                retrieval_results.append(
                    {
                        "retriever": retriever,
                        "embedding_model": (
                            settings.embedding_model
                            if retriever == "BGE dense"
                            else None
                        ),
                        "chunk_size": chunk_size,
                        "chunk_overlap": overlap,
                        "top_k": top_k,
                        "chunk_count": len(chunks),
                        "indexing_latency_ms": index_latency,
                        **metrics,
                    }
                )
        if chunk_size == ANSWER_CHUNK_SIZE and overlap == ANSWER_OVERLAP:
            answer_rankings = bge_rankings

    results: dict[str, Any] = {
        "benchmark": {
            "name": benchmark["name"],
            "version": benchmark["version"],
            "dataset_sha256": dataset_sha256(),
            "document_count": len(benchmark["documents"]),
            "question_count": len(questions),
            "all_content_fictional": True,
        },
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_revision": git_revision(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "embedding_model": settings.embedding_model,
            "sentence_transformers": package_version("sentence-transformers"),
            "torch": package_version("torch"),
            "chromadb": package_version("chromadb"),
        },
        "retrieval": retrieval_results,
        "answer_evaluation": None,
    }
    if with_llm:
        if answer_rankings is None:
            raise RuntimeError("Answer evaluation configuration was not generated.")
        results["answer_evaluation"] = evaluate_answers(questions, answer_rankings)
    return results


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_report(results: dict[str, Any]) -> str:
    benchmark = results["benchmark"]
    run = results["run"]
    rows = []
    for item in results["retrieval"]:
        rows.append(
            "| {retriever} | {chunk_size} | {chunk_overlap} | {top_k} | {chunk_count} | "
            "{recall} | {mrr} | {mean:.3f} | {p95:.3f} |".format(
                retriever=item["retriever"],
                chunk_size=item["chunk_size"],
                chunk_overlap=item["chunk_overlap"],
                top_k=item["top_k"],
                chunk_count=item["chunk_count"],
                recall=percent(item["recall_at_k"]),
                mrr=percent(item["mrr_at_k"]),
                mean=item["retrieval_latency_mean_ms"],
                p95=item["retrieval_latency_p95_ms"],
            )
        )

    answer = results.get("answer_evaluation")
    if answer:
        answer_section = f"""
## Grounded-answer results

The default project configuration (`chunk_size=1000`, `overlap=150`, `top_k=4`) was evaluated with `{answer['configuration']['llm_model']}`. Answer correctness is a transparent exact check that all annotated gold keywords appear after Unicode and whitespace normalization. Citation accuracy is macro-averaged citation precision: a citation is correct only when it points to the annotated gold document and page.

| Metric | Result |
| --- | ---: |
| Answer accuracy | {percent(answer['answer_accuracy'])} |
| Citation accuracy | {percent(answer['citation_accuracy'])} |
| Grounded-answer rate | {percent(answer['grounded_answer_rate'])} |
| Mean DeepSeek generation latency | {answer['generation_latency_mean_ms']:.1f} ms |
| P95 DeepSeek generation latency | {answer['generation_latency_p95_ms']:.1f} ms |
"""
    else:
        answer_section = """
## Grounded-answer results

This run is retrieval-only. Load `DEEPSEEK_API_KEY` and add `--with-llm` to reproduce answer correctness, citation accuracy and generation latency.
"""

    return f"""# StudyMate RAG quantitative evaluation

This report is generated by `scripts/evaluate_rag.py` from a fully fictional, public Chinese benchmark. It contains {benchmark['question_count']} questions over {benchmark['document_count']} PDFs. Every question has a gold document, page and answer-keyword set. Dataset SHA-256: `{benchmark['dataset_sha256']}`.

## Retrieval methodology

- Embedding model: `{run['embedding_model']}` with normalized vectors
- Relevance rule: a retrieved chunk is relevant only if both its document and page match the gold annotation
- Metrics: Recall@K, MRR@K, mean retrieval latency and P95 retrieval latency; BGE latency includes query embedding after a warm-up inference
- Comparison: BGE dense retrieval versus a transparent character 2/3-gram Jaccard baseline, across three character chunk sizes and three `top_k` values
- Environment: Python {run['python']}, sentence-transformers {run['sentence_transformers']}, torch {run['torch']}
- Measured at: `{run['generated_at']}` on `{run['platform']}`

## Retrieval results

| Retriever | Chunk size | Overlap | Top K | Chunks | Recall@K | MRR@K | Mean ms/query | P95 ms/query |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{os.linesep.join(rows)}
{answer_section}
## Reproduce

```bash
.venv/bin/python scripts/generate_evaluation_assets.py
.venv/bin/python scripts/evaluate_rag.py

# Also call DeepSeek for answer and citation metrics
set -a && source .env.local && set +a
.venv/bin/python scripts/evaluate_rag.py --with-llm
```

The machine-readable result, including per-question grounded-answer evidence, is stored in [`output/evaluation/evaluation-results.json`](../output/evaluation/evaluation-results.json).

## Limitations

- The benchmark is deliberately small and synthetic, so it measures reproducibility rather than production-domain generalization.
- Keyword correctness is deterministic and auditable, but it does not replace expert grading of nuanced free-form answers.
- DeepSeek output and latency can change across provider versions and network conditions; retrieval results are locally reproducible without an API key.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Call DeepSeek and compute answer/citation metrics.",
    )
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_benchmark(with_llm=args.with_llm)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.report.write_text(render_report(results), encoding="utf-8")
    print(args.output)
    print(args.report)


if __name__ == "__main__":
    main()
