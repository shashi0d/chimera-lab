"""Quantizes QA screenshots to 256-color PNGs (about 3x smaller, fine for review evidence).
Usage: python scripts/shrink_shots.py docs/visual-qa/<round>"""
import sys
from pathlib import Path

from PIL import Image

total_before = total_after = 0
for p in Path(sys.argv[1]).rglob("*.png"):
    before = p.stat().st_size
    with Image.open(p) as im:
        if im.mode == "P":
            continue
        q = im.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q.save(p, optimize=True)
    total_before += before
    total_after += p.stat().st_size
print(f"{total_before / 1e6:.1f} MB -> {total_after / 1e6:.1f} MB")
