from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from scripts.evaluate_rag import keywords_present, load_benchmark
from scripts.evaluate_real_course import load_manifest

ROOT_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT_DIR / "evaluation" / "benchmark.json"
PDF_DIR = ROOT_DIR / "output" / "pdf" / "evaluation"
REAL_BENCHMARK_PATH = ROOT_DIR / "evaluation" / "real_course_benchmark.json"
REAL_RESULT_PATH = ROOT_DIR / "output" / "evaluation" / "real-course-results.json"


def test_evaluation_benchmark_has_30_unique_questions_and_three_documents():
    benchmark = load_benchmark(BENCHMARK_PATH)

    assert len(benchmark["documents"]) == 3
    assert len(benchmark["questions"]) == 30
    assert len({question["id"] for question in benchmark["questions"]}) == 30


def test_gold_keywords_exist_on_annotated_pdf_pages():
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    page_text = {}
    for document in benchmark["documents"]:
        reader = PdfReader(PDF_DIR / document["filename"])
        assert len(reader.pages) == 4
        for page_number, page in enumerate(reader.pages, start=1):
            page_text[(document["filename"], page_number)] = page.extract_text() or ""

    for question in benchmark["questions"]:
        text = page_text[(question["gold_document"], question["gold_page"])]
        assert keywords_present(text, question["answer_keywords"]), question["id"]


def test_keyword_matching_normalizes_spacing_and_punctuation():
    answer = "默认值为 8.4GHz；只传输状态摘要。"

    assert keywords_present(answer, ["8.4 GHz", "状态摘要"])


def test_real_course_benchmark_is_anonymous_and_well_formed():
    benchmark = load_manifest(REAL_BENCHMARK_PATH)

    assert len(benchmark["documents"]) == 3
    assert len(benchmark["questions"]) == 15
    assert all(
        document["filename"].startswith("course-")
        for document in benchmark["documents"]
    )
    serialized = json.dumps(benchmark, ensure_ascii=False)
    assert "/Users/" not in serialized
    assert "junior_year_spring" not in serialized


def test_real_course_result_is_private_and_complete():
    result = json.loads(REAL_RESULT_PATH.read_text(encoding="utf-8"))

    assert result["benchmark"]["all_content_fictional"] is False
    assert result["benchmark"]["source_hashes_verified"] is True
    assert result["benchmark"]["source_page_counts_verified"] is True
    assert result["benchmark"]["gold_keywords_verified"] is True
    assert result["privacy"]["source_files_committed"] is False
    assert result["privacy"]["source_paths_in_output"] is False
    assert result["privacy"]["source_text_in_output"] is False
    assert result["privacy"]["external_llm_calls"] is False
    assert len(result["question_results"]) == 15
    serialized = json.dumps(result, ensure_ascii=False)
    assert "/Users/" not in serialized
    assert "junior_year_spring" not in serialized
