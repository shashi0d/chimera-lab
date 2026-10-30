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
    meta_vision_model: str = "muse-spark"  # placeholder until P7-02
    meta_image_model: str = "muse-image"  # placeholder until P7-02

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    storage_bucket: str = "chimera-assets"

    data_path: str = "data/chimera_data.json"

    # Spend guard (fixed point 0.2-3)
    max_generations_per_run: int = 2
    max_vision_calls_per_run: int = 4
    daily_generation_cap: int = 200

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
    identify_timeout_seconds: float = 30.0
    generate_timeout_seconds: float = 120.0
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
