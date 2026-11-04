"""Env-driven settings. The app is live-only; every knob lives here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "1.0.0"


class Settings(BaseSettings):
    # The repo-root .env, wherever the server is started from. Tests pass _env_file=None so they never read it.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Meta API: Muse Image draws every image; Muse Spark reads images (identify, topic check, profile).
    meta_api_base_url: str = "https://api.meta.ai/v1"
    meta_api_key: str | None = None
    meta_vision_model: str = "muse-spark-1.3"
    meta_image_model: str = "muse-image-1.0"

    supabase_url: str | None = None
    # Server-side key (bypasses RLS). Supabase now calls it the secret key (sb_secret_...); the legacy name still works.
    supabase_service_key: str | None = Field(
        default=None, validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY", "supabase_service_key"))
    # Browser-safe key: the frontend signs in with it (served by GET /evo/config). Row level security keeps it from
    # reading or writing any table.
    supabase_publishable_key: str | None = None
    storage_bucket: str = "chimera-assets"
    evo_public_bucket: str = "chimera-public"  # generated images, public read

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    local_data_dir: str = ".localdata"  # local SQLite and files when Supabase is not configured
    frontend_dist: str = "frontend/dist"  # served at / when it exists
    evo_proxy_hops: int = Field(default=1, ge=0)  # trusted proxies in front of the app (X-Forwarded-For)

    # Model calls: per-attempt timeouts (about 2x the slowest live latency seen) and retries (tests shrink these).
    retry_base_seconds: float = 1.0
    retry_max_attempts: int = 3
    identify_timeout_seconds: float = 20.0
    vision_timeout_seconds: float = 60.0
    generate_timeout_seconds: float = 80.0

    # Fusion: one image from EVO_FUSION_PROMPT ({a} and {b} are the parents' names), in the chosen art style.
    evo_fusion_prompt: str = "create a hybrid of {a} and {b}"
    # Every generated image (Fusion and edits) is asked for this background. Empty: no background rule.
    evo_fusion_background: str = ("Show the whole creature, centred, on a plain pure white background with no "
                                  "scenery.")
    evo_identify_min_confidence: float = 0.6  # a photo read below this asks the user to confirm the animal
    evo_max_upload_bytes: int = 8 * 1024 * 1024
    evo_identify_max_side: int = 1024  # uploads are resized to this before any model call

    # Runs: in-process jobs with a heartbeat lease (D-016), a concurrency limit with a queue, and a hard time cap.
    evo_max_concurrent_runs: int = Field(default=3, ge=1)  # more are queued
    evo_run_hard_seconds: float = 900.0
    evo_keepalive_seconds: float = 15.0  # SSE ": ping"
    evo_poll_seconds: float = 1.0  # SSE re-read of a run that lives in another process
    evo_heartbeat_seconds: float = 10.0
    run_lease_seconds: float = 180.0

    # Limits. Off (the default): no daily caps and no per-minute rate limits; usage is still counted.
    evo_limits_enabled: bool = False
    evo_daily_runs: int = 50  # Fusion runs per day, all users
    evo_visitor_daily_runs: int = 3  # Fusion runs per user per day
    evo_runs_per_minute_per_ip: int = 5
    lab_daily_actions: int = Field(default=100, ge=1)  # edits and cards per day, all users
    lab_user_daily_actions: int = Field(default=20, ge=1)
    lab_actions_per_minute_per_ip: int = Field(default=10, ge=1)

    # The Lab: edits and cards share a model pool; a job with no update for this long reads as interrupted.
    lab_max_concurrent_actions: int = Field(default=2, ge=1)
    lab_job_stale_seconds: float = Field(default=1800.0, gt=0)
    lab_workspace_max_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)  # one saved canvas

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def resolved_local_dir(self) -> Path:
        p = Path(self.local_data_dir)
        return p if p.is_absolute() else REPO_ROOT / p

    @staticmethod
    def repo_path(value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def get_settings() -> Settings:
    return Settings()
