#!/usr/bin/env python3
"""Generate the public PDF used by the StudyMate demonstration."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / "output" / "pdf" / "studymate-demo-course.pdf"
FONT_NAME = "StudyMateDemoSans"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf"),
)


def register_demo_font() -> None:
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
            return
    raise RuntimeError(
        "未找到可嵌入的中文字体。请安装 Noto Sans CJK，或在脚本中增加字体路径。"
    )


def draw_page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 9)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(22 * mm, 14 * mm, "StudyMate 公开演示资料")
    canvas.drawRightString(188 * mm, 14 * mm, f"第 {document.page} 页")
    canvas.restoreState()


def build_demo_pdf(output_path: Path = OUTPUT_PATH) -> Path:
    register_demo_font()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=24 * mm,
        title="星港算法基础 - StudyMate 公开演示资料",
        author="StudyMate RAG Project",
        subject="A fictional course handout for reproducible RAG demonstrations",
    )

    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "ChineseTitle",
        parent=base["Title"],
        fontName=FONT_NAME,
        fontSize=24,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=10 * mm,
    )
    subtitle = ParagraphStyle(
        "ChineseSubtitle",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=8 * mm,
    )
    heading = ParagraphStyle(
        "ChineseHeading",
        parent=base["Heading1"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=26,
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=4 * mm,
        spaceAfter=4 * mm,
    )
    subheading = ParagraphStyle(
        "ChineseSubheading",
        parent=base["Heading2"],
        fontName=FONT_NAME,
        fontSize=14,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "ChineseBody",
        parent=base["BodyText"],
        fontName=FONT_NAME,
        fontSize=11,
        leading=19,
        textColor=colors.HexColor("#334155"),
        spaceAfter=3 * mm,
    )
    note = ParagraphStyle(
        "ChineseNote",
        parent=body,
        backColor=colors.HexColor("#EFF6FF"),
        borderColor=colors.HexColor("#93C5FD"),
        borderWidth=0.7,
        borderPadding=8,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=4 * mm,
        spaceAfter=4 * mm,
    )

    story = [
        Spacer(1, 18 * mm),
        Paragraph("星港算法基础", title),
        Paragraph("StudyMate RAG 公开演示课程资料", subtitle),
        Paragraph(
            "这是一份完全虚构、可公开使用的课程讲义，用于验证 PDF 解析、中文文件名、"
            "向量检索、基于资料的回答以及页码引用。资料不包含真实课程、个人信息或保密内容。",
            note,
        ),
        Spacer(1, 5 * mm),
        Paragraph("学习目标", heading),
        Paragraph("完成本讲义后，学习者应能够：", body),
        Paragraph("1. 说明蓝色令牌的用途和有效期。", body),
        Paragraph("2. 解释锚点窗口如何确认一组连续观测。", body),
        Paragraph("3. 使用回声阈值判断信号是否可以进入稳定队列。", body),
        Spacer(1, 8 * mm),
        Paragraph("演示建议问题", heading),
        Paragraph("蓝色令牌的有效期是多少？它有什么用途？", note),
        PageBreak(),
        Paragraph("1. 三个核心概念", heading),
        Paragraph("1.1 蓝色令牌", subheading),
        Paragraph(
            "蓝色令牌用于标记已经通过双重校验的观测记录。每枚蓝色令牌的有效期固定为"
            "三个星港周期；超过三个周期后必须重新校验。令牌只能附着在原始记录上，不能转移给其他记录。",
            body,
        ),
        Paragraph("1.2 锚点窗口", subheading),
        Paragraph(
            "锚点窗口由连续五次观测组成。只有当五次观测的方向一致，且时间间隔均不超过"
            "十二秒时，窗口才被视为有效。任意一次观测缺失都会使窗口重新计数。",
            body,
        ),
        Paragraph("1.3 回声阈值", subheading),
        Paragraph(
            "回声分数的取值范围为 0 到 1。系统使用 0.72 作为稳定阈值：分数大于或等于"
            "0.72 的记录进入稳定队列，低于 0.72 的记录进入人工复核队列。",
            body,
        ),
        Spacer(1, 6 * mm),
        Table(
            [
                ["概念", "关键参数", "结果"],
                ["蓝色令牌", "3 个星港周期", "到期后重新校验"],
                ["锚点窗口", "连续 5 次观测", "方向一致且间隔不超过 12 秒"],
                ["回声阈值", "0.72", "达到阈值后进入稳定队列"],
            ],
            colWidths=[38 * mm, 45 * mm, 72 * mm],
            style=TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("LEADING", (0, 0), (-1, -1), 16),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
        PageBreak(),
        Paragraph("2. 判断流程与练习", heading),
        Paragraph("判断一条观测能否进入稳定队列时，按以下顺序执行：", body),
        Paragraph("1. 检查记录是否持有仍在有效期内的蓝色令牌。", body),
        Paragraph("2. 检查它是否属于一个有效的锚点窗口。", body),
        Paragraph("3. 检查回声分数是否大于或等于 0.72。", body),
        Paragraph(
            "三个条件必须同时满足。蓝色令牌本身不能替代锚点窗口，也不能降低回声阈值。",
            note,
        ),
        Paragraph("练习", heading),
        Paragraph(
            "某记录的蓝色令牌已经使用两个星港周期，所在窗口包含五次方向一致的观测，"
            "最大时间间隔为十秒，回声分数为 0.76。该记录满足三个条件，可以进入稳定队列。",
            body,
        ),
        Paragraph(
            "如果同一记录的回声分数改为 0.68，即使令牌和窗口都有效，也必须进入人工复核队列。",
            body,
        ),
        Spacer(1, 8 * mm),
        Paragraph("资料边界", heading),
        Paragraph(
            "本讲义中的星港周期、蓝色令牌、锚点窗口和回声阈值均为虚构概念，仅用于软件演示。",
            body,
        ),
    ]

    document.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
    return output_path


if __name__ == "__main__":
    print(build_demo_pdf())
