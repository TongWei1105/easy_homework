#!/usr/bin/env python3
"""Generate a synthetic exam paper image with red teacher marks for testing.

Output: examples/mock_exam.png

Not part of the user-facing skill — only used during development to validate
the end-to-end pipeline without a real exam photo.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 1700  # roughly A4 at ~150 DPI
MARGIN = 80
BLACK = (20, 20, 20)
GRAY = (90, 90, 90)
RED = (210, 30, 30)
BLUE = (30, 60, 180)
WHITE = (255, 255, 255)

CJK_FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(CJK_FONT_PATH, size, index=0)


def draw_x(draw: ImageDraw.ImageDraw, x: int, y: int, size: int = 36, color=RED, width: int = 5):
    h = size // 2
    draw.line([(x - h, y - h), (x + h, y + h)], fill=color, width=width)
    draw.line([(x - h, y + h), (x + h, y - h)], fill=color, width=width)


def draw_circle(draw: ImageDraw.ImageDraw, x: int, y: int, rx: int, ry: int, color=RED, width: int = 4):
    draw.ellipse([(x - rx, y - ry), (x + rx, y + ry)], outline=color, width=width)


def draw_strike(draw: ImageDraw.ImageDraw, x1: int, y: int, x2: int, color=RED, width: int = 3):
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def main():
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Header
    d.text((W // 2 - 280, MARGIN), "五年级数学单元测试", font=font(40), fill=BLACK)
    d.text((MARGIN, MARGIN + 70), "姓名：小明        日期：2026.05.10        得分：__ / 100",
           font=font(22), fill=GRAY)
    d.line([(MARGIN, MARGIN + 110), (W - MARGIN, MARGIN + 110)], fill=GRAY, width=1)

    y = MARGIN + 150
    line_h = 36

    def put(text, x_off=0, color=BLACK, size=26, dy=None):
        nonlocal y
        d.text((MARGIN + x_off, y), text, font=font(size), fill=color)
        if dy is None:
            y += line_h
        else:
            y += dy

    # Q1 - wrong (red X on answer)
    put("一、计算题（每题 5 分）", color=GRAY, size=22, dy=50)
    put("1. 计算：3/4 + 5/6 = ", dy=8)
    # student answer in blue, then red X
    d.text((MARGIN + 280, y - line_h - 8), "7/10", font=font(28), fill=BLUE)
    draw_x(d, MARGIN + 360, y - line_h + 6, size=44)
    d.text((MARGIN + 420, y - line_h - 4), "-5", font=font(26), fill=RED)
    y += 50

    # Q2 - correct (no mark)
    put("2. 计算：1.25 × 8 = ", dy=8)
    d.text((MARGIN + 280, y - line_h - 8), "10", font=font(28), fill=BLUE)
    y += 50

    # Q3 - wrong (red circle around answer)
    put("3. 计算：2.4 ÷ 0.6 = ", dy=8)
    d.text((MARGIN + 280, y - line_h - 8), "0.4", font=font(28), fill=BLUE)
    draw_circle(d, MARGIN + 305, y - line_h + 8, rx=42, ry=24)
    d.text((MARGIN + 380, y - line_h - 4), "-5", font=font(26), fill=RED)
    y += 60

    # Q4 - wrong (red strike + score deduction)
    put("二、应用题（每题 10 分）", color=GRAY, size=22, dy=50)
    put("4. 小明有 24 颗糖，平均分给 4 个小朋友，", dy=line_h)
    put("   每人分得几颗？如果再来 2 个小朋友", dy=line_h)
    put("   一起平分，每人分得几颗？", dy=8)
    # student wrote answer
    sa_y = y
    d.text((MARGIN + 40, sa_y), "解：24 ÷ 4 = 6（颗）", font=font(24), fill=BLUE)
    d.text((MARGIN + 40, sa_y + 36), "  24 ÷ 6 = 5（颗）", font=font(24), fill=BLUE)
    d.text((MARGIN + 40, sa_y + 72), "答：每人 6 颗，再来 2 人后每人 5 颗。", font=font(24), fill=BLUE)
    # red strike on the second line (wrong: should be 4+2=6 ÷ 24, etc.)
    draw_strike(d, MARGIN + 50, sa_y + 50, MARGIN + 360, width=3)
    d.text((MARGIN + 700, sa_y + 30), "✗ -6", font=font(30), fill=RED)
    y = sa_y + 130

    # Q5 - wrong (multiple choice, red X on chosen wrong option)
    put("三、选择题（每题 4 分）", color=GRAY, size=22, dy=50)
    put("5. 下列哪个数最大？", dy=line_h)
    put("   A. 0.5      B. 1/3      C. 0.55      D. 0.499", dy=8)
    # student selected A
    d.text((MARGIN + 50, y), "答：A", font=font(26), fill=BLUE)
    draw_x(d, MARGIN + 130, y + 14, size=34)
    d.text((MARGIN + 200, y - 4), "-4", font=font(26), fill=RED)
    y += 60

    # Q6 - correct (no mark)
    put("6. 下列哪个分数与 1/2 相等？", dy=line_h)
    put("   A. 2/3      B. 3/6      C. 4/9      D. 5/12", dy=8)
    d.text((MARGIN + 50, y), "答：B", font=font(26), fill=BLUE)
    y += 60

    # Total score in red
    d.text((W - MARGIN - 200, MARGIN + 70), "得分：80", font=font(28), fill=RED)

    out = Path(__file__).parent / "mock_exam.png"
    img.save(out, "PNG")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
