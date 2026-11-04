"""Agent run state and its event log, in the existing document store (collection `agent_runs`).

One document per run holds the snapshot fields of GET /evo/agent/runs/{id} plus the stored events, so a replay is
identical to what was streamed (ids start at 1 and grow by 1, no gaps). While a run lives in this process the
document is kept in memory and written through on every change; readers in this process are woken on each new event.
A run that is not alive here and whose `updatedAt` is older than the lease (D-016) is marked interrupted when read.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.adapters.base import DbAdapter
from app.util import now_iso, parse_iso

COLLECTION = "agent_runs"
TERMINAL = {"succeeded", "failed", "interrupted"}
TERMINAL_EVENTS = {"finalize", "error"}
PUBLIC_FIELDS = ("runId", "status", "position", "sire", "dam", "style", "createdAt", "updatedAt", "lastEventId",
                 "creatureId", "error", "pendingChoice")
INTERRUPTED = {"code": "RUN_INTERRUPTED", "retryable": True,
               "message": "The server stopped while this run was going, so it ended. Start it again."}


def snapshot(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in PUBLIC_FIELDS}


class RunStore:
    def __init__(self, db: DbAdapter, lease_seconds: float) -> None:
        self.db, self.lease = db, lease_seconds
        self.live: dict[str, dict[str, Any]] = {}  # runs owned by this process
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiters: dict[str, list[asyncio.Future[None]]] = {}

    def lock(self, run_id: str) -> asyncio.Lock:
        return self._locks.setdefault(run_id, asyncio.Lock())

    # ------------------------------------------------------------ read / write

    async def create(self, doc: dict[str, Any]) -> None:
        doc.setdefault("events", [])
        doc.setdefault("lastEventId", 0)
        self.live[doc["runId"]] = doc
        await self.save(doc)

    async def save(self, doc: dict[str, Any]) -> None:
        doc["updatedAt"] = now_iso()
        await self.db.put(COLLECTION, doc["runId"], doc)

    async def get(self, run_id: str) -> dict[str, Any] | None:
        if run_id in self.live:
            return self.live[run_id]
        doc = await self.db.get(COLLECTION, run_id)
        if doc is None:
            return None
        if doc.get("status") not in TERMINAL:
            age = (datetime.now(UTC) - parse_iso(doc["updatedAt"])).total_seconds()
            if age > self.lease:
                await self.interrupt(doc)
        return doc

    def release(self, run_id: str) -> None:
        """The run ended here: later reads go to the store."""
        self.live.pop(run_id, None)
        self._locks.pop(run_id, None)

    # ------------------------------------------------------------ events

    async def append(self, doc: dict[str, Any], type_: str, **payload: Any) -> dict[str, Any]:
        async with self.lock(doc["runId"]):
            event = {"id": doc["lastEventId"] + 1, "type": type_, "runId": doc["runId"], "at": now_iso(), **payload}
            doc["events"].append(event)
            doc["lastEventId"] = event["id"]
            await self.save(doc)
        self.notify(doc["runId"])
        return event

    async def update(self, doc: dict[str, Any], **fields: Any) -> None:
        async with self.lock(doc["runId"]):
            doc.update(fields)
            await self.save(doc)
        self.notify(doc["runId"])

    def notify(self, run_id: str) -> None:
        for fut in self._waiters.pop(run_id, []):
            if not fut.done():
                fut.set_result(None)

    async def wait(self, run_id: str, timeout: float) -> bool:
        """Wait for the next change of a run that lives here. False on timeout (or when the run is not live here,
        after `timeout`: the caller re-reads the store)."""
        if run_id not in self.live:
            await asyncio.sleep(timeout)
            return False
        fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(run_id, []).append(fut)
        try:
            await asyncio.wait_for(fut, timeout)
            return True
        except TimeoutError:
            return False

    # ------------------------------------------------------------ interruption

    async def interrupt(self, doc: dict[str, Any]) -> None:
        if doc.get("status") in TERMINAL:
            return
        event = {"id": doc.get("lastEventId", 0) + 1, "type": "error", "runId": doc["runId"], "at": now_iso(),
                 **INTERRUPTED}
        doc.setdefault("events", []).append(event)
        doc.update(lastEventId=event["id"], status="interrupted", error=dict(INTERRUPTED), pendingChoice=None,
                   position=None)
        await self.save(doc)
        self.notify(doc["runId"])

    async def interrupt_orphans(self) -> int:
        """Single-process (local) store: any unfinished run at startup is orphaned."""
        n = 0
        for doc in await self.db.list(COLLECTION):
            if doc.get("status") not in TERMINAL and doc.get("runId") not in self.live:
                await self.interrupt(doc)
                n += 1
        return n
