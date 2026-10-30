from __future__ import annotations

import re

from fastapi import Request

from app.adapters.base import MOCK_FAULTS
from app.pipeline.runner import RunManager
from app.services import Services

SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def runs(request: Request) -> RunManager:
    return request.app.state.runs  # type: ignore[no-any-return]


def session_id(request: Request) -> str:
    sid = request.headers.get("x-session-id", "")
    return sid if SESSION_RE.match(sid) else "anonymous"


def mock_fault(request: Request) -> str | None:
    """X-Mock-Fault is honoured only in mock mode."""
    if request.app.state.services.settings.chimera_mode != "mock":
        return None
    fault = request.headers.get("x-mock-fault")
    return fault if fault in MOCK_FAULTS else None
