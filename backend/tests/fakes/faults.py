"""Test-only fault injection for the fake adapters (the app has no fault hooks)."""

from __future__ import annotations

import contextvars

current_fault: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_fault", default=None)
