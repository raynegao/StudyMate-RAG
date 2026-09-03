#!/usr/bin/env python3
"""Evaluate anonymous real-course PDFs without committing or sending source content."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.chunking import DocumentChunk, split_pages_into_chunks  # noqa: E402
from app.services.pdf_parser import extract_pdf_pages  # noqa: E402
from scripts.evaluate_rag import (  # noqa: E402
    character_ngrams,
    document_id,
    embed_texts,
    evaluate_retrieval,
    git_revision,
    is_relevant,
    keywords_present,
    lexical_rank_chunks,
    package_version,
    rank_chunks,
)

BENCHMARK_PATH = ROOT_DIR / "evaluation" / "real_course_benchmark.json"
SOURCE_MAP_PATH = ROOT_DIR / "evaluation" / "private" / "real-course-sources.json"
RESULT_PATH = ROOT_DIR / "output" / "evaluation" / "real-course-results.json"
REPORT_PATH = ROOT_DIR / "docs" / "real-course-evaluation.md"
EXPERIMENTS = ((300, 60), (600, 100), (1000, 150))
TOP_K_VALUES = (1, 3, 5)
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path = BENCHMARK_PATH) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    documents = manifest.get("documents") or []
    questions = manifest.get("questions") or []
    aliases = {document.get("filename") for document in documents}

    if len(documents) != 3:
        raise ValueError(f"Expected 3 anonymous documents, found {len(documents)}.")
    if len(questions) != 15:
        raise ValueError(f"Expected 15 questions, found {len(questions)}.")
    if len(aliases) != len(documents) or None in aliases:
        raise ValueError("Anonymous document aliases must be unique and non-empty.")
    if len({question.get("id") for question in questions}) != len(questions):
        raise ValueError("Question IDs must be unique.")

    for document in documents:
        alias = document["filename"]
        if not alias.startswith("course-") or not alias.endswith(".pdf"):
            raise ValueError(f"Invalid anonymous document alias: {alias}")
        digest = document.get("sha256", "")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"Invalid SHA-256 for {alias}.")
        if int(document.get("page_count", 0)) <= 0:
            raise ValueError(f"Invalid page count for {alias}.")

    for question in questions:
        if question.get("gold_document") not in aliases:
            raise ValueError(f"Unknown gold document for {question.get('id')}.")
        if int(question.get("gold_page", 0)) <= 0:
            raise ValueError(f"Invalid gold page for {question.get('id')}.")
        if not question.get("answer_keywords"):
            raise ValueError(f"Missing answer keywords for {question.get('id')}.")
    return manifest


def load_source_map(path: Path, aliases: set[str]) -> dict[str, Path]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing private source map: {path}. Copy "
            "evaluation/real_course_sources.example.json and keep it under "
            "evaluation/private/."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if set(raw) != aliases:
        raise ValueError("Private source map aliases must exactly match the manifest.")
    sources = {alias: Path(source_path).expanduser() for alias, source_path in raw.items()}
    missing = [alias for alias, source in sources.items() if not source.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing source PDFs for aliases: {', '.join(missing)}")
    return sources


def validate_sources(
    manifest: dict[str, Any], sources: dict[str, Path]
) -> dict[str, dict[int, str]]:
    page_text: dict[str, dict[int, str]] = {}
    for document in manifest["documents"]:
        alias = document["filename"]
        source = sources[alias]
        if sha256_file(source) != document["sha256"]:
            raise ValueError(f"Source hash mismatch for {alias}.")

        reader = PdfReader(source)
        if len(reader.pages) != document["page_count"]:
            raise ValueError(f"Page count mismatch for {alias}.")
        page_text[alias] = {
            index: (page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        }

    for question in manifest["questions"]:
        text = page_text[question["gold_document"]][question["gold_page"]]
        if not keywords_present(text, question["answer_keywords"]):
            raise ValueError(f"Gold keywords not found for {question['id']}.")
    return page_text


def build_chunks(
    manifest: dict[str, Any],
    sources: dict[str, Path],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for document in manifest["documents"]:
        alias = document["filename"]
        pages = extract_pdf_pages(sources[alias])
        chunks.extend(
            split_pages_into_chunks(
                pages,
                document_id=document_id(alias),
                filename=alias,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks


def run_benchmark(manifest_path: Path, source_map_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    aliases = {document["filename"] for document in manifest["documents"]}
    sources = load_source_map(source_map_path, aliases)
    validate_sources(manifest, sources)
    questions = manifest["questions"]

    embed_texts(["StudyMate anonymous real-course benchmark warmup"])
    query_embeddings = []
    query_embedding_latencies_ms = []
    for question in questions:
        started = time.perf_counter()
        query_embeddings.append(embed_texts([question["question"]])[0])
        query_embedding_latencies_ms.append((time.perf_counter() - started) * 1000)

    retrieval_results = []
    question_results = []
    for chunk_size, overlap in EXPERIMENTS:
        chunks = build_chunks(
            manifest,
            sources,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )
        index_started = time.perf_counter()
        chunk_embeddings = embed_texts([chunk.text for chunk in chunks])
        indexing_latency_ms = (time.perf_counter() - index_started) * 1000

        bge_rankings = {}
        bge_latencies = []
        for question, query_embedding, embedding_latency_ms in zip(
            questions,
            query_embeddings,
            query_embedding_latencies_ms,
        ):
            started = time.perf_counter()
            bge_rankings[question["id"]] = rank_chunks(
                chunks, chunk_embeddings, query_embedding
            )
            bge_latencies.append(
                embedding_latency_ms + (time.perf_counter() - started) * 1000
            )

        lexical_index_started = time.perf_counter()
        chunk_ngrams = [character_ngrams(chunk.text) for chunk in chunks]
        lexical_indexing_latency_ms = (
            time.perf_counter() - lexical_index_started
        ) * 1000
        lexical_rankings = {}
        lexical_latencies = []
        for question in questions:
            started = time.perf_counter()
            lexical_rankings[question["id"]] = lexical_rank_chunks(
                chunks, chunk_ngrams, question["question"]
            )
            lexical_latencies.append((time.perf_counter() - started) * 1000)

        for top_k in TOP_K_VALUES:
            for retriever, rankings, latencies, index_latency in (
                ("BGE dense", bge_rankings, bge_latencies, indexing_latency_ms),
                (
                    "character n-gram",
                    lexical_rankings,
                    lexical_latencies,
                    lexical_indexing_latency_ms,
                ),
            ):
                retrieval_results.append(
                    {
                        "retriever": retriever,
                        "embedding_model": (
                            settings.embedding_model if retriever == "BGE dense" else None
                        ),
                        "chunk_size": chunk_size,
                        "chunk_overlap": overlap,
                        "top_k": top_k,
                        "chunk_count": len(chunks),
                        "indexing_latency_ms": index_latency,
                        **evaluate_retrieval(
                            questions,
                            rankings,
                            top_k=top_k,
                            retrieval_latencies_ms=latencies,
                        ),
                    }
                )

        if chunk_size == DEFAULT_CHUNK_SIZE and overlap == DEFAULT_CHUNK_OVERLAP:
            for question in questions:
                top_chunk = bge_rankings[question["id"]][0][0]
                question_results.append(
                    {
                        "id": question["id"],
                        "gold_document": question["gold_document"],
                        "gold_page": question["gold_page"],
                        "retrieved_document": top_chunk.filename,
                        "retrieved_page": top_chunk.page_number,
                        "top1_relevant": is_relevant(top_chunk, question),
                    }
                )

    return {
        "benchmark": {
            "name": manifest["name"],
            "version": manifest["version"],
            "manifest_sha256": sha256_file(manifest_path),
            "document_count": len(manifest["documents"]),
            "question_count": len(questions),
            "all_content_fictional": False,
            "source_hashes_verified": True,
            "source_page_counts_verified": True,
            "gold_keywords_verified": True,
        },
        "privacy": {
            **manifest["privacy"],
            "source_paths_in_output": False,
            "source_text_in_output": False,
            "external_llm_calls": False,
        },
        "run": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_revision": git_revision(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "embedding_model": settings.embedding_model,
            "sentence_transformers": package_version("sentence-transformers"),
            "torch": package_version("torch"),
        },
        "retrieval": retrieval_results,
        "question_results": question_results,
    }


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_report(results: dict[str, Any]) -> str:
    rows = []
    for item in results["retrieval"]:
        rows.append(
            "| {retriever} | {chunk_size} | {chunk_overlap} | {top_k} | "
            "{chunk_count} | {recall} | {mrr} | {mean:.3f} | {p95:.3f} |".format(
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

    default_top1 = next(
        item
        for item in results["retrieval"]
        if item["retriever"] == "BGE dense"
        and item["chunk_size"] == DEFAULT_CHUNK_SIZE
        and item["top_k"] == 1
    )
    return f"""# Anonymous real-course evaluation

This evaluation uses {results['benchmark']['question_count']} paraphrased Chinese questions over {results['benchmark']['document_count']} real university course PDFs. The PDFs, original filenames, local paths, institution names, instructor names and student data are not committed. Only anonymous aliases, integrity hashes, page-level labels and minimal answer keywords are public.

## Privacy boundary

- Source PDFs remain local and Git-ignored.
- The evaluator verifies source SHA-256 values, page counts and gold keywords before running.
- Only local BGE embeddings are used; no source text or question is sent to an external LLM.
- Results contain anonymous aliases and page numbers, never local paths or source text.

## Default result

- BGE Recall@1: {percent(default_top1['recall_at_k'])}
- BGE MRR@1: {percent(default_top1['mrr_at_k'])}
- Mean retrieval latency: {default_top1['retrieval_latency_mean_ms']:.3f} ms
- P95 retrieval latency: {default_top1['retrieval_latency_p95_ms']:.3f} ms

## Retrieval results

| Retriever | Chunk size | Overlap | Top K | Chunks | Recall@K | MRR@K | Mean ms/query | P95 ms/query |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{os.linesep.join(rows)}

## Reproduce locally

1. Copy `evaluation/real_course_sources.example.json` to the Git-ignored path `evaluation/private/real-course-sources.json`.
2. Map each anonymous alias to the corresponding local PDF.
3. Run `.venv/bin/python scripts/evaluate_real_course.py`.

Machine-readable results are stored in `output/evaluation/real-course-results.json`.

## Limitations

- The benchmark contains one real course domain and 15 questions, so it measures a more realistic retrieval slice rather than broad academic generalization.
- Source PDFs cannot be redistributed, so third parties need their own authorized local documents to reproduce the workflow.
- Keyword and page labels were manually checked; they are not expert-scored free-form answer labels.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH)
    parser.add_argument("--sources", type=Path, default=SOURCE_MAP_PATH)
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_benchmark(args.benchmark, args.sources)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.report.write_text(render_report(results), encoding="utf-8")
    print(args.output)
    print(args.report)


if __name__ == "__main__":
    main()
