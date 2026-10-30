"""Per-call accounting for real model calls (L1-04) and the hard live budget (L1).

Adapters call ``guard(kind)`` before every HTTP attempt and ``record(...)``
after it. Records go to the current run (``current_calls``) so the runner can
put tokens per step in the run detail and charge the token spend guard, and,
when ``CHIMERA_LIVE_LOG`` is set, to a markdown log (docs/LIVE_LOG.md).

``CHIMERA_LIVE_BUDGET_FILE`` enables a hard, cross-process cap on live calls
(``CHIMERA_LIVE_MAX_IMAGES`` / ``CHIMERA_LIVE_MAX_SPARK``). Every attempt
counts, failed ones included; past the cap the adapter refuses to call.
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.errors import ChimeraError
from app.models.schemas import ErrorCode

CallKind = Literal["spark", "image"]


@dataclass
class CallRecord:
    step: str
    kind: CallKind
    purpose: str  # describe / plan / card / generate / text_to_image
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    outcome: str = "ok"  # "ok" or an error code
    response_id: str | None = None
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


current_step: contextvars.ContextVar[str] = contextvars.ContextVar("current_step", default="-")
current_calls: contextvars.ContextVar[list[CallRecord] | None] = contextvars.ContextVar("current_calls", default=None)

_lock = threading.Lock()


def tokens_of(usage: dict[str, Any] | None) -> tuple[int, int, int]:
    """Chat completions report prompt/completion tokens; the Responses API input/output tokens."""
    u = usage or {}
    inp = int(u.get("input_tokens") or u.get("prompt_tokens") or 0)
    out = int(u.get("output_tokens") or u.get("completion_tokens") or 0)
    total = int(u.get("total_tokens") or inp + out)
    return inp, out, total


def record(rec: CallRecord) -> None:
    calls = current_calls.get()
    if calls is not None:
        calls.append(rec)
    log_path = os.environ.get("CHIMERA_LIVE_LOG")
    if log_path:
        _append_log(Path(log_path), rec)


def _append_log(path: Path, rec: CallRecord) -> None:
    with _lock:
        new = not path.exists()
        with path.open("a", encoding="utf-8") as f:
            if new:
                f.write("# Live call log\n\nEvery real Meta API call made by L1 (appended automatically by "
                        "`backend/app/adapters/usage.py`).\n\n| Time (UTC) | Step | Purpose | Model | Latency ms | "
                        "Input tok | Output tok | Total tok | Outcome | Response id |\n|---|---|---|---|---|---|---|---|---|---|\n")
            f.write(f"| {rec.ts} | {rec.step} | {rec.purpose} | {rec.model} | {rec.latency_ms} | {rec.input_tokens} | "
                    f"{rec.output_tokens} | {rec.total_tokens} | {rec.outcome} | {rec.response_id or ''} |\n")


# ------------------------------------------------------------------ hard live budget


def _budget_file() -> Path | None:
    p = os.environ.get("CHIMERA_LIVE_BUDGET_FILE")
    return Path(p) if p else None


def _limits() -> dict[str, int]:
    return {"image": int(os.environ.get("CHIMERA_LIVE_MAX_IMAGES", "15")),
            "spark": int(os.environ.get("CHIMERA_LIVE_MAX_SPARK", "60"))}


def budget_used() -> dict[str, int]:
    path = _budget_file()
    if not path or not path.exists():
        return {"image": 0, "spark": 0}
    return {"image": 0, "spark": 0, **json.loads(path.read_text())}


def guard(kind: CallKind) -> None:
    """Count one attempt against the live budget, or refuse it. No-op when no budget file is configured."""
    path = _budget_file()
    if path is None:
        return
    with _lock:
        used = budget_used()
        limit = _limits()[kind]
        if used[kind] >= limit:
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, f"Live budget reached: {used[kind]}/{limit} {kind} calls.",
                               retryable=False)
        used[kind] += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(used))


class Timer:
    def __enter__(self) -> Timer:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = int((time.perf_counter() - self.start) * 1000)


def as_dict(rec: CallRecord) -> dict[str, Any]:
    return asdict(rec)
