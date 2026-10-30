"""Tiles screenshots into labelled 2x2 contact sheets for review: python scripts/contact_sheets.py <dir> <out>"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
files = sorted(src.glob("*.png"))
for i in range(0, len(files), 4):
    sheet = Image.new("RGB", (1440, 930), "white")
    d = ImageDraw.Draw(sheet)
    for j, f in enumerate(files[i:i + 4]):
        im = Image.open(f).convert("RGB")
        im.thumbnail((720, 450))
        x, y = (j % 2) * 720, (j // 2) * 465
        sheet.paste(im, (x, y + 15))
        d.text((x + 4, y + 2), f.stem, fill="black")
    sheet.save(out / f"sheet-{i // 4:02d}.png")
print(len(files), "->", (len(files) + 3) // 4, "sheets")
