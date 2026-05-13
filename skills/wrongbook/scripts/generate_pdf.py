#!/usr/bin/env python3
"""Generate a minimal practice PDF from a wrong-question JSON file.

Input JSON schema (M1):
{
  "title": "数学错题练习 - 2026-05-11",
  "student": "（可选）",
  "questions": [
    {"id": 1, "subject": "数学", "type": "计算题",
     "content": "题干文本，可以多行。", "answer_lines": 3}
  ]
}

Usage:
  python3 generate_pdf.py <input.json> <output.pdf>
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Flowable, KeepTogether,
        Image as RLImage,
    )
except ImportError as e:
    print(f"[wrongbook] Missing dependency: {e.name}", file=sys.stderr)
    print("Install with: pip3 install --user reportlab pillow", file=sys.stderr)
    sys.exit(1)


# Candidate CJK fonts with full Unicode coverage (path, registered_name, subfont_index).
# Tried in order; first one that loads wins. Falls back to STSong-Light CID (limited glyphs).
_FONT_CANDIDATES = {
    "Darwin": [
        ("/System/Library/Fonts/PingFang.ttc", "PingFang", 0),
        ("/System/Library/Fonts/STHeiti Medium.ttc", "STHeiti", 0),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", "HiraginoSansGB", 0),
        ("/Library/Fonts/Songti.ttc", "Songti", 0),
    ],
    "Linux": [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WenQuanYiMicroHei", 0),
        ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "WenQuanYiZenHei", 0),
    ],
    "Windows": [
        ("C:/Windows/Fonts/msyh.ttc", "MicrosoftYaHei", 0),
        ("C:/Windows/Fonts/simhei.ttf", "SimHei", None),
        ("C:/Windows/Fonts/simsun.ttc", "SimSun", 0),
    ],
}


def _register_cjk_font() -> str:
    candidates = _FONT_CANDIDATES.get(platform.system(), [])
    for path, name, idx in candidates:
        if not Path(path).exists():
            continue
        try:
            kwargs = {"subfontIndex": idx} if idx is not None else {}
            pdfmetrics.registerFont(TTFont(name, path, **kwargs))
            return name
        except Exception as e:
            print(f"[wrongbook] Failed to load {path}: {e}", file=sys.stderr)
    fallback = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    print(f"[wrongbook] Warning: no system CJK TTF found, fell back to {fallback} "
          f"(some symbols like '·' '÷' may render incorrectly)", file=sys.stderr)
    return fallback


CJK_FONT = _register_cjk_font()


class AnswerLines(Flowable):
    """N evenly spaced horizontal rules for handwritten answers."""

    def __init__(self, n: int, width: float, line_gap: float = 9 * mm,
                 color=HexColor("#BBBBBB")):
        super().__init__()
        self.n = max(1, int(n))
        self.width = width
        self.line_gap = line_gap
        self.color = color
        self.height = self.n * self.line_gap

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(0.4)
        for i in range(1, self.n + 1):
            y = self.height - i * self.line_gap + 1 * mm
            c.line(0, y, self.width, y)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "wb_title", parent=base["Title"], fontName=CJK_FONT,
            fontSize=18, leading=24, spaceAfter=4 * mm,
        ),
        "meta": ParagraphStyle(
            "wb_meta", parent=base["Normal"], fontName=CJK_FONT,
            fontSize=10, leading=14, textColor=HexColor("#666666"),
            spaceAfter=6 * mm,
        ),
        "chapter": ParagraphStyle(
            "wb_chapter", parent=base["Heading2"], fontName=CJK_FONT,
            fontSize=14, leading=20, textColor=HexColor("#333333"),
            spaceBefore=4 * mm, spaceAfter=3 * mm,
        ),
        "qhead": ParagraphStyle(
            "wb_qhead", parent=base["Normal"], fontName=CJK_FONT,
            fontSize=11, leading=15, textColor=HexColor("#888888"),
            spaceAfter=1 * mm,
        ),
        "qbody": ParagraphStyle(
            "wb_qbody", parent=base["Normal"], fontName=CJK_FONT,
            fontSize=12, leading=18, textColor=black, spaceAfter=2 * mm,
        ),
    }


def _scaled_image(path: str, max_width: float, max_height: float) -> RLImage | None:
    """Load `path` as a reportlab Image, scaled to fit within max_width × max_height
    while preserving aspect ratio. Returns None if the file is missing or unreadable."""
    p = Path(path)
    if not p.exists():
        print(f"[wrongbook] Warning: image_path not found: {path}", file=sys.stderr)
        return None
    try:
        from PIL import Image as PILImage
        with PILImage.open(p) as im:
            iw, ih = im.size
    except Exception as e:
        print(f"[wrongbook] Warning: cannot read image {path}: {e}", file=sys.stderr)
        return None
    scale = min(max_width / iw, max_height / ih, 1.0)
    return RLImage(str(p), width=iw * scale, height=ih * scale)


def _question_block(q: dict, idx_fallback: int, styles: dict, content_width: float,
                    show_subject_in_head: bool = True):
    qid = q.get("id", idx_fallback)
    qtype = q.get("type") or ""
    subject = q.get("subject") or ""
    content = (q.get("content") or "").replace("\n", "<br/>")
    answer_lines = int(q.get("answer_lines", 3))
    image_path = q.get("image_path")

    head_bits = []
    if show_subject_in_head and subject:
        head_bits.append(subject)
    if qtype:
        head_bits.append(qtype)
    head_text = " · ".join(head_bits)

    flowables = []
    if head_text:
        flowables.append(Paragraph(f"【{head_text}】", styles["qhead"]))
    flowables.append(Paragraph(f"<b>{qid}.</b> {content}", styles["qbody"]))
    if image_path:
        img = _scaled_image(image_path, max_width=content_width, max_height=80 * mm)
        if img is not None:
            flowables.append(Spacer(1, 2 * mm))
            flowables.append(img)
            flowables.append(Spacer(1, 2 * mm))
    flowables.append(AnswerLines(answer_lines, content_width))
    flowables.append(Spacer(1, 6 * mm))
    return KeepTogether(flowables)


def _chapter_heading(subject: str, styles: dict) -> Paragraph:
    return Paragraph(f"——  {subject}  ——", styles["chapter"])


def _make_footer(doc_title: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(CJK_FONT, 9)
        canvas.setFillColor(HexColor("#999999"))
        canvas.drawString(18 * mm, 8 * mm, doc_title)
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"第 {doc.page} 页")
        canvas.restoreState()
    return draw


def build_pdf(data: dict, out_path: Path) -> None:
    page_size = A4
    margin = 18 * mm
    title = data.get("title") or "错题练习"
    doc = SimpleDocTemplate(
        str(out_path), pagesize=page_size,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin + 6 * mm,  # leave room for footer
        title=title,
    )
    content_width = page_size[0] - 2 * margin
    styles = _styles()

    story = []
    story.append(Paragraph(title, styles["title"]))

    meta_bits = []
    if data.get("student"):
        meta_bits.append(f"学生：{data['student']}")
    meta_bits.append("姓名：__________   日期：__________")
    story.append(Paragraph("　　".join(meta_bits), styles["meta"]))

    questions = data.get("questions") or []
    if not questions:
        story.append(Paragraph("（无错题）", styles["qbody"]))
    else:
        # Group by subject only when more than one unique subject is present.
        unique_subjects = {(q.get("subject") or "") for q in questions}
        group_by_subject = len(unique_subjects) > 1
        current_subject = None
        for i, q in enumerate(questions, start=1):
            subj = q.get("subject") or ""
            if group_by_subject and subj != current_subject:
                story.append(_chapter_heading(subj or "未分类", styles))
                current_subject = subj
            story.append(_question_block(
                q, i, styles, content_width,
                show_subject_in_head=not group_by_subject,
            ))

    footer = _make_footer(title)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate practice PDF from wrong-question JSON.")
    ap.add_argument("input", type=Path, help="Input JSON file")
    ap.add_argument("output", type=Path, help="Output PDF file")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"[wrongbook] Input not found: {args.input}", file=sys.stderr)
        return 2

    data = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(data, args.output)
    print(f"[wrongbook] Wrote: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
