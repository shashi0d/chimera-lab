"""SQLite document store for dev and tests (one table per collection)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

COLLECTIONS = ("assets", "runs", "graphs", "creatures", "idempotency", "counters")


class SqliteDb:
    def __init__(self, path: Path | str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            for c in COLLECTIONS:
                self._conn.execute(f"CREATE TABLE IF NOT EXISTS {c} (key TEXT PRIMARY KEY, doc TEXT NOT NULL)")
            self._conn.commit()

    def _check(self, collection: str) -> None:
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection {collection}")

    def _put(self, collection: str, key: str, doc: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                f"INSERT INTO {collection}(key, doc) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET doc=excluded.doc",
                (key, json.dumps(doc)),
            )
            self._conn.commit()

    def _get(self, collection: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(f"SELECT doc FROM {collection} WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _list(self, collection: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(f"SELECT doc FROM {collection}").fetchall()
        return [json.loads(r[0]) for r in rows]

    def _incr(self, counter: str, by: int) -> int:
        with self._lock:
            row = self._conn.execute("SELECT doc FROM counters WHERE key=?", (counter,)).fetchone()
            value = (json.loads(row[0])["value"] if row else 0) + by
            self._conn.execute(
                "INSERT INTO counters(key, doc) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET doc=excluded.doc",
                (counter, json.dumps({"value": value})),
            )
            self._conn.commit()
        return value

    async def put(self, collection: str, key: str, doc: dict[str, Any]) -> None:
        self._check(collection)
        await asyncio.to_thread(self._put, collection, key, doc)

    async def get(self, collection: str, key: str) -> dict[str, Any] | None:
        self._check(collection)
        return await asyncio.to_thread(self._get, collection, key)

    async def list(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]:
        self._check(collection)
        docs = await asyncio.to_thread(self._list, collection)
        if field is None:
            return docs
        return [d for d in docs if d.get(field) == value]

    async def incr(self, counter: str, by: int = 1) -> int:
        return await asyncio.to_thread(self._incr, counter, by)
