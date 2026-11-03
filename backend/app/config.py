"""Env-driven settings. The app is live-only; every knob lives here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_VERSION = "0.1.0"


class Settings(BaseSettings):
    # The repo-root .env, wherever the server is started from. Tests pass _env_file=None so they never read it.
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    meta_api_base_url: str = "https://api.meta.ai/v1"
    meta_api_key: str | None = None
    meta_vision_model: str = "muse-spark-1.3"  # L1-02, verified via GET /v1/models
    meta_image_model: str = "muse-image-1.0"

    # S1: Muse Spark Open on Baseten (OpenAI-compatible chat completions). Probe only: no route uses it yet.
    baseten_base_url: str = "https://inference.baseten.co/v1"
    baseten_api_key: str | None = Field(default=None, validation_alias="BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26")
    baseten_spark_model: str = "meta-models/muse-spark-open-1026"
    # S1 live: Spark Open reasons before answering (2.4k reasoning tokens for a short traits answer); a ~9k-char
    # plan prompt did not finish inside the Meta plan timeout of 60 s on any of 8 attempts. Per-attempt limit:
    baseten_timeout_seconds: float = 300.0

    supabase_url: str | None = None
    # Server-side key (bypasses RLS). Supabase now calls it the secret key (sb_secret_...); the legacy name still works.
    supabase_service_key: str | None = Field(
        default=None, validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY", "supabase_service_key"))
    # Browser-safe key: the frontend signs in with it (served by GET /evo/config). Row level security keeps it from
    # reading or writing any table.
    supabase_publishable_key: str | None = None
    storage_bucket: str = "chimera-assets"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Local adapters
    local_data_dir: str = ".localdata"
    # E4: learned-animal cache. None: data/learned_animals.json.
    evo_learned_path: str | None = None
    gbif_timeout_seconds: float = 10.0

    # Timing (tests shrink these)
    retry_base_seconds: float = 1.0
    retry_max_attempts: int = 3
    # L1-05: per-attempt timeouts, about 2x the slowest live latency seen (docs/LIVE_LOG.md, 2026-10-30):
    # describe max 9.0s -> 20s; plan max 24.1s (two pinned attempts exceeded 30s) -> 60s;
    # generate max 37.1s (text-to-image 23.7s) -> 80s.
    identify_timeout_seconds: float = 20.0
    plan_timeout_seconds: float = 60.0
    generate_timeout_seconds: float = 80.0
    sam_timeout_seconds: float = 60.0
    cite_timeout_seconds: float = 240.0  # S2: web-cited traits (search and open pages); one probe call took 12.8 s  # E2: SAM 3.1 segmentation, no live latency measured yet
    run_lease_seconds: float = 180.0

    # R1: the public agent API (docs/api_contract.md "Caps"). Env names are the upper-case field names.
    evo_daily_runs: int = 50  # agent runs per day, all visitors
    evo_visitor_daily_runs: int = 3  # agent runs per signed-in user per day
    evo_max_concurrent_runs: int = Field(default=3, ge=1)  # more are queued
    evo_runs_per_minute_per_ip: int = 5  # POST /evo/agent/runs
    # Lab actions (revise, paint, review, collaborator messages) on generated images. Each is one action.
    lab_daily_actions: int = Field(default=100, ge=1)  # all users
    lab_user_daily_actions: int = Field(default=20, ge=1)
    lab_actions_per_minute_per_ip: int = Field(default=10, ge=1)
    # Lab model work has its own pool, in addition to the agent runner's evo_max_concurrent_runs.
    lab_max_concurrent_actions: int = Field(default=2, ge=1)
    # A queued or running lab job with no update for this long is reported as interrupted (its process stopped).
    # Longer than any one stage can take: a Spark Open call with retries is at most ~15 minutes.
    lab_job_stale_seconds: float = Field(default=1800.0, gt=0)
    lab_workspace_max_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)  # the saved canvas document
    evo_run_soft_seconds: float = 840.0  # the agent finalizes its best image here (cap_reached scope time)
    evo_run_hard_seconds: float = 900.0  # the runner stops the run here
    evo_choice_seconds: float = 120.0  # host-tie choice wait
    evo_keepalive_seconds: float = 15.0  # SSE ": ping"
    evo_poll_seconds: float = 1.0  # SSE re-read of a run that lives in another process
    evo_heartbeat_seconds: float = 10.0  # live runs refresh updatedAt (the lease, D-016)
    evo_showcase: str = "b09,b01,b03,b08,b11,b05"  # S5 case ids (or crt_ creature ids), in gallery order
    evo_showcase_dir: str = "docs/evolution/live/s5"  # S5 outputs: <case>/agent/
    evo_identify_min_confidence: float = 0.6  # below this the POST returns needs_choice
    evo_max_upload_bytes: int = 8 * 1024 * 1024
    evo_identify_max_side: int = 1024  # uploads are resized to this before any model call
    evo_public_bucket: str = "chimera-public"  # Supabase: generated images, public read
    evo_proxy_hops: int = Field(default=1, ge=0)  # trusted proxies in front of the app (X-Forwarded-For)
    frontend_dist: str = "frontend/dist"  # served at / when it exists
    evo_seed_on_start: bool = True  # seed the showcase in the background at startup (else on first gallery read)

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

    @property
    def showcase_list(self) -> list[str]:
        return [s.strip() for s in self.evo_showcase.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
