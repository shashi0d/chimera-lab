"""The agent job runner: in-process asyncio tasks with a heartbeat lease (D-016), a concurrent-run limit with a queue,
interactive choices, and the per-run time caps. Works on any host that keeps one Python process alive for a run.

A job's driver does the work and reports through the job (`emit`, `ask`):
- AgentDriver runs the engine's agent (EvoEngine.agent_fuse) on Muse Spark Open and turns its trace steps into events.
  Tests build it offline (the scripted policy brain over the engine's offline adapters); the app never does.

Time caps: at EVO_RUN_SOFT_SECONDS (14 min) a cap_reached(time) event fires and the agent's next turn finalizes its
best inspected image (DeadlineBrain); at EVO_RUN_HARD_SECONDS (15 min) the runner stops the run with an error event.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.agentapi.creature import build_creature, short_args, visible
from app.agentapi.files import EXT, PublicFiles
from app.agentapi.gallery import Creatures
from app.agentapi.store import RunStore
from app.errors import ChimeraError
from app.services import Services
from app.util import new_id, now_iso

log = logging.getLogger(__name__)

CAP_MESSAGES = {
    "renders": "This run has used its {limit} renders. The agent now finalizes its best image.",
    "tool_calls": "This run has used its {limit} tool calls. The agent now finalizes its best image.",
    "time": "This run has reached its {minutes}-minute limit. The agent now finalizes its best image.",
}
HARD_STOP = ("This run passed its {minutes}-minute limit and was stopped. Nothing was saved; try again, the gallery "
             "is still open.")


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
    choice: dict[str, Any] | None = None
    t0: float = 0.0
    position: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return str(self.doc["runId"])

    @property
    def soft_deadline(self) -> float:
        return self.t0 + self.runner.settings.evo_run_soft_seconds

    async def emit(self, type_: str, **payload: Any) -> dict[str, Any]:
        return await self.runner.store.append(self.doc, type_, **payload)

    async def cap(self, scope: str, limit: int) -> None:
        minutes = round(self.runner.settings.evo_run_soft_seconds / 60)
        await self.emit("cap_reached", scope=scope, limit=limit,
                        message=CAP_MESSAGES[scope].format(limit=limit, minutes=minutes))

    async def ask(self, kind: str, question: str, options: list[str], n: int | None) -> str | None:
        """A needs_choice event, then wait for POST .../choice or the timeout; choice_resolved either way."""
        st = self.runner.settings
        choice_id = new_id("choice")
        expires = (datetime.now(UTC) + timedelta(seconds=st.evo_choice_seconds)).isoformat(
            timespec="milliseconds").replace("+00:00", "Z")
        fut: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self.choice = {"choiceId": choice_id, "options": list(options), "future": fut}
        pending = {"choiceId": choice_id, "kind": kind, "question": question, "options": list(options),
                   "expiresAt": expires}
        await self.runner.store.update(self.doc, status="needs_choice", pendingChoice=pending)
        await self.emit("needs_choice", n=n, choiceId=choice_id, kind=kind, question=question, options=list(options),
                        expiresAt=expires)
        try:
            answer: str | None = await asyncio.wait_for(asyncio.shield(fut), st.evo_choice_seconds)
            by = "user"
        except TimeoutError:
            answer, by = None, "timeout"
        finally:
            self.choice = None
            if not fut.done():
                fut.cancel()
        await self.runner.store.update(self.doc, status="running", pendingChoice=None)
        await self.emit("choice_resolved", choiceId=choice_id, answer=answer, by=by)
        return answer


class ChoiceRefused(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


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
            await job.emit("started", sire=doc["sire"], dam=doc["dam"], mode=doc["mode"],
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
            log.exception("agent run %s crashed", job.run_id)
            await self._fail(job, "INTERNAL", "Something went wrong on our side, so this run ended. Try again; the "
                             "gallery is still open.", True)
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
        from app.evolution.agent import settings as agent_settings

        a = agent_settings()
        return {"renders": a["max_renders"], "toolCalls": a["max_tool_calls"],
                "seconds": int(self.settings.evo_run_hard_seconds)}

    # ------------------------------------------------------------ choices

    def answer(self, run_id: str, choice_id: str, answer: Any) -> None:
        job = self.running.get(run_id)
        ch = job.choice if job else None
        if ch is None or ch["choiceId"] != choice_id or ch["future"].done():
            raise ChoiceRefused(409, "This choice was already answered or has expired.")
        if not isinstance(answer, str) or answer not in ch["options"]:
            raise ChoiceRefused(422, "Pick one of the offered options.")
        ch["future"].set_result(answer)

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


class DeadlineBrain:
    """Wraps the agent's brain for the 14-minute time cap: past the soft deadline the next turn finalizes the best
    inspected image (inspecting the last render first if none is inspected). Before it, the inner brain decides."""

    def __init__(self, inner: Any, job: Job) -> None:
        self.inner, self.job = inner, job
        self.model_id = getattr(inner, "model_id", "?")
        self.run: Any = None
        self.fired = False

    def bind(self, run: Any) -> None:
        self.run = run
        if hasattr(self.inner, "bind"):
            self.inner.bind(run)

    async def next(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        from app.evolution.agent import Turn

        if time.monotonic() < self.job.soft_deadline:
            return await self.inner.next(messages, tools)
        if not self.fired:
            self.fired = True
            await self.job.extra["flush"]()
            await self.job.cap("time", int(self.job.runner.settings.evo_run_soft_seconds))
        r = self.run
        why = "code: the run reached its time limit; finalize the best inspected image"
        if r.state.finalized:
            return Turn([], "time cap")
        best = r.best_image_id()
        if best:
            return Turn([{"id": "deadline_finalize", "name": "finalize",
                          "arguments": {"image_id": best, "reason": why}}])
        if r.state.order and r.state.images[r.state.order[-1]].inspect is None:
            return Turn([{"id": "deadline_inspect", "name": "inspect",
                          "arguments": {"image_id": r.state.order[-1], "reason": why}}])
        return Turn([], "time cap: no image to finalize")


class AgentDriver:
    """The engine's agent (S3c/S5) as a job: every trace step becomes events as it happens."""

    def __init__(self, services: Services, offline: bool = False) -> None:
        self.svc, self.offline = services, offline

    async def run(self, job: Job) -> dict[str, Any]:
        from app.evolution import agent as A
        from app.evolution.engine import EvoEngine

        svc, doc = self.svc, job.doc
        eng = EvoEngine(svc, offline=self.offline)
        cfg = A.settings()
        if eng.mock:
            inner: Any = A.PolicyBrain(A.default_policy)
        else:
            eng._guard()
            baseten = getattr(eng.spark, "baseten", None)
            if baseten is None:
                raise RunFailed("UPSTREAM_ERROR", "The agent model is not configured on this server.", False)
            inner = A.SparkOpenBrain(baseten, int(cfg["max_tokens"]))
        brain = DeadlineBrain(inner, job)
        image_dir = svc.settings.resolved_local_dir() / "agent_runs" / job.run_id
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        urls: dict[str, str] = {}
        flags = {"render_cap": False, "call_cap": False}

        async def upload(iid: str, path: Path, ctype: str) -> str:
            if iid not in urls:
                ext = EXT.get(ctype, path.suffix.lstrip(".") or "webp")
                urls[iid] = await job.runner.files.put(f"runs/{job.run_id}/{iid}.{ext}", path.read_bytes(), ctype)
            return urls[iid]

        async def handle(item: dict[str, Any]) -> None:
            s, res = item["step"], item["step"].get("result") or {}
            ok = bool(s.get("ok", True))
            err = None if ok else (res.get("error") or ((res.get("errors") or [{}])[0].get("code")))
            await job.emit("step", n=s.get("n"), tool=s.get("tool"), args=short_args(s.get("arguments")),
                           summary=s.get("summary", ""), reason=s.get("reason", ""), cards=s.get("cards") or [],
                           ok=ok, error=err)
            for im in item["images"]:
                await job.emit("render", n=s.get("n"), imageId=im["id"], url=await upload(im["id"], im["path"],
                                                                                         im["content_type"]),
                               kind=im["kind"], parent=im["parent"], method=im["method"],
                               rendersUsed=im["used"], rendersLeft=im["left"])
            if s.get("tool") in ("render", "edit") and ok and item["renders"] >= cfg["max_renders"] \
                    and not flags["render_cap"]:
                flags["render_cap"] = True
                await job.cap("renders", cfg["max_renders"])
            if s.get("tool") == "inspect" and ok:
                fails, hidden = visible(res.get("failures"))
                await job.emit("inspect", n=s.get("n"), imageId=res.get("image_id"), verdict=res.get("verdict"),
                               failures=fails, hiddenChecks=hidden, bestSoFar=res.get("best_so_far"),
                               rule=res.get("rule"))
            if (s.get("n") or 0) >= cfg["max_tool_calls"] and not flags["call_cap"]:
                flags["call_cap"] = True
                await job.cap("tool_calls", cfg["max_tool_calls"])

        async def consume() -> None:
            while True:
                item = await queue.get()
                try:
                    await handle(item)
                except Exception:  # noqa: BLE001 - one bad event must not stall the run
                    log.exception("run %s: event for step %s failed", job.run_id, item["step"].get("n"))
                finally:
                    queue.task_done()

        def on_step(run: Any, step: dict[str, Any]) -> None:
            """Sync (the engine's hook): capture what the events need now; the consumer emits them in order."""
            res = step.get("result") or {}
            new: list[dict[str, Any]] = []
            if step.get("tool") in ("render", "edit") and step.get("ok"):
                ids = [i for i in (res.get("host_image_id"), res.get("image_id")) if i]
                for iid in ids:
                    im = run.state.images[iid]
                    is_render = im.kind in ("render", "growth_host")
                    used = res.get("renders_used") if is_render else None
                    new.append({"id": iid, "path": im.path, "content_type": im.content_type, "kind": im.kind,
                                "parent": im.parent, "method": (step.get("arguments") or {}).get("method", "edit"),
                                "used": used,
                                "left": (cfg["max_renders"] - used) if is_render and used is not None else None})
            queue.put_nowait({"step": step, "images": new, "renders": run.state.renders})

        async def flush() -> None:
            await queue.join()

        job.extra["flush"] = flush

        async def ask(question: str, options: list[str]) -> str | None:
            await flush()
            n = brain.run.state.calls if brain.run is not None else None
            return await job.ask("host_tie", question, [str(o) for o in options], n)

        consumer = asyncio.create_task(consume())
        try:
            result, run = await eng.agent_fuse(doc["sire"]["commonName"], doc["dam"]["commonName"], doc["mode"],
                                               brain=brain, ask=ask, image_dir=image_dir, on_step=on_step)
            await flush()
            if not result.get("genome"):
                raise RunFailed("UPSTREAM_ERROR", "The run ended without an image, so nothing was saved. Try again "
                                "in a few minutes.", True)
            return await self._finish(job, result, run, upload, brain.fired)
        finally:
            consumer.cancel()
            shutil.rmtree(image_dir, ignore_errors=True)

    async def _finish(self, job: Job, result: dict[str, Any], run: Any, upload: Any, timed_out: bool) -> dict[str, Any]:
        svc, files = self.svc, job.runner.files
        card, plan = result["card"], result["genome"]
        images = []
        for iid in run.state.order:
            im = run.state.images[iid]
            images.append({"imageId": iid, "url": await upload(iid, im.path, im.content_type), "kind": im.kind,
                           "verdict": (im.inspect or {}).get("verdict")})
        overlay = None
        okey = (card.get("anatomy_map") or {}).get("overlay_key")
        if okey:
            try:
                overlay = await files.put_jpeg(f"runs/{job.run_id}/anatomy.jpg", await svc.storage.get(okey))
            except ChimeraError:
                log.warning("run %s: anatomy overlay %s missing", job.run_id, okey)
        trace = json.loads(json.dumps(run.trace, default=str))
        asked = any(s.get("tool") == "ask_user" and (s.get("result") or {}).get("answer") for s in trace)
        cid = new_id("crt")
        view = build_creature(
            creature_id=cid, created_at=now_iso(), sire=job.doc["sire"], dam=job.doc["dam"], mode=job.doc["mode"],
            card=card, plan=plan, route_mode=(result.get("route") or {}).get("mode"), image_id=result["image_id"],
            trace=trace, images=images, overlay_url=overlay, run_id=job.run_id, host_by="user" if asked else None,
            stats={"renders": run.state.renders, "edits": run.state.edits, "toolCalls": run.state.calls,
                   "seconds": round(time.monotonic() - job.t0, 1)})
        await job.runner.creatures.save(view, "run", trace=trace, engineCreatureId=plan.get("id"),
                                        owner=job.doc.get("owner"))
        fails, hidden = visible(card.get("remaining_failures"))
        stop = (card.get("agent") or {}).get("stop") or "finalized"
        if timed_out:
            stop = f"{stop} at the {round(svc.settings.evo_run_soft_seconds / 60)}-minute time cap"
        return {"creatureId": cid, "imageId": result["image_id"], "imageUrl": view["imageUrl"],
                "remainingFailures": fails, "hiddenChecks": hidden,
                "agree": bool((card.get("final_choice") or {}).get("agree", True)), "stop": stop}


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
        from app.evolution.live import RetryingImageGen

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
        trace = [{"n": 1, "tool": "render", "arguments": {"prompt": prompt}, "summary": summary,
                  "reason": "prompt mode", "ok": True}]
        view = build_creature(
            creature_id=cid, created_at=now_iso(), sire=doc["sire"], dam=doc["dam"], mode=doc["mode"], card={},
            plan=record, route_mode=None, image_id="img1", trace=trace,
            images=[{"imageId": "img1", "url": url, "kind": "render", "verdict": None}], overlay_url=None,
            run_id=job.run_id, stats={"renders": 1, "edits": 0, "toolCalls": 1,
                                      "seconds": round(time.monotonic() - t0, 1)})
        if record["profile"] and record["profile"].get("name"):
            view["title"] = record["profile"]["name"]
        await job.runner.creatures.save(view, "run", trace=trace, owner=doc.get("owner"))
        return {"creatureId": cid, "imageId": "img1", "imageUrl": url, "remainingFailures": [], "hiddenChecks": 0,
                "agree": True, "stop": "prompt mode: one render", "title": view["title"]}
