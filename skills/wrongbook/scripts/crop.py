#!/usr/bin/env python3
"""Crop a rectangular region from an image.

Used by the wrongbook skill when a wrong question contains visual content
(图片选择题、连线题、字母圈选、几何图等) that can't be expressed as plain
text. Claude estimates the bounding box of the question region in the
original exam-paper photo and calls this script to extract a small image
that gets embedded into the practice PDF.

Usage:
  # Pixel coordinates
  python3 crop.py <input> <output> --box x,y,w,h

  # Percentage coordinates (more robust to source image size variations)
  python3 crop.py <input> <output> --box x,y,w,h --pct
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[wrongbook.crop] Missing dependency: pillow", file=sys.stderr)
    print("Install with: pip3 install --user pillow", file=sys.stderr)
    sys.exit(1)


def parse_box(spec: str) -> tuple[float, float, float, float]:
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) != 4:
        raise ValueError(f"--box must be 'x,y,w,h', got {spec!r}")
    try:
        return tuple(float(p) for p in parts)  # type: ignore[return-value]
    except ValueError as e:
        raise ValueError(f"--box values must be numbers: {e}") from None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", type=Path, help="Source image path")
    ap.add_argument("output", type=Path, help="Output cropped image path")
    ap.add_argument("--box", required=True,
                    help="Bounding box as x,y,w,h (pixels by default; pass --pct for percentages)")
    ap.add_argument("--pct", action="store_true",
                    help="Treat --box values as percentages of source image size (0-100)")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"[wrongbook.crop] Input not found: {args.input}", file=sys.stderr)
        return 2

    x, y, w, h = parse_box(args.box)

    with Image.open(args.input) as im:
        iw, ih = im.size
        if args.pct:
            x = x * iw / 100
            y = y * ih / 100
            w = w * iw / 100
            h = h * ih / 100
        x, y, w, h = int(round(x)), int(round(y)), int(round(w)), int(round(h))

        # Clamp to image bounds so a slightly-off estimate still produces a valid crop.
        x = max(0, min(x, iw - 1))
        y = max(0, min(y, ih - 1))
        w = max(1, min(w, iw - x))
        h = max(1, min(h, ih - y))

        cropped = im.crop((x, y, x + w, y + h))
        # Composite RGBA onto white so the embedded PDF image has a sensible background.
        if cropped.mode == "RGBA":
            bg = Image.new("RGB", cropped.size, (255, 255, 255))
            bg.paste(cropped, mask=cropped.split()[3])
            cropped = bg

        args.output.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(args.output)

    print(f"[wrongbook.crop] {args.input} -> {args.output}  "
          f"box=({x},{y},{w},{h}) src={iw}x{ih}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
