"""Executes runs step by step as in-process asyncio tasks.

Each status change bumps `version` (used as the ETag) and `updatedAt`. A
heartbeat keeps `updatedAt` fresh during long steps; a run whose heartbeat
stops for RUN_LEASE_SECONDS is marked `interrupted` the next time it is read.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.adapters.base import current_fault
from app.errors import ChimeraError
from app.models.schemas import ApiError, ErrorCode, Graph, Run, Step
from app.pipeline.context import RunContext
from app.pipeline.registry import EXECUTORS, StepDef
from app.services import Services
from app.util import now_iso, parse_iso

log = logging.getLogger(__name__)
TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}
HEARTBEAT_SECONDS = 10.0


class _Crash(BaseException):
    """Simulated process death (mock fault crash_mid_run)."""


class RunManager:
    def __init__(self, services: Services) -> None:
        self.services = services
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------ persistence

    async def save(self, run: Run) -> Run:
        run.version += 1
        run.updated_at = now_iso()
        await self.services.db.put("runs", run.id, run.dump())
        return run

    async def load(self, run_id: str) -> Run | None:
        doc = await self.services.db.get("runs", run_id)
        if doc is None:
            return None
        run = Run.model_validate(doc)
        if run.status not in TERMINAL and run.id not in self.tasks:
            age = (datetime.now(UTC) - parse_iso(run.updated_at)).total_seconds()
            if age > self.services.settings.run_lease_seconds:
                await self._interrupt(run)
        return run

    async def _interrupt(self, run: Run) -> None:
        run.status = "interrupted"
        run.error = ChimeraError(
            ErrorCode.RUN_INTERRUPTED, "The server stopped while this fusion was running.", retryable=True
        ).to_api()
        for step in run.steps:
            if step.status in ("running", "pending"):
                step.status = "skipped"
        await self.save(run)

    async def interrupt_orphans(self) -> int:
        """Single-process (local) backends: any unfinished run at startup is orphaned."""
        count = 0
        for doc in await self.services.db.list("runs"):
            if doc.get("status") not in TERMINAL:
                await self._interrupt(Run.model_validate(doc))
                count += 1
        return count

    # ------------------------------------------------------------ lifecycle

    def new_steps(self, node_type: str) -> list[Step]:
        return [Step(key=s.key, label=s.label) for s in EXECUTORS[node_type].steps()]

    def start(self, run: Run, graph: Graph, node_type: str, fault: str | None) -> None:
        executor = EXECUTORS[node_type]
        node = next(n for n in graph.nodes if n.id == run.node_id)
        ctx = RunContext(run=run, graph=graph, services=self.services, fault=fault)
        ctx.inputs = executor.resolve_inputs(graph, node)
        ctx.state.update(executor.configure(node))
        token = current_fault.set(fault)
        try:
            task = asyncio.create_task(self._execute(ctx, executor.steps()), name=f"run-{run.id}")
        finally:
            current_fault.reset(token)
        self.tasks[run.id] = task
        task.add_done_callback(lambda _t: self.tasks.pop(run.id, None))

    async def cancel(self, run: Run) -> Run:
        task = self.tasks.get(run.id)
        if task is not None:
            task.cancel()
            try:
                await task
            except BaseException:  # noqa: BLE001 - cancellation / crash both end here
                pass
        fresh = await self.load(run.id) or run
        if fresh.status in TERMINAL:
            return fresh
        fresh.status = "cancelled"
        for step in fresh.steps:
            if step.status in ("running", "pending"):
                step.status = "skipped"
                step.detail = "Cancelled" if step.started_at else step.detail
        return await self.save(fresh)

    async def _heartbeat(self, run: Run) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self.save(run)

    async def _execute(self, ctx: RunContext, steps: list[StepDef]) -> None:
        run = ctx.run
        run.status = "running"
        await self.save(run)
        beat = asyncio.create_task(self._heartbeat(run))
        try:
            for i, step_def in enumerate(steps):
                step = run.steps[i]
                step.status = "running"
                step.started_at = now_iso()
                await self.save(run)
                if ctx.fault == "slow":
                    await asyncio.sleep(8 * self.services.settings.mock_delay_scale)
                if ctx.fault == "crash_mid_run" and step_def.key == "generate":
                    raise _Crash()
                try:
                    step.detail = await step_def.fn(ctx)
                except ChimeraError as exc:
                    step.status = "failed"
                    step.ended_at = now_iso()
                    step.detail = exc.message
                    self._fail(run, exc.to_api(), exc.details.get("slot"))
                    await self.save(run)
                    return
                step.status = "succeeded"
                step.ended_at = now_iso()
                await self.save(run)
            run.status = "succeeded"
            run.result = ctx.state["result"]
            await self.save(run)
        except asyncio.CancelledError:
            raise
        except _Crash:
            log.warning("run %s: simulated crash, leaving it for the lease check", run.id)
        except Exception as exc:
            log.exception("run %s crashed", run.id)
            for step in run.steps:
                if step.status == "running":
                    step.status = "failed"
                    step.ended_at = now_iso()
            self._fail(run, ChimeraError(ErrorCode.INTERNAL).to_api(), None)
            await self.save(run)
            del exc
        finally:
            beat.cancel()

    @staticmethod
    def _fail(run: Run, error: ApiError, slot: object) -> None:
        run.status = "failed"
        run.error = error
        run.failed_input = slot if slot in ("A", "B") else None  # type: ignore[assignment]
        for step in run.steps:
            if step.status == "pending":
                step.status = "skipped"
