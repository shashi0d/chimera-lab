"""Filesystem storage for dev and tests. URLs point back at the API."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.errors import ChimeraError
from app.models.schemas import ErrorCode


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, "Invalid storage key.")
        return p

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return key

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise ChimeraError(ErrorCode.NOT_FOUND, "File not found.")
        return await asyncio.to_thread(path.read_bytes)

    async def get_url(self, key: str) -> str:
        # Asset keys are "assets/<id>"; the API serves them at /assets/<id>/content.
        return f"/{key}/content"
