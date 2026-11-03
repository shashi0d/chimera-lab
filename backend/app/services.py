"""Builds the adapter set from settings. Swap adapters here, nowhere else.

The app is live-only: the vision and image models are always Meta's. Storage is Supabase when SUPABASE_URL and
the secret key are set, else local SQLite and files (development on one machine)."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.base import DbAdapter, ImageGenAdapter, StorageAdapter, VisionAdapter
from app.config import Settings


@dataclass
class Services:
    settings: Settings
    vision: VisionAdapter
    image_gen: ImageGenAdapter
    storage: StorageAdapter
    db: DbAdapter
    local_backend: bool  # single-process store: orphaned runs can be interrupted at startup


def build_storage(settings: Settings) -> tuple[StorageAdapter, DbAdapter, bool]:
    if settings.supabase_url and settings.supabase_service_key:
        from app.adapters.supabase.adapters import SupabaseDb, SupabaseStorage

        storage: StorageAdapter = SupabaseStorage(settings.supabase_url, settings.supabase_service_key,
                                                  settings.storage_bucket)
        return storage, SupabaseDb(settings.supabase_url, settings.supabase_service_key), False
    from app.adapters.local.db import SqliteDb
    from app.adapters.local.storage import LocalStorage

    root = settings.resolved_local_dir()
    return LocalStorage(root / "files"), SqliteDb(root / "chimera.sqlite3"), True


def build_services(settings: Settings) -> Services:
    from app.adapters.meta.client import MetaImageGen, MetaVision

    if not settings.meta_api_key:
        raise RuntimeError("Chimera Lab needs META_API_KEY")
    vision = MetaVision(settings.meta_api_base_url, settings.meta_api_key, settings.meta_vision_model,
                        timeout=max(settings.identify_timeout_seconds, settings.plan_timeout_seconds))
    image_gen = MetaImageGen(settings.meta_api_base_url, settings.meta_api_key, settings.meta_image_model,
                             timeout=settings.generate_timeout_seconds)
    storage, db, local = build_storage(settings)
    return Services(settings, vision, image_gen, storage, db, local)
