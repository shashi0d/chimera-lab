"""Who is asking: a per-browser visitor id. The browser makes a random UUID once, keeps it in localStorage and
sends it on every request as `X-Visitor-Id`. That id owns the visitor's runs, lab versions and workspaces, and
counts against the per-visitor daily caps (the total cap and the per-IP rate limit bound everything else).

There is no sign-in: a random UUID is unguessable, so it works as the visitor's key for a demo."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Request

from app.errors import ChimeraError
from app.models.schemas import ErrorCode

HEADER = "x-visitor-id"


@dataclass(frozen=True)
class User:
    id: str
    email: str | None = None


def unauthorized(message: str = "Reload the page to start a session.") -> ChimeraError:
    return ChimeraError(ErrorCode.UNAUTHORIZED, message, retryable=False)


async def current_user(request: Request) -> User | None:
    """The visitor, or None when the request carries no id. A malformed id is an error (401), never anonymous."""
    raw = request.headers.get(HEADER, "").strip()
    if not raw:
        return None
    try:
        visitor = uuid.UUID(raw)
    except ValueError as exc:
        raise unauthorized() from exc
    return User(id=str(visitor))


async def require_user(request: Request) -> User:
    user = await current_user(request)
    if user is None:
        raise unauthorized()
    return user
