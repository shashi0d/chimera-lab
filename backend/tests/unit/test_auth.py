"""The visitor id (app/auth.py): a UUID from the X-Visitor-Id header; missing means signed out, malformed is a 401."""

from __future__ import annotations

import uuid

import pytest
from starlette.requests import Request

from app.auth import current_user, require_user
from app.errors import ChimeraError
from app.models.schemas import ErrorCode


def req(value: str | None) -> Request:
    headers = [] if value is None else [(b"x-visitor-id", value.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


async def test_a_uuid_header_is_the_visitor():
    vid = str(uuid.uuid4())
    user = await current_user(req(vid))
    assert user is not None and user.id == vid
    assert (await current_user(req(vid.upper()))).id == vid  # normalised


async def test_no_header_is_signed_out():
    assert await current_user(req(None)) is None
    assert await current_user(req("  ")) is None
    with pytest.raises(ChimeraError) as e:
        await require_user(req(None))
    assert e.value.code == ErrorCode.UNAUTHORIZED


async def test_a_malformed_id_is_refused():
    for bad in ("user-1", "not-a-uuid", "x" * 200):
        with pytest.raises(ChimeraError) as e:
            await current_user(req(bad))
        assert e.value.code == ErrorCode.UNAUTHORIZED and e.value.status == 401
