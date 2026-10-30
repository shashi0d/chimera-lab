"""Generates the fixture images used by mock mode, tests and screenshots.

Real photos can't be fetched in the build environment, so each fixture is a
painted "specimen card" in the hue the mock vision adapter maps to that animal
(see backend/app/adapters/mock/vision.py). Run: python scripts/make_fixture_images.py
"""

from __future__ import annotations

import colorsys
import io
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.adapters.mock.vision import MOCK_SPECIES  # noqa: E402

OUT = ROOT / "backend" / "tests" / "fixtures" / "images"
EDGE = OUT / "edge"


def rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def creature(hue: int, plan: str, seed: int, size: int = 900) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    # Soft habitat backdrop, low saturation so the animal's hue dominates.
    for y in range(size):
        t = y / size
        d.line([(0, y), (size, y)], fill=rgb(hue + 30, 0.10, 0.92 - 0.25 * t))
    d.rectangle([0, int(size * 0.72), size, size], fill=rgb(hue + 40, 0.14, 0.62))
    body = Image.new("L", (size, size), 0)
    bd = ImageDraw.Draw(body)
    s = size
    if plan == "avian":
        bd.ellipse([s * .32, s * .30, s * .66, s * .70], fill=255)
        bd.ellipse([s * .50, s * .16, s * .70, s * .36], fill=255)
        bd.polygon([(s * .68, s * .24), (s * .80, s * .28), (s * .68, s * .31)], fill=255)
        bd.polygon([(s * .34, s * .40), (s * .12, s * .62), (s * .40, s * .60)], fill=255)
        bd.line([(s * .46, s * .70), (s * .44, s * .86)], fill=255, width=int(s * .02))
        bd.line([(s * .54, s * .70), (s * .56, s * .86)], fill=255, width=int(s * .02))
    elif plan == "aquatic":
        bd.ellipse([s * .14, s * .36, s * .80, s * .60], fill=255)
        bd.polygon([(s * .78, s * .48), (s * .94, s * .34), (s * .90, s * .48), (s * .94, s * .62)], fill=255)
        bd.polygon([(s * .44, s * .38), (s * .52, s * .24), (s * .56, s * .40)], fill=255)
        bd.ellipse([s * .06, s * .44, s * .20, s * .52], fill=255)
    elif plan == "cephalopod":
        bd.ellipse([s * .34, s * .14, s * .66, s * .46], fill=255)
        for i in range(8):
            a = math.pi * (0.15 + 0.7 * i / 7)
            x0, y0 = s * .5, s * .42
            pts = [(x0 + math.cos(a) * s * r * .42 + math.sin(r * 9 + i) * s * .03, y0 + math.sin(a) * s * r * .42)
                   for r in [k / 12 for k in range(13)]]
            bd.line(pts, fill=255, width=int(s * .035))
    else:  # quadruped
        bd.ellipse([s * .22, s * .38, s * .70, s * .62], fill=255)
        bd.ellipse([s * .60, s * .26, s * .80, s * .46], fill=255)
        for x in (.28, .38, .56, .64):
            bd.rectangle([s * x, s * .55, s * (x + .05), s * .80], fill=255)
        bd.line([(s * .23, s * .45), (s * .10, s * .34)], fill=255, width=int(s * .03))
        bd.polygon([(s * .64, s * .30), (s * .66, s * .18), (s * .71, s * .28)], fill=255)
    body = body.filter(ImageFilter.GaussianBlur(3))
    fur = Image.new("RGB", (size, size))
    fd = ImageDraw.Draw(fur)
    for y in range(size):
        fd.line([(0, y), (size, y)], fill=rgb(hue + rnd.uniform(-6, 6), 0.78, 0.84 - 0.3 * (y / size)))
    if hue in (55,):  # tiger stripes
        for i in range(14):
            x = s * (.25 + i * .04)
            fd.line([(x, s * .30), (x + s * .02, s * .62)], fill=rgb(hue, 0.9, 0.18), width=int(s * .012))
    for _ in range(900):  # texture speckle
        x, y = rnd.randrange(size), rnd.randrange(size)
        fd.point((x, y), fill=rgb(hue + rnd.uniform(-10, 10), 0.6, rnd.uniform(.4, .95)))
    img.paste(fur, (0, 0), body)
    # Eye
    ex, ey = (s * .70, s * .34) if plan == "quadruped" else (s * .62, s * .24) if plan == "avian" else (s * .16, s * .46) if plan == "aquatic" else (s * .45, s * .28)
    d.ellipse([ex - s * .015, ey - s * .015, ex + s * .015, ey + s * .015], fill=(20, 20, 20))
    return img


def slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    EDGE.mkdir(parents=True, exist_ok=True)
    for i, (hue, common, _sci, plan, _parts) in enumerate(MOCK_SPECIES):
        creature(hue, plan, i).save(OUT / f"{slug(common)}.jpg", quality=88)

    lion = creature(40, "quadruped", 1)
    lion.resize((200, 160)).save(EDGE / "too_small.jpg", quality=85)
    lion.resize((3000, 3000)).save(EDGE / "huge_3000.png")
    good = io.BytesIO()
    lion.save(good, "JPEG")
    (EDGE / "corrupt.jpg").write_bytes(good.getvalue()[:400] + b"\x00" * 600)
    lion.resize((400, 400)).save(EDGE / "anim.gif")
    (EDGE / "doc.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    (EDGE / "vector.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')

    # EXIF: orientation 6 (rotate 90 CW on display) + a GPS block that must be stripped.
    tall = creature(25, "quadruped", 7).resize((600, 400))
    exif = Image.Exif()
    exif[0x0112] = 6
    exif[0x8825] = {1: "N", 2: (39.0, 10.0, 0.0), 3: "W", 4: (86.0, 31.0, 0.0)}
    tall.save(EDGE / "exif_rotated_gps.jpg", exif=exif, quality=88)

    try:
        from pillow_heif import from_pillow

        from_pillow(creature(320, "avian", 9).resize((512, 512))).save(EDGE / "flamingo.heic", quality=80)
    except Exception as exc:  # encoder may be missing
        print("HEIC fixture skipped:", exc)
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
