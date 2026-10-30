"""Env-driven settings. Every knob in TASKSHEET Section 13 lives here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    chimera_mode: Literal["mock", "real"] = "mock"

    meta_api_base_url: str = "https://api.meta.ai/v1"
    meta_api_key: str | None = None
    meta_vision_model: str = "muse-spark-1.3"  # L1-02, verified via GET /v1/models
    meta_image_model: str = "muse-image-1.0"

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    storage_bucket: str = "chimera-assets"

    data_path: str = "data/chimera_data.json"

    # Spend guard (fixed point 0.2-3)
    max_generations_per_run: int = 2
    max_vision_calls_per_run: int = 4
    daily_generation_cap: int = 200
    # L1-04: token caps (all models, every attempt). Generous defaults; the call caps above bind first.
    max_tokens_per_run: int = 200_000
    daily_token_cap: int = 5_000_000

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Local adapters
    local_data_dir: str = ".localdata"

    # Limits
    max_upload_bytes: int = 20 * 1024 * 1024
    min_short_side: int = 256
    runs_per_minute_per_session: int = 10

    # Timing (tests shrink these)
    retry_base_seconds: float = 1.0
    retry_max_attempts: int = 3
    # L1-05: per-attempt timeouts, about 2x the slowest live latency seen (docs/LIVE_LOG.md, 2026-10-30):
    # describe max 9.0s -> 20s; plan max 24.1s (two pinned attempts exceeded 30s) -> 60s;
    # generate max 37.1s (text-to-image 23.7s) -> 80s.
    identify_timeout_seconds: float = 20.0
    plan_timeout_seconds: float = 60.0
    generate_timeout_seconds: float = 80.0
    run_lease_seconds: float = 180.0
    mock_delay_scale: float = Field(default=1.0, ge=0)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_data_path(self) -> Path:
        p = Path(self.data_path)
        return p if p.is_absolute() else REPO_ROOT / p

    def resolved_local_dir(self) -> Path:
        p = Path(self.local_data_dir)
        return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
