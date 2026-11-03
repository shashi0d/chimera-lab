"""Shared test setup. Tests never call a paid model and never read the repo's .env (so they never reach the live
Supabase project): settings are built with _env_file=None and the services are the offline fakes."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import User, unauthorized
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
        evo_seed_on_start=False,
    )
    base.update(overrides)
    return Settings(**base)


class FakeAuth:
    """Accepts "user:<id>" bearer tokens (no keys, no network). Anything else is a failed sign-in."""

    configured = True

    async def verify(self, token: str) -> User:
        if token.startswith("user:") and len(token) > 5:
            return User(id=token[5:], email=f"{token[5:]}@example.test")
        raise unauthorized()


def auth(user: str = "user-1") -> dict[str, str]:
    return {"Authorization": f"Bearer user:{user}"}


def offline_services(settings: Settings, delay_scale: float = 0.0) -> Services:
    """The app's services with the deterministic fake models (local storage unless a test configures otherwise)."""
    from tests.fakes import MockImageGen, MockVision

    storage, db, local = build_storage(settings)
    return Services(settings, MockVision(delay_scale), MockImageGen(delay_scale), storage, db, local)


def offline_app(settings: Settings) -> Any:
    from app.agentapi.jobs import AgentDriver

    svc = offline_services(settings)
    app = create_app(settings, services=svc)
    app.state.agent.driver_factory = lambda: AgentDriver(svc, offline=True)
    app.state.auth = FakeAuth()
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
