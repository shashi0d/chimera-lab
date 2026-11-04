"""The Fusion job runner: in-process asyncio tasks with a heartbeat lease (D-016), a concurrent-run limit with a queue,
and a hard time cap. Works on any host that keeps one Python process alive for a run.

A job's driver does the work and reports through the job (`emit`): PromptDriver renders one image from the Fusion
prompt (app.agentapi.fusion_prompt), writes the creature's profile, and saves the creature that becomes image V1.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agentapi.creatures import Creatures, build_creature
from app.agentapi.files import EXT, PublicFiles
from app.agentapi.store import RunStore
from app.errors import ChimeraError
from app.services import Services
from app.util import new_id, now_iso

log = logging.getLogger(__name__)

HARD_STOP = "This run passed its {minutes}-minute limit and was stopped. Nothing was saved; try again."


class RunFailed(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.retryable = code, message, retryable


class Driver(Protocol):
    async def run(self, job: Job) -> dict[str, Any]:
        """Do the run; return the finalize payload, or raise RunFailed / ChimeraError."""
        ...


@dataclass
class Hold:
    """A queue placeholder ahead of a mock 'queued' run: it leaves the queue at `release_at` (monotonic)."""
    release_at: float
    released: bool = False


@dataclass
class Job:
    doc: dict[str, Any]
    driver: Driver
    runner: JobRunner
    not_before: float | None = None  # mock 'queued': the earliest start (monotonic)
    task: asyncio.Task[None] | None = None
    t0: float = 0.0
    position: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return str(self.doc["runId"])

    async def emit(self, type_: str, **payload: Any) -> dict[str, Any]:
        return await self.runner.store.append(self.doc, type_, **payload)

class JobRunner:
    def __init__(self, services: Services, store: RunStore, files: PublicFiles, creatures: Creatures) -> None:
        self.services, self.store, self.files, self.creatures = services, store, files, creatures
        self.settings = services.settings
        self.running: dict[str, Job] = {}
        self.queue: list[Job | Hold] = []
        self._dispatch_lock = asyncio.Lock()
        self._beat: asyncio.Task[None] | None = None
        self._timers: set[asyncio.Task[None]] = set()
        self._closing = False

    # ------------------------------------------------------------ queue

    @property
    def queued_jobs(self) -> list[Job]:
        return [j for j in self.queue if isinstance(j, Job)]

    def _can_start_now(self, job: Job) -> bool:
        return not self.queue and len(self.running) < self.settings.evo_max_concurrent_runs and job.not_before is None

    async def submit(self, job: Job, holds: list[float] | None = None) -> None:
        """Create the run: start it now, or queue it (a queued event with its position)."""
        self._ensure_heartbeat()
        now = time.monotonic()
        hold_objs = [Hold(now + d) for d in (holds or [])]
        if not hold_objs and self._can_start_now(job):
            job.doc.update(status="running", position=None)
            await self.store.create(job.doc)
            self._start(job)
            return
        self.queue.extend(hold_objs)
        self.queue.append(job)
        job.position = self.queue.index(job) + 1
        job.doc.update(status="queued", position=job.position)
        await self.store.create(job.doc)
        await job.emit("queued", position=job.position, ahead=job.position)
        for h in hold_objs:
            self._later(h.release_at - now, lambda h=h: self._release(h))
        if job.not_before is not None:
            self._later(job.not_before - now, self.dispatch)
        await self.dispatch()

    def _later(self, delay: float, fn: Any) -> None:
        """Run the coroutine function `fn` after `delay` seconds (dropped on shutdown)."""
        async def go() -> None:
            await asyncio.sleep(max(0.0, delay))
            await fn()

        t = asyncio.create_task(go())
        self._timers.add(t)
        t.add_done_callback(self._timers.discard)

    async def _release(self, hold: Hold) -> None:
        hold.released = True
        await self.dispatch()

    async def dispatch(self) -> None:
        """Two phases, so every position a run passes through is announced: released holds leave the queue and the
        new positions are sent; then runs start while a slot is free (and the rest move up again)."""
        async with self._dispatch_lock:
            before = len(self.queue)
            while self.queue and isinstance(self.queue[0], Hold) and self.queue[0].released:
                self.queue.pop(0)
            if len(self.queue) != before:
                await self._announce()
            started = False
            while self.queue:
                head = self.queue[0]
                if isinstance(head, Hold):
                    break
                if len(self.running) >= self.settings.evo_max_concurrent_runs:
                    break
                if head.not_before is not None and time.monotonic() < head.not_before:
                    break
                self.queue.pop(0)
                started = True
                head.position = None
                await self.store.update(head.doc, status="running", position=None)
                self._start(head)
            if started:
                await self._announce()

    async def _announce(self) -> None:
        for i, entry in enumerate(self.queue, 1):
            if isinstance(entry, Job) and entry.position != i:
                entry.position = i
                await self.store.update(entry.doc, position=i)
                await entry.emit("queued", position=i, ahead=i)

    # ------------------------------------------------------------ execution

    def _start(self, job: Job) -> None:
        self.running[job.run_id] = job
        job.task = asyncio.create_task(self._execute(job), name=f"agent-run-{job.run_id}")

    async def _execute(self, job: Job) -> None:
        st, doc = self.settings, job.doc
        try:
            await job.emit("started", sire=doc["sire"], dam=doc["dam"], style=doc.get("style"),
                           caps=self.caps())
            job.t0 = time.monotonic()
            try:
                fin = await asyncio.wait_for(job.driver.run(job), timeout=st.evo_run_hard_seconds)
            except TimeoutError as exc:
                raise RunFailed("RUN_INTERRUPTED", HARD_STOP.format(minutes=round(st.evo_run_hard_seconds / 60)),
                                retryable=True) from exc
            await job.emit("finalize", **fin)
            await self.store.update(doc, status="succeeded", creatureId=fin["creatureId"], pendingChoice=None)
        except asyncio.CancelledError:
            await self.store.interrupt(doc)
            raise
        except RunFailed as e:
            await self._fail(job, e.code, e.message, e.retryable)
        except ChimeraError as e:
            await self._fail(job, e.code.value, e.message, e.retryable)
        except Exception:
            log.exception("run %s crashed", job.run_id)
            await self._fail(job, "INTERNAL", "Something went wrong on our side, so this run ended. Try again.", True)
        finally:
            self.running.pop(job.run_id, None)
            self.store.release(job.run_id)
            if not self._closing:
                self._later(0, self.dispatch)

    async def _fail(self, job: Job, code: str, message: str, retryable: bool) -> None:
        await job.emit("error", code=code, message=message, retryable=retryable)
        await self.store.update(job.doc, status="failed", pendingChoice=None,
                                error={"code": code, "message": message, "retryable": retryable})

    def caps(self) -> dict[str, Any]:
        return {"renders": 1, "toolCalls": 1, "seconds": int(self.settings.evo_run_hard_seconds)}

    # ------------------------------------------------------------ lease

    def _ensure_heartbeat(self) -> None:
        if self._beat is None or self._beat.done():
            self._beat = asyncio.create_task(self._heartbeat())

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self.settings.evo_heartbeat_seconds)
            for job in [*self.running.values(), *self.queued_jobs]:
                async with self.store.lock(job.run_id):
                    await self.store.save(job.doc)

    async def shutdown(self) -> None:
        self._closing = True
        for t in list(self._timers):
            t.cancel()
        if self._beat:
            self._beat.cancel()
        tasks = [j.task for j in self.running.values() if j.task]
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except BaseException:  # noqa: BLE001 - cancelled on shutdown
                pass
        for j in self.queued_jobs:
            await self.store.interrupt(j.doc)
        self.queue.clear()


# ====================================================================== drivers


class PromptDriver:
    """Prompt mode (EVO_FUSION_MODE=prompt): one Muse Image call with a plain prompt, no plan, critics or edits.

    The prompt comes from app.agentapi.fusion_prompt (EVO_FUSION_PROMPT, the art style, the white background). The
    parents' photos or earlier creatures go to the image model as reference images. The run emits the same events
    as the agent (one step, one render, finalize), so the Lab shows its image as V1. How the image was made (the
    prompt, style, parents and references) is kept in the creature's plan, so later steps can build on it."""

    def __init__(self, services: Services) -> None:
        self.svc = services

    def generation(self, job: Job) -> tuple[str, list[bytes], dict[str, Any]]:
        from app.agentapi.fusion_prompt import SLOT_ORDER, build_fusion_prompt, style_phrase

        doc = job.doc
        refs_by_slot: dict[str, bytes] = job.extra.get("refs") or {}
        slots = [s for s in SLOT_ORDER if refs_by_slot.get(s)]
        style = doc.get("style") or "real"
        prompt = build_fusion_prompt(self.svc.settings, doc["sire"], doc["dam"], style, slots)
        record = {"fusion_mode": "prompt", "operation": "fusion", "prompt": prompt, "style": style,
                  "style_wording": style_phrase(style), "references": slots,
                  "parents": [{k: doc[s].get(k) for k in ("commonName", "scientificName", "source", "versionId",
                                                          "summary")} for s in SLOT_ORDER]}
        return prompt, [refs_by_slot[s] for s in slots], record

    async def run(self, job: Job) -> dict[str, Any]:
        from app.adapters.retrying import RetryingImageGen

        svc, doc = self.svc, job.doc
        prompt, refs, record = self.generation(job)
        t0 = time.monotonic()
        img = await RetryingImageGen(svc.image_gen, svc.settings).generate(prompt, refs, "1:1")
        job.extra.pop("refs", None)
        if not img.data:
            raise RunFailed("UPSTREAM_ERROR", "The image model returned no image. Try again.", True)
        # The creature's basic info (name, size, habitat, notes): its title now, its card and its next Fusion later.
        from app.agentapi.creature_ai import make_profile

        record["profile"] = await make_profile(svc.vision, img.data, record)
        summary = f"rendered with {len(refs)} reference image(s): {prompt}" if refs else f"rendered: {prompt}"
        await job.emit("step", n=1, tool="render", args={"prompt": prompt}, summary=summary,
                       reason="prompt mode: one image from a plain prompt", cards=[], ok=True, error=None)
        ext = EXT.get(img.content_type, "webp")
        url = await job.runner.files.put(f"runs/{job.run_id}/img1.{ext}", img.data, img.content_type)
        await job.emit("render", n=1, imageId="img1", url=url, kind="render", parent=None, method="prompt",
                       rendersUsed=1, rendersLeft=0)
        cid = new_id("crt")
        view = build_creature(creature_id=cid, created_at=now_iso(), sire=doc["sire"], dam=doc["dam"], image_url=url,
                              generation=record, run_id=job.run_id, seconds=round(time.monotonic() - t0, 1))
        await job.runner.creatures.save(view, doc.get("owner"))
        return {"creatureId": cid, "imageId": "img1", "imageUrl": url, "remainingFailures": [], "hiddenChecks": 0,
                "agree": True, "stop": "finalized", "title": view["title"]}
