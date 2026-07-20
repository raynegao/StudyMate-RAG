from pathlib import Path

from pypdf import PdfReader


DEMO_PDF = Path("output/pdf/studymate-demo-course.pdf")


def test_public_demo_pdf_is_readable_and_contains_expected_facts():
    reader = PdfReader(DEMO_PDF)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) == 3
    assert "蓝色令牌" in text
    assert "三个星港周期" in text
    assert "0.72" in text
    assert "虚构" in text
