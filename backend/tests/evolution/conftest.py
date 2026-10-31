from __future__ import annotations

from pathlib import Path

import pytest

from app.evolution.data import taxonomy
from app.evolution.engine import EvoEngine
from app.services import build_services
from tests.conftest import make_settings


@pytest.fixture
def engine(tmp_path: Path) -> EvoEngine:
    return EvoEngine(build_services(make_settings(tmp_path)))


@pytest.fixture
def tax():
    return taxonomy()


def plan_for(engine: EvoEngine, sire: str, dam: str, myth: bool = False, seed: int = 0, **kw):
    """Seed plan through 4.1 to 4.5 with no model call (the code path /fuse uses before rendering)."""
    s, d = engine.tax.resolve(sire), engine.tax.resolve(dam)
    g, r = engine.seed_plan(s, d, myth=myth, seed=seed, **kw)
    return engine.finish(g, r), r
