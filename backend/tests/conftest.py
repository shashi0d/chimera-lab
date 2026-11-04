"""Shared test setup. Tests never call a paid model and never read the repo's .env (so they never reach the live
Supabase project): settings are built with _env_file=None and the services are the offline fakes."""

from __future__ import annotations

import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.main import create_app
from app.services import Services, build_storage

FIXTURES = Path(__file__).parent / "fixtures"
IMAGES = FIXTURES / "images"
EDGE = IMAGES / "edge"


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base: dict[str, Any] = dict(
        _env_file=None,
        local_data_dir=str(tmp_path / "local"),
        retry_base_seconds=0.001,
        frontend_dist=str(tmp_path / "no-frontend"),  # tests that serve a frontend build their own dist
        evo_limits_enabled=True,  # the cap tests run with limits on (the app's default is off)
    )
    base.update(overrides)
    return Settings(**base)


def visitor_id(user: str = "user-1") -> str:
    """A stable visitor UUID for a test user name."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chimera-test:{user}"))


def auth(user: str = "user-1") -> dict[str, str]:
    return {"X-Visitor-Id": visitor_id(user)}


SIGNED_OUT = {"X-Visitor-Id": ""}


def offline_services(settings: Settings, delay_scale: float = 0.0) -> Services:
    """The app's services with the deterministic fake models (local storage unless a test configures otherwise)."""
    from tests.fakes import MockImageGen, MockVision

    storage, db, local = build_storage(settings)
    return Services(settings, MockVision(delay_scale), MockImageGen(delay_scale), storage, db, local)


def offline_app(settings: Settings) -> Any:
    from app.agentapi.jobs import PromptDriver

    svc = offline_services(settings)
    app = create_app(settings, services=svc)
    app.state.agent.driver_factory = lambda: PromptDriver(svc)
    return app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = offline_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=auth()
    ) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c
