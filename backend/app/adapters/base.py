"""Adapter interfaces. Every external service sits behind one of these."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any, Protocol

from app.models.schemas import AnimalReading, FusionPlan

MOCK_FAULTS = {
    "timeout",
    "rate_limit",
    "server_error",
    "refusal",
    "not_animal",
    "human",
    "corrupt_output",
    "slow",
    "crash_mid_run",
    "budget",
}

# Set per request / per run task. Only mock adapters and the runner read it,
# and only when CHIMERA_MODE=mock (enforced where the header is parsed).
current_fault: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_fault", default=None)


@dataclass
class GeneratedImage:
    data: bytes
    content_type: str
    model: str


class VisionAdapter(Protocol):
    model_id: str

    async def describe_animal(self, image: bytes, slot: str) -> AnimalReading: ...

    async def plan_fusion(self, context: dict[str, Any]) -> FusionPlan: ...


class ImageGenAdapter(Protocol):
    model_id: str

    async def generate(
        self, prompt: str, reference_images: list[bytes], aspect: str | None
    ) -> GeneratedImage: ...


class StorageAdapter(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def get_url(self, key: str) -> str: ...


class DbAdapter(Protocol):
    """Document-style CRUD. Collections: assets, runs, graphs, creatures, idempotency, counters."""

    async def put(self, collection: str, key: str, doc: dict[str, Any]) -> None: ...

    async def get(self, collection: str, key: str) -> dict[str, Any] | None: ...

    async def list(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]: ...

    async def incr(self, counter: str, by: int = 1) -> int: ...
