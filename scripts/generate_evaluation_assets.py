#!/usr/bin/env python3
"""Generate the public fictional PDFs used by the original and hard evaluation benchmarks."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT_DIR = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT_DIR / "evaluation" / "benchmark.json"
HARD_BENCHMARK_PATH = ROOT_DIR / "evaluation" / "hard_benchmark.json"
DEFAULT_PURPOSE = (
    "本资料与另外两份公开文档共同构成 30 题中文基准。每道题都标注标准文档、"
    "标准页码和答案关键词，用于计算 Recall@K、MRR、回答正确率和引用准确率。"
)
HARD_PURPOSE = (
    "本资料是加难评测版本：第 2 至 4 页与原评测资料完全相同，第 5 页加入名称相近、"
    "数值不同的设备和规程，用于检验换说法提问、相近概念干扰、边界条件和跨页综合。"
)
# Fixed timestamps and IDs so regenerating the PDFs does not change their bytes.
rl_config.invariant = 1
OUTPUT_DIR = ROOT_DIR / "output" / "pdf" / "evaluation"
FONT_NAME = "StudyMateEvaluationSans"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf"),
)


def register_font() -> None:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
            return
    raise RuntimeError("未找到可嵌入的中文字体。请安装 Noto Sans CJK。")


def load_benchmark() -> dict:
    with BENCHMARK_PATH.open(encoding="utf-8") as file:
        benchmark = json.load(file)
    if len(benchmark["questions"]) != 30:
        raise ValueError("公开评测集必须包含 30 道问题。")
    return benchmark


def draw_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 9)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(22 * mm, 14 * mm, "StudyMate RAG 公开虚构评测资料")
    canvas.drawRightString(188 * mm, 14 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def hard_documents(base: dict) -> list[dict]:
    """Compose each hard PDF from the unchanged base pages plus its confusable extra page."""
    with HARD_BENCHMARK_PATH.open(encoding="utf-8") as file:
        hard = json.load(file)
    by_name = {document["filename"]: document for document in base["documents"]}
    return [
        {
            **document,
            "pages": by_name[document["base_document"]]["pages"] + document["extra_pages"],
            "purpose": HARD_PURPOSE,
        }
        for document in hard["documents"]
    ]


def build_document(document_data: dict) -> Path:
    output_path = OUTPUT_DIR / document_data["filename"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=24 * mm,
        title=document_data["title"],
        author="StudyMate RAG Project",
        subject="A fictional public document for reproducible RAG evaluation",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "EvaluationTitle",
        parent=base["Title"],
        fontName=FONT_NAME,
        fontSize=24,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8 * mm,
    )
    subtitle = ParagraphStyle(
        "EvaluationSubtitle",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8 * mm,
    )
    heading = ParagraphStyle(
        "EvaluationHeading",
        parent=base["Heading1"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=26,
        textColor=colors.HexColor("#1D4ED8"),
        spaceAfter=5 * mm,
    )
    section = ParagraphStyle(
        "EvaluationSection",
        parent=base["Heading2"],
        fontName=FONT_NAME,
        fontSize=14,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "EvaluationBody",
        parent=base["BodyText"],
        fontName=FONT_NAME,
        fontSize=11,
        leading=19,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4 * mm,
    )
    note = ParagraphStyle(
        "EvaluationNote",
        parent=body,
        backColor=colors.HexColor("#EFF6FF"),
        borderColor=colors.HexColor("#93C5FD"),
        borderWidth=0.7,
        borderPadding=10,
        textColor=colors.HexColor("#1E3A8A"),
    )

    story = [
        Spacer(1, 30 * mm),
        Paragraph(document_data["title"], title),
        Paragraph(document_data["subtitle"], subtitle),
        Paragraph(
            "本文档中的名称、参数与流程均为虚构内容，只用于公开、可复现的 RAG "
            "检索和问答评测，不包含真实课程、个人信息或保密材料。",
            note,
        ),
        Spacer(1, 10 * mm),
        Paragraph("评测用途", heading),
        Paragraph(document_data.get("purpose", DEFAULT_PURPOSE), body),
    ]
    for page in document_data["pages"]:
        story.append(PageBreak())
        story.append(Paragraph(page["heading"], heading))
        for item in page["sections"]:
            story.append(Paragraph(item["title"], section))
            story.append(Paragraph(item["text"], body))

    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output_path


def main() -> None:
    register_font()
    benchmark = load_benchmark()
    documents = benchmark["documents"] + hard_documents(benchmark)
    outputs = [build_document(item) for item in documents]
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
