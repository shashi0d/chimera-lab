"""Supabase storage + db adapters. UNVERIFIED here (no keys); see P7-03.

The db adapter mirrors the local SQLite store: one table per collection,
each row `(key text primary key, doc jsonb)`. Tables come from schema.sql.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.errors import ChimeraError
from app.models.schemas import ErrorCode


def _client(url: str, key: str) -> Any:
    from supabase import create_client  # imported lazily so mock mode never needs it

    return create_client(url, key)


class SupabaseStorage:
    def __init__(self, url: str, key: str, bucket: str, signed_url_seconds: int = 3600) -> None:
        self.client = _client(url, key)
        self.bucket = bucket
        self.signed_url_seconds = signed_url_seconds

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        def _put() -> None:
            self.client.storage.from_(self.bucket).upload(
                key, data, {"content-type": content_type, "upsert": "true"}
            )

        await asyncio.to_thread(_put)
        return key

    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            return self.client.storage.from_(self.bucket).download(key)

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:  # supabase raises its own StorageException
            raise ChimeraError(ErrorCode.NOT_FOUND, "File not found.") from exc

    async def get_url(self, key: str) -> str:
        def _sign() -> str:
            res = self.client.storage.from_(self.bucket).create_signed_url(key, self.signed_url_seconds)
            return res.get("signedURL") or res.get("signedUrl") or res["signed_url"]

        return await asyncio.to_thread(_sign)


class SupabaseDb:
    def __init__(self, url: str, key: str) -> None:
        self.client = _client(url, key)

    async def put(self, collection: str, key: str, doc: dict[str, Any]) -> None:
        await asyncio.to_thread(lambda: self.client.table(collection).upsert({"key": key, "doc": doc}).execute())

    async def get(self, collection: str, key: str) -> dict[str, Any] | None:
        res = await asyncio.to_thread(
            lambda: self.client.table(collection).select("doc").eq("key", key).limit(1).execute()
        )
        return res.data[0]["doc"] if res.data else None

    async def list(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]:
        def _q() -> Any:
            q = self.client.table(collection).select("doc")
            if field is not None:
                q = q.eq(f"doc->>{field}", value)
            return q.execute()

        res = await asyncio.to_thread(_q)
        return [r["doc"] for r in res.data]

    async def incr(self, counter: str, by: int = 1) -> int:
        res = await asyncio.to_thread(lambda: self.client.rpc("incr_counter", {"k": counter, "by": by}).execute())
        return int(res.data)
