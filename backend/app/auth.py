"""Sign-in with Supabase Auth. The browser signs in (magic link) and sends `Authorization: Bearer <access token>`;
the backend verifies the token locally against the project's published signing keys (JWKS) and takes the user id
(`sub`) as the owner of runs, lab versions, the workspace and the daily caps.

No network call per request: the signing keys are fetched once and cached (re-fetched when an unknown key id
appears, i.e. after a key rotation)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Request

from app.config import Settings
from app.errors import ChimeraError
from app.models.schemas import ErrorCode

log = logging.getLogger(__name__)
ALGORITHMS = ["ES256", "RS256"]  # Supabase asymmetric signing keys
AUDIENCE = "authenticated"


@dataclass(frozen=True)
class User:
    id: str
    email: str | None = None


def unauthorized(message: str = "Sign in to continue.") -> ChimeraError:
    return ChimeraError(ErrorCode.UNAUTHORIZED, message, retryable=False)


class Auth:
    """Verifies Supabase access tokens. Tests replace `verify` with a fake (no keys, no network)."""

    def __init__(self, settings: Settings) -> None:
        self.url = (settings.supabase_url or "").rstrip("/")
        self.issuer = f"{self.url}/auth/v1"
        self._jwks: jwt.PyJWKClient | None = None
        if self.url:
            # The JWKS endpoint is public; the publishable key is sent as the gateway asks for one.
            headers = {"apikey": settings.supabase_publishable_key} if settings.supabase_publishable_key else {}
            self._jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=3600,
                                         headers=headers, timeout=10)

    @property
    def configured(self) -> bool:
        return self._jwks is not None

    async def verify(self, token: str) -> User:
        if self._jwks is None:
            raise unauthorized("Sign-in is not configured on this server.")
        jwks = self._jwks
        try:
            key = await asyncio.to_thread(jwks.get_signing_key_from_jwt, token)
            claims: dict[str, Any] = jwt.decode(token, key.key, algorithms=ALGORITHMS, audience=AUDIENCE,
                                                issuer=self.issuer, options={"require": ["exp", "sub"]})
        except jwt.ExpiredSignatureError as exc:
            raise unauthorized("Your sign-in expired. Sign in again.") from exc
        except (jwt.PyJWTError, jwt.PyJWKClientError) as exc:
            log.info("Rejected access token: %s", type(exc).__name__)
            raise unauthorized() from exc
        if claims.get("role") != AUDIENCE or claims.get("is_anonymous"):
            raise unauthorized()
        return User(id=str(claims["sub"]), email=claims.get("email"))


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


async def current_user(request: Request) -> User | None:
    """The signed-in user, or None when the request carries no token. A token that fails verification is an
    error (401), never silently anonymous."""
    token = _bearer(request)
    if token is None:
        return None
    auth: Auth = request.app.state.auth
    return await auth.verify(token)


async def require_user(request: Request) -> User:
    user = await current_user(request)
    if user is None:
        raise unauthorized()
    return user
