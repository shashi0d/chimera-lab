"""Upload normalisation: sniff the real type, convert HEIC, apply EXIF
orientation, strip all metadata (GPS included), enforce size limits."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import ChimeraError
from app.models.schemas import ErrorCode

try:  # HEIC/HEIF support (TASKSHEET 7.1)
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_OK = True
except Exception:  # pragma: no cover - only if the wheel is missing
    HEIF_OK = False

MAX_EDGE = 2048
ACCEPTED_HINT = "JPEG, PNG, WebP or HEIC"
HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heif", b"avif"}


@dataclass
class Normalised:
    data: bytes
    content_type: str
    width: int
    height: int
    sha256: str


def sniff(head: bytes) -> str | None:
    if head[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp" and head[8:12] in HEIF_BRANDS:
        return "avif" if head[8:12] == b"avif" else "heif"
    return None


def normalise(raw: bytes, *, min_short_side: int) -> Normalised:
    kind = sniff(raw[:16])
    if kind is None or kind == "avif":
        raise ChimeraError(ErrorCode.UNSUPPORTED_FILE, f"This file type isn't supported. Use {ACCEPTED_HINT}.",
                           details={"accepted": ["image/jpeg", "image/png", "image/webp", "image/heic"]})
    if kind == "heif" and not HEIF_OK:
        raise ChimeraError(ErrorCode.UNSUPPORTED_FILE, "HEIC images can't be converted right now. Use JPEG or PNG.")
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            im = ImageOps.exif_transpose(im) or im
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            im = im.convert("RGBA" if has_alpha else "RGB")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        if kind == "heif":
            raise ChimeraError(ErrorCode.UNSUPPORTED_FILE, "This HEIC image couldn't be converted. Export it as JPEG.") from exc
        raise ChimeraError(ErrorCode.IMAGE_CORRUPT, "This image is damaged and can't be read.") from exc
    if min(im.size) < min_short_side:
        raise ChimeraError(
            ErrorCode.IMAGE_TOO_SMALL,
            f"This image is too small. The short side must be at least {min_short_side}px.",
            details={"width": im.size[0], "height": im.size[1], "minShortSide": min_short_side},
        )
    if max(im.size) > MAX_EDGE:
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    if has_alpha:
        im.save(out, "PNG", optimize=True)
        content_type = "image/png"
    else:
        im.save(out, "JPEG", quality=92, optimize=True)  # no exif= argument: metadata is dropped
        content_type = "image/jpeg"
    data = out.getvalue()
    return Normalised(data, content_type, im.size[0], im.size[1], hashlib.sha256(data).hexdigest())
