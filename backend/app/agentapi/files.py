"""Public files: generated images (renders, edits, anatomy overlays), readable by anyone, written only by the backend.

Local storage serves them at /evo/files/<key>. With Supabase they go to a public bucket (EVO_PUBLIC_BUCKET, created by
migration 001_agent_api.sql) and the URL is the bucket's public object URL; writes use the service key.
"""

from __future__ import annotations

import asyncio
import io
import logging
import mimetypes
from typing import Any

from PIL import Image

from app.adapters.base import StorageAdapter
from app.config import Settings

log = logging.getLogger(__name__)

CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def content_type_for(key: str) -> str:
    for ext, ct in CONTENT_TYPES.items():
        if key.lower().endswith(ext):
            return ct
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def to_jpeg(data: bytes, max_side: int = 1024, quality: int = 85) -> bytes:
    """Gallery-sized JPEG (overlays and S5 images are large PNG/WebP)."""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


class PublicFiles:
    def __init__(self, storage: StorageAdapter, url_base: str, local: bool) -> None:
        self.storage, self.url_base, self.local = storage, url_base.rstrip("/"), local

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        await self.storage.put(key, data, content_type or content_type_for(key))
        return self.url(key)

    async def put_jpeg(self, key: str, data: bytes, max_side: int = 1024) -> str:
        jpg = await asyncio.to_thread(to_jpeg, data, max_side)
        return await self.put(key, jpg, "image/jpeg")

    async def get(self, key: str) -> bytes:
        return await self.storage.get(key)

    def url(self, key: str) -> str:
        return f"{self.url_base}/{key}"

    def key_of(self, url: str) -> str | None:
        """The storage key of one of our public URLs (None for anything else)."""
        base = f"{self.url_base}/"
        return url[len(base):] if isinstance(url, str) and url.startswith(base) else None

    async def delete(self, key: str) -> None:
        """Remove a file; a file that is already gone is not an error."""
        try:
            await self.storage.delete(key)
        except Exception:  # noqa: BLE001 - a missing file or a storage hiccup must not block deleting the record
            log.warning("could not delete file %s", key, exc_info=True)


def build_public_files(settings: Settings) -> PublicFiles:
    if settings.supabase_url and settings.supabase_service_key:
        from app.adapters.supabase.adapters import SupabaseStorage

        storage: Any = SupabaseStorage(settings.supabase_url, settings.supabase_service_key, settings.evo_public_bucket)
        base = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{settings.evo_public_bucket}"
        return PublicFiles(storage, base, local=False)
    from app.adapters.local.storage import LocalStorage

    return PublicFiles(LocalStorage(settings.resolved_local_dir() / "public"), "/evo/files", local=True)
