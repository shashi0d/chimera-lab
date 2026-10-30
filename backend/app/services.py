"""Builds the adapter set from settings. Swap adapters here, nowhere else."""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.base import DbAdapter, ImageGenAdapter, StorageAdapter, VisionAdapter
from app.config import Settings
from app.data.loader import ChimeraData, load_data


@dataclass
class Services:
    settings: Settings
    vision: VisionAdapter
    image_gen: ImageGenAdapter
    storage: StorageAdapter
    db: DbAdapter
    data: ChimeraData
    local_backend: bool  # single-process store: orphaned runs can be interrupted at startup


def build_services(settings: Settings) -> Services:
    data = load_data(settings.resolved_data_path())
    if settings.chimera_mode == "real":
        from app.adapters.meta.client import MetaImageGen, MetaVision

        if not settings.meta_api_key:
            raise RuntimeError("CHIMERA_MODE=real needs META_API_KEY")
        vision: VisionAdapter = MetaVision(
            settings.meta_api_base_url, settings.meta_api_key, settings.meta_vision_model,
            timeout=settings.identify_timeout_seconds,
        )
        image_gen: ImageGenAdapter = MetaImageGen(
            settings.meta_api_base_url, settings.meta_api_key, settings.meta_image_model,
            timeout=settings.generate_timeout_seconds,
        )
    else:
        from app.adapters.mock import MockImageGen, MockVision

        vision = MockVision(settings.mock_delay_scale)
        image_gen = MockImageGen(settings.mock_delay_scale)

    if settings.supabase_url and settings.supabase_service_key:
        from app.adapters.supabase.adapters import SupabaseDb, SupabaseStorage

        storage: StorageAdapter = SupabaseStorage(
            settings.supabase_url, settings.supabase_service_key, settings.storage_bucket
        )
        db: DbAdapter = SupabaseDb(settings.supabase_url, settings.supabase_service_key)
        local = False
    else:
        from app.adapters.local.db import SqliteDb
        from app.adapters.local.storage import LocalStorage

        root = settings.resolved_local_dir()
        storage = LocalStorage(root / "files")
        db = SqliteDb(root / "chimera.sqlite3")
        local = True
    return Services(settings, vision, image_gen, storage, db, data, local)
