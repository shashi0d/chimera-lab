"""Public-safety caps for agent runs (docs/api_contract.md "Caps"; per-run caps are the engine's own, S3c).

- daily total and per-user daily runs: counters in the document store, keyed by the UTC day (they reset at 00:00
  UTC); refused at POST with 429 CAP_REACHED, never as an event
- the per-IP rate limit on POST /evo/agent/runs: a sliding minute, in memory (429 RATE_LIMITED, Retry-After)
- the concurrent-run limit lives in the job runner (extra runs are queued)

The per-user counter is keyed by the signed-in user's id. The client IP (rate limit only) is the X-Forwarded-For
entry written by the trusted proxy in front of the app (EVO_PROXY_HOPS from the right), else the socket peer.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request

from app.adapters.base import DbAdapter
from app.config import Settings
from app.errors import ChimeraError
from app.models.schemas import ErrorCode


def client_ip(request: Request, hops: int) -> str:
    fwd = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if hops > 0 and fwd:
        return fwd[-hops] if len(fwd) >= hops else fwd[0]
    return request.client.host if request.client else "unknown"


def day_key(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def resets_at(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.strftime("%Y-%m-%dT%H:%M:%SZ")


def cap_error(scope: str, limit: int) -> ChimeraError:
    message = ("Today's live creature runs are used up. The gallery is still open; new runs open again at 00:00 UTC."
               if scope == "daily_total" else
               "You've used today's live creature runs. The gallery is still open; new runs open again at 00:00 UTC.")
    return ChimeraError(ErrorCode.CAP_REACHED, message, retryable=False,
                        details={"scope": scope, "limit": limit, "resetsAt": resets_at()})


class Caps:
    def __init__(self, db: DbAdapter, settings: Settings) -> None:
        self.db, self.settings = db, settings
        self._recent: dict[str, deque[float]] = defaultdict(deque)

    def rate_limit(self, ip: str) -> None:
        per_minute = self.settings.evo_runs_per_minute_per_ip
        now = time.monotonic()
        q = self._recent[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= per_minute:
            retry_ms = int((60 - (now - q[0])) * 1000) + 1
            raise ChimeraError(ErrorCode.RATE_LIMITED, "You're starting runs too quickly. Wait a minute and try "
                               "again.", retry_after_ms=retry_ms, details={"limit": per_minute, "window": "1m"})
        q.append(now)

    def _keys(self, visitor: str) -> tuple[str, str]:
        day = day_key()
        return f"agent_runs:{day}", f"agent_runs:{day}:v:{visitor}"

    async def used(self, visitor: str) -> tuple[int, int]:
        total, mine = self._keys(visitor)
        return await self.db.incr(total, 0), await self.db.incr(mine, 0)

    async def check(self, visitor: str) -> None:
        """Refuse before any work (no identify call is spent on a capped request)."""
        total, mine = await self.used(visitor)
        if total >= self.settings.evo_daily_runs:
            raise cap_error("daily_total", self.settings.evo_daily_runs)
        if mine >= self.settings.evo_visitor_daily_runs:
            raise cap_error("visitor_daily", self.settings.evo_visitor_daily_runs)

    async def take(self, visitor: str) -> None:
        """Count one run; increment first, then roll back if a racing request took the last one."""
        total_key, mine_key = self._keys(visitor)
        total = await self.db.incr(total_key, 1)
        if total > self.settings.evo_daily_runs:
            await self.db.incr(total_key, -1)
            raise cap_error("daily_total", self.settings.evo_daily_runs)
        mine = await self.db.incr(mine_key, 1)
        if mine > self.settings.evo_visitor_daily_runs:
            await self.db.incr(mine_key, -1)
            await self.db.incr(total_key, -1)
            raise cap_error("visitor_daily", self.settings.evo_visitor_daily_runs)

    async def limits(self, visitor: str | None, running: int, queued: int) -> dict[str, Any]:
        """`visitor` is the signed-in user's id; signed out, only the shared numbers are known."""
        total, mine = await self.used(visitor) if visitor else (await self.db.incr(self._keys("-")[0], 0), 0)
        s = self.settings
        capped = total >= s.evo_daily_runs or mine >= s.evo_visitor_daily_runs
        return {"liveRuns": "capped" if capped else "open",
                "dailyTotal": {"used": total, "limit": s.evo_daily_runs, "resetsAt": resets_at()},
                "visitor": {"used": mine, "limit": s.evo_visitor_daily_runs},
                "concurrent": {"running": running, "limit": s.evo_max_concurrent_runs, "queued": queued}}
