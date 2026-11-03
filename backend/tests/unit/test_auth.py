"""Supabase access-token verification (app/auth.py) with a locally generated ES256 key: no network."""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth import Auth
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from tests.conftest import make_settings

URL = "https://proj.supabase.co"
ISSUER = f"{URL}/auth/v1"


class Keys:
    """Stands in for PyJWKClient: one known signing key."""

    def __init__(self, key: Any) -> None:
        self.key = key

    def get_signing_key_from_jwt(self, token: str) -> Any:
        if jwt.get_unverified_header(token).get("kid") != "k1":
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return type("K", (), {"key": self.key})()


@pytest.fixture
def signer() -> Any:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def auth(tmp_path: Any, signer: Any) -> Auth:
    a = Auth(make_settings(tmp_path, supabase_url=URL, supabase_publishable_key="sb_publishable_x"))
    a._jwks = Keys(signer.public_key())  # type: ignore[assignment]
    return a


def token(signer: Any, kid: str = "k1", alg: str = "ES256", **claims: Any) -> str:
    now = int(time.time())
    body = {"sub": "user-123", "aud": "authenticated", "role": "authenticated", "iss": ISSUER,
            "email": "a@example.test", "iat": now, "exp": now + 600, **claims}
    return jwt.encode(body, signer, algorithm=alg, headers={"kid": kid})


async def refused(auth: Auth, tok: str) -> ChimeraError:
    with pytest.raises(ChimeraError) as e:
        await auth.verify(tok)
    assert e.value.code == ErrorCode.UNAUTHORIZED and e.value.status == 401
    return e.value


async def test_a_valid_token_gives_the_user(auth, signer):
    user = await auth.verify(token(signer))
    assert user.id == "user-123" and user.email == "a@example.test"


async def test_invalid_tokens_are_refused(auth, signer):
    other = ec.generate_private_key(ec.SECP256R1())
    err = await refused(auth, token(signer, exp=int(time.time()) - 10))
    assert "expired" in err.message
    await refused(auth, token(signer, aud="anon"))
    await refused(auth, token(signer, iss="https://evil.supabase.co/auth/v1"))
    await refused(auth, token(signer, role="anon"))
    await refused(auth, token(signer, is_anonymous=True))
    await refused(auth, token(other))  # signed by another key with the same kid
    await refused(auth, token(signer, kid="unknown"))
    await refused(auth, jwt.encode({"sub": "x", "aud": "authenticated", "iss": ISSUER, "exp": int(time.time()) + 60},
                                   "secret", algorithm="HS256", headers={"kid": "k1"}))
    await refused(auth, "not-a-jwt")


async def test_without_supabase_sign_in_is_not_configured(tmp_path):
    a = Auth(make_settings(tmp_path))
    assert a.configured is False
    err = await refused(a, "anything")
    assert "not configured" in err.message
