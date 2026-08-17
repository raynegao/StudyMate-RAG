from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from scripts.evaluate_rag import keywords_present, load_benchmark

ROOT_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT_DIR / "evaluation" / "benchmark.json"
PDF_DIR = ROOT_DIR / "output" / "pdf" / "evaluation"


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
