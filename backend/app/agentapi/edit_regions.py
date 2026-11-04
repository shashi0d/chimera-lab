"""Pixel work around the image model for the Lab's region edits (Paint, Draw). Pure functions on PNG/JPEG bytes.

The model (Muse Image) has no mask parameter: it always returns a whole new image. These helpers decide where that
new image is used and where the original is kept, the way inpainting tools do it:

- `change_mask`: the area to take from the model. A creator's brush is only a rough hint (a painted wing never
  covers every pixel of the old wing, and the new wing never has the old one's outline), so the area is where the
  model's output really differs from the original, inside a margin around the brush, plus the brush itself.
  Compositing only inside the brush leaves scraps of the old part and cuts the new one off at the brush edge.
- `blend`: the original with the model's pixels inside that area, feathered across the edge (both sides) so no
  seam shows.
- `drift`: how much the model changed *outside* the area. A model that redrew or moved the whole creature cannot be
  blended (the seam would show); the caller then keeps the model's whole image instead.
- `crop_box` / `crop` / `paste`: crop-and-stitch for small areas. A pair of eyes is a few percent of the image; at
  full-image scale the model gives it almost no detail. The area is cut out with context around it, enlarged to the
  model's size, edited, and pasted back.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter, ImageOps

Box = tuple[int, int, int, int]


def load_rgb(data: bytes, size: tuple[int, int] | None = None) -> Image.Image:
    with Image.open(io.BytesIO(data)) as im:
        rgb = im.convert("RGB")
    return rgb.resize(size, Image.Resampling.LANCZOS) if size and rgb.size != size else rgb


def alpha_of(layer: bytes, size: tuple[int, int]) -> Image.Image:
    """The drawn/painted pixels of a transparent PNG layer, as an L mask (255 = drawn) at `size`."""
    with Image.open(io.BytesIO(layer)) as im:
        a = im.convert("RGBA").getchannel("A")
    return a.resize(size, Image.Resampling.NEAREST).point(lambda v: 255 if v > 0 else 0)


def png(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


def _px(size: tuple[int, int], fraction: float) -> int:
    return max(1, round(min(size) * fraction))


def grow(mask: Image.Image, fraction: float) -> Image.Image:
    """Dilate a mask by `fraction` of the image's short side (a max filter, applied in steps to stay fast)."""
    radius = _px(mask.size, fraction)
    small = mask.resize((max(1, mask.width // 4), max(1, mask.height // 4)), Image.Resampling.BILINEAR)
    r = max(1, radius // 4)
    while r > 0:
        k = min(r, 12)
        small = small.filter(ImageFilter.MaxFilter(2 * k + 1))
        r -= k
    return small.resize(mask.size, Image.Resampling.BILINEAR).point(lambda v: 255 if v > 40 else 0)


def difference(a: Image.Image, b: Image.Image) -> Image.Image:
    """Per-pixel change between two same-size images (L, 0..255), lightly blurred so noise and resampling don't count."""
    d = ImageChops.difference(a, b).convert("L").filter(ImageFilter.GaussianBlur(2))
    return d.point(lambda v: 255 if v > 28 else 0)


def change_mask(original: Image.Image, edited: Image.Image, hint: Image.Image, margin: float) -> Image.Image:
    """Where to take the model's pixels: the hint (brush or strokes) plus what really changed within `margin`
    of it. Small specks of change are dropped; holes are closed."""
    reach = grow(hint, margin)
    changed = ImageChops.multiply(difference(original, edited), reach)
    # Grow, don't erode: thin new parts (horn tips, spikes, whiskers) must come across whole, and their soft edges
    # (anti-aliasing, shading) with them. Specks can only appear within the reach of the brush anyway.
    changed = changed.filter(ImageFilter.MaxFilter(9))
    return ImageChops.lighter(changed, hint)


def drift(original: Image.Image, edited: Image.Image, area: Image.Image, margin: float) -> float:
    """Share of pixels that changed *outside* the edit area (and its margin): 0 = untouched, 1 = all redrawn."""
    outside = ImageOps.invert(grow(area, margin))
    d = ImageChops.multiply(difference(original, edited), outside)
    total = outside.histogram()[255] or 1
    return d.histogram()[255] / total


def blend(original: Image.Image, edited: Image.Image, area: Image.Image, feather: float = 0.012) -> Image.Image:
    """The original with `edited` inside `area`, feathered across its edge."""
    r = _px(original.size, feather)
    soft = grow(area, feather / 2).filter(ImageFilter.GaussianBlur(r))
    return Image.composite(edited, original, soft)


# ------------------------------------------------------------------ crop-and-stitch


@dataclass(frozen=True)
class Crop:
    box: Box  # in original pixels, square

    @property
    def side(self) -> int:
        return self.box[2] - self.box[0]


def crop_box(area: Image.Image, context: float = 1.0, min_side: float = 0.28) -> Crop | None:
    """A square around `area` with `context` times its size again around it, at least `min_side` of the image.
    None when the area is already large (more than about half the image): edit the whole image then."""
    bbox = area.getbbox()
    if not bbox:
        return None
    w, h = area.size
    x0, y0, x1, y1 = bbox
    side = max(x1 - x0, y1 - y0)
    side = max(round(side * (1 + context)), round(min(w, h) * min_side))
    if side >= min(w, h) * 0.55:
        return None
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    left = min(max(0, cx - side // 2), w - side)
    top = min(max(0, cy - side // 2), h - side)
    return Crop((left, top, left + side, top + side))


def crop(im: Image.Image, c: Crop, size: int = 1024) -> Image.Image:
    return im.crop(c.box).resize((size, size), Image.Resampling.LANCZOS)


def paste(original: Image.Image, edited_crop: Image.Image, c: Crop) -> Image.Image:
    """The edited crop, scaled back, placed into a copy of the original (blend afterwards decides what is kept)."""
    out = original.copy()
    out.paste(edited_crop.resize((c.side, c.side), Image.Resampling.LANCZOS), c.box[:2])
    return out


# ------------------------------------------------------------------ guides shown to the model


def highlight(im: Image.Image, area: Image.Image, colour: tuple[int, int, int] = (255, 0, 200)) -> Image.Image:
    """The image with `area` tinted and outlined: shows the model where to work."""
    base = im.convert("RGBA")
    tint = Image.new("RGBA", base.size, (*colour, 0))
    tint.putalpha(area.point(lambda v: 110 if v else 0))
    edge = area.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
    line = Image.new("RGBA", base.size, (*colour, 255))
    line.putalpha(edge)
    return Image.alpha_composite(Image.alpha_composite(base, tint), line).convert("RGB")


def overlay(im: Image.Image, layer: bytes) -> Image.Image:
    """The creator's drawing (a transparent PNG) over the image."""
    with Image.open(io.BytesIO(layer)) as lay:
        top = lay.convert("RGBA").resize(im.size)
    return Image.alpha_composite(im.convert("RGBA"), top).convert("RGB")


# ------------------------------------------------------------------ did the model draw the marks themselves?


def leftover_colour(result: Image.Image, area: Image.Image, colour: tuple[int, int, int]) -> float:
    """Share of `area` whose pixels are still (near) the highlight colour."""
    target = Image.new("RGB", result.size, colour)
    near = ImageChops.difference(result, target).convert("L").point(lambda v: 255 if v < 70 else 0)
    hit = ImageChops.multiply(near, area).histogram()[255]
    return hit / (area.histogram()[255] or 1)


def leftover_strokes(original: Image.Image, guide: Image.Image, result: Image.Image, strokes: Image.Image) -> float:
    """Share of the stroke pixels where the result looks like the drawn line (close to the guide's colour there)
    while the original was clearly different: the model copied the lines instead of turning them into anatomy."""
    like_line = ImageChops.difference(result, guide).convert("L").point(lambda v: 255 if v < 40 else 0)
    was_other = ImageChops.difference(original, guide).convert("L").point(lambda v: 255 if v > 90 else 0)
    hits = ImageChops.multiply(ImageChops.multiply(like_line, was_other), strokes).histogram()[255]
    return hits / (ImageChops.multiply(was_other, strokes).histogram()[255] or 1)
