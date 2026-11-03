"""Adapter interfaces. Every external service sits behind one of these."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.schemas import AnimalReading


@dataclass
class GeneratedImage:
    data: bytes
    content_type: str
    model: str
    # L1-01: Meta's response id, so a later edit can chain with previous_response_id.
    response_id: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)


class VisionAdapter(Protocol):
    model_id: str

    async def describe_animal(self, image: bytes, slot: str) -> AnimalReading: ...


class ImageGenAdapter(Protocol):
    model_id: str

    async def generate(self, prompt: str, reference_images: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage: ...


class StorageAdapter(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def get_url(self, key: str) -> str: ...


class DbAdapter(Protocol):
    """Document-style CRUD. Collections: assets, graphs, creatures, agent_runs, counters."""

    async def put(self, collection: str, key: str, doc: dict[str, Any]) -> None: ...

    async def get(self, collection: str, key: str) -> dict[str, Any] | None: ...

    async def list(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]: ...

    async def incr(self, counter: str, by: int = 1) -> int: ...
