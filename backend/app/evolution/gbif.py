"""GBIF species match for the open-world resolver (E4, ENGINE_CONTRACT.md).

Taxonomy for a learned animal comes only from here (source "gbif"). The resolver accepts
matchType EXACT at species rank or below; anything else returns needs_choice. Never guess.

`GbifClient` calls api.gbif.org with a timeout and the shared retry policy. `FixtureGbif`
replays responses recorded from the live API (tests/fixtures/recorded/gbif/), and can be
switched off to test the offline fallback. Both raise `GbifUnavailable` when GBIF cannot
be reached, so the resolver can fall back to "taxonomy unknown".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.adapters.mock.recorded import RECORDED
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.pipeline.retry import call_with_retry

GBIF_MATCH = "https://api.gbif.org/v1/species/match"
SPECIES_RANKS = ("SPECIES", "SUBSPECIES", "VARIETY", "FORM", "INFRASPECIFIC_NAME")
FIXTURES = RECORDED / "gbif"


class GbifUnavailable(Exception):
    """GBIF could not be reached (timeout, network error, 5xx after retries)."""


class Gbif(Protocol):
    async def match(self, scientific_name: str) -> dict[str, Any]: ...


def accepted(match: dict[str, Any]) -> bool:
    """EXACT at species rank or below, in Animalia. A genus-level EXACT ("Pangolin") is not a species."""
    return (match.get("matchType") == "EXACT" and match.get("rank") in SPECIES_RANKS
            and match.get("kingdom") == "Animalia")


def taxonomy_from(match: dict[str, Any]) -> dict[str, Any]:
    return {"class": match.get("class", ""), "order": match.get("order", ""), "family": match.get("family", ""),
            "genus": match.get("genus", ""), "gbif_key": str(match.get("usageKey") or ""),
            "canonical_name": match.get("canonicalName") or "", "rank": match.get("rank", ""),
            "status": match.get("status", "")}


def fixture_name(scientific_name: str) -> str:
    return "_".join(scientific_name.split()) + ".json"


class GbifClient:
    def __init__(self, timeout: float = 10.0, attempts: int = 2, base_delay: float = 0.5,
                 url: str = GBIF_MATCH, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.timeout, self.attempts, self.base_delay, self.url = timeout, attempts, base_delay, url
        self.transport = transport  # tests inject httpx.MockTransport
        self.recorded: list[dict[str, Any]] = []  # request/response pairs, for fixtures and the report

    async def _once(self, name: str) -> dict[str, Any]:
        params = {"name": name, "strict": "true", "kingdom": "Animalia"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                resp = await client.get(self.url, params=params)
        except httpx.HTTPError as e:
            raise ChimeraError(ErrorCode.UPSTREAM_TIMEOUT, f"GBIF unreachable: {e!r}", retryable=True) from e
        if resp.status_code >= 500:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, f"GBIF returned {resp.status_code}", retryable=True)
        if resp.status_code >= 400:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, f"GBIF returned {resp.status_code}", retryable=False)
        data = resp.json()
        self.recorded.append({"request": str(resp.request.url), "response": data})
        return data

    async def match(self, scientific_name: str) -> dict[str, Any]:
        try:
            return await call_with_retry(lambda: self._once(scientific_name), timeout=self.timeout + 1,
                                         base_delay=self.base_delay, max_attempts=self.attempts)
        except ChimeraError as e:
            raise GbifUnavailable(e.message) from e


class FixtureGbif:
    """Replays recorded GBIF responses. A name with no recording is a NONE match; online=False is GBIF down."""

    def __init__(self, root: Path = FIXTURES, online: bool = True) -> None:
        self.root, self.online = root, online
        self.calls: list[str] = []

    async def match(self, scientific_name: str) -> dict[str, Any]:
        self.calls.append(scientific_name)
        if not self.online:
            raise GbifUnavailable("GBIF offline (fixture switch)")
        path = self.root / fixture_name(scientific_name)
        if not path.exists():
            return {"matchType": "NONE", "confidence": 0, "synonym": False}
        return json.loads(path.read_text(encoding="utf-8"))["response"]
