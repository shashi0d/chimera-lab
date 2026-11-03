"""The Lab after a Fusion run: every edit of a generated creature is a new version on the user's canvas.

One flow (FLORA-style lineage): a finished Fusion run becomes version 1 (`POST /evo/lab/versions/from-run`); a
revision or a painted edit of any version makes a child version, so the user's canvas shows the whole path from the
two animals to the final image. A visual review and a collaborator chat help decide the next edit; the
collaborator only proposes, the user runs. A final version can be published to the gallery with its whole path.

Everything here belongs to the signed-in user (app/auth.py). Image edits run as background jobs that survive the
request (and a page reload); each lab action counts against the user's daily lab budget and is refunded if it
fails."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError
from starlette.datastructures import UploadFile

from app.adapters.base import GeneratedImage
from app.agentapi.caps import Caps, client_ip, day_key, resets_at
from app.agentapi.files import EXT, content_type_for
from app.agentapi.routes import AgentApi, api
from app.auth import User, require_user
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/lab", tags=["lab"])
log = logging.getLogger(__name__)

VERSION_KIND = "lab_version"
JOB_KIND = "lab_job"
PUBLICATION_KIND = "lab_publication"
CAP_MESSAGE = "Today's lab action limit is reached. More actions are available at 00:00 UTC."
INTERRUPTED = "The server stopped while this was running. Please try again."
MAX_INSTRUCTION = 2000


def _err(code: ErrorCode, message: str, status: int) -> ChimeraError:
    return ChimeraError(code, message, retryable=False).with_status(status)


# ====================================================================== caps, slots, background jobs


class LabCaps(Caps):
    """A separate daily budget for lab actions (edits, reviews, collaborator messages), per user and in total."""

    def __init__(self, db: Any, settings: Any) -> None:
        super().__init__(db, settings.model_copy(update={
            "evo_daily_runs": settings.lab_daily_actions,
            "evo_visitor_daily_runs": settings.lab_user_daily_actions,
            "evo_runs_per_minute_per_ip": settings.lab_actions_per_minute_per_ip,
        }))

    def _keys(self, visitor: str, day: str | None = None) -> tuple[str, str]:
        day = day or day_key()
        return f"lab_actions:{day}", f"lab_actions:{day}:u:{visitor}"

    async def charge(self, user_id: str) -> str:
        """Take one action and return the UTC day it was counted on, for a refund if the action fails."""
        day = day_key()
        try:
            await self.take(user_id)
        except ChimeraError as exc:
            if exc.code == ErrorCode.CAP_REACHED:
                exc.message = CAP_MESSAGE
            raise
        return day

    async def check(self, visitor: str) -> None:
        try:
            await super().check(visitor)
        except ChimeraError as exc:
            if exc.code == ErrorCode.CAP_REACHED:
                exc.message = CAP_MESSAGE
            raise

    async def refund(self, user_id: str, day: str) -> None:
        """Give back an action that did not complete, on the day it was counted."""
        total, mine = self._keys(user_id, day)
        if await self.db.incr(mine, 0) > 0:
            await self.db.incr(mine, -1)
        if await self.db.incr(total, 0) > 0:
            await self.db.incr(total, -1)


@dataclass
class LabState:
    caps: LabCaps
    slots: asyncio.Semaphore
    tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


def lab(request: Request) -> LabState:
    return request.app.state.lab  # type: ignore[no-any-return]


async def _user(request: Request) -> tuple[User, str]:
    user = await require_user(request)
    return user, client_ip(request, api(request).settings.evo_proxy_hops)


async def _charge(request: Request) -> tuple[User, str]:
    """Sign-in, the per-IP rate limit and the daily budget, before any work. Returns the user and the charge day."""
    user, ip = await _user(request)
    state = lab(request)
    state.caps.rate_limit(ip)
    await state.caps.check(user.id)
    return user, ip


@asynccontextmanager
async def charged_slot(request: Request, user_id: str, day: str) -> AsyncIterator[None]:
    """Hold a model slot for an action already charged on `day`. An action that fails or is cancelled is refunded."""
    state = lab(request)
    try:
        async with state.slots:
            yield
    except BaseException:
        await state.caps.refund(user_id, day)
        raise


def public_job(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("id", "operation", "status", "stage", "parentId", "instruction", "createdAt",
                                    "updatedAt", "result", "error")}


async def start_job(request: Request, user: User, day: str, operation: str, parent_id: str, instruction: str,
                    work: Callable[[Callable[[str], Awaitable[None]]], Awaitable[dict[str, Any]]]) -> JSONResponse:
    """Run a paid edit independently of its HTTP request (it survives the request and a page reload)."""
    a, state = api(request), lab(request)
    job_id = new_id("labjob")
    doc: dict[str, Any] = {"id": job_id, "kind": JOB_KIND, "owner": user.id, "operation": operation,
                           "parentId": parent_id, "instruction": instruction, "status": "queued",
                           "stage": "Waiting for a model slot", "createdAt": now_iso(), "updatedAt": now_iso(),
                           "result": None, "error": None}

    async def save(**fields: Any) -> None:
        doc.update(fields, updatedAt=now_iso())
        await a.services.db.put("assets", job_id, doc)

    async def stage(message: str) -> None:
        await save(status="running", stage=message)

    async def run() -> None:
        try:
            async with charged_slot(request, user.id, day):
                await stage("Starting")
                result = await work(stage)
                await save(status="succeeded", stage="Ready", result=result)
        except asyncio.CancelledError:
            await save(status="interrupted", stage="Interrupted", error=INTERRUPTED)
            raise
        except ChimeraError as exc:
            await save(status="failed", stage="Failed", error=exc.message)
        except Exception:
            log.exception("Lab job %s failed", job_id)
            await save(status="failed", stage="Failed", error="The edit failed. Please try again.")
        finally:
            state.tasks.pop(job_id, None)

    await save()
    state.tasks[job_id] = asyncio.create_task(run(), name=job_id)
    return JSONResponse(public_job(doc), status_code=202)


def job_is_stale(doc: dict[str, Any], stale_seconds: float, now: datetime | None = None) -> bool:
    stamp = doc.get("updatedAt") or doc.get("createdAt")
    try:
        updated = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return True  # an unreadable timestamp cannot prove the job is alive
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return ((now or datetime.now(UTC)) - updated).total_seconds() > stale_seconds


@router.get("/jobs")
async def jobs(request: Request) -> JSONResponse:
    a, state = api(request), lab(request)
    user, _ = await _user(request)
    docs = [d for d in await a.services.db.list("assets", "owner", user.id) if d.get("kind") == JOB_KIND]
    # A nonterminal job this process is not running was interrupted by a restart: at once with local storage
    # (single-process), else once it has had no update for longer than any stage takes (it may live elsewhere).
    for doc in docs:
        if doc.get("status") in ("queued", "running") and doc["id"] not in state.tasks:
            if a.services.local_backend or job_is_stale(doc, a.settings.lab_job_stale_seconds):
                doc.update(status="interrupted", stage="Interrupted", updatedAt=now_iso(), error=INTERRUPTED)
                await a.services.db.put("assets", doc["id"], doc)
    docs.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""), reverse=True)
    return JSONResponse({"jobs": [public_job(d) for d in docs[:30]]}, headers={"Cache-Control": "no-store"})


@router.get("/limits")
async def limits(request: Request) -> JSONResponse:
    user, _ = await _user(request)
    caps = lab(request).caps
    total, mine = await caps.used(user.id)
    return JSONResponse({"used": mine, "limit": caps.settings.evo_visitor_daily_runs,
                         "totalUsed": total, "totalLimit": caps.settings.evo_daily_runs,
                         "resetsAt": resets_at()}, headers={"Cache-Control": "no-store"})


# ====================================================================== workspace (the user's canvas)


def _workspace_key(user: User) -> str:
    return f"workspace:{user.id}"


@router.get("/workspace")
async def get_workspace(request: Request) -> JSONResponse:
    user, _ = await _user(request)
    doc = await api(request).services.db.get("graphs", _workspace_key(user))
    body = {"graph": doc.get("graph"), "revision": doc.get("revision", 0), "updatedAt": doc.get("updatedAt")} \
        if doc else {"graph": None, "revision": 0, "updatedAt": None}
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


@router.put("/workspace")
async def put_workspace(request: Request) -> JSONResponse:
    """Save the canvas (last write wins). The document is opaque here beyond its shape and size."""
    user, _ = await _user(request)
    a = api(request)
    raw = await request.body()
    if len(raw) > a.settings.lab_workspace_max_bytes:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The workspace is too large to save.", 413)
    try:
        body = json.loads(raw)
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the workspace as JSON.", 422) from exc
    graph = body.get("graph") if isinstance(body, dict) else None
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"),
                                                                                                    list):
        raise _err(ErrorCode.VALIDATION_FAILED, "The workspace needs nodes and edges.", 422)
    key = _workspace_key(user)
    old = await a.services.db.get("graphs", key)
    revision = int((old or {}).get("revision", 0)) + 1
    doc = {"owner": user.id, "graph": graph, "revision": revision, "updatedAt": now_iso()}
    await a.services.db.put("graphs", key, doc)
    return JSONResponse({"revision": revision, "updatedAt": doc["updatedAt"]}, headers={"Cache-Control": "no-store"})


# ====================================================================== versions


def public_version(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("id", "parentId", "runId", "creatureId", "operation", "instruction", "imageUrl",
                                    "createdAt", "isFinal", "publicationId", "title")}


async def get_version(a: AgentApi, version_id: str, user: User) -> dict[str, Any]:
    doc = await a.services.db.get("assets", version_id)
    if not doc or doc.get("kind") != VERSION_KIND or doc.get("owner") != user.id:
        raise _err(ErrorCode.NOT_FOUND, "This version is unavailable.", 404)
    return doc


async def version_image(a: AgentApi, doc: dict[str, Any]) -> bytes:
    return await a.files.get(doc["imageKey"])


async def lineage(a: AgentApi, version: dict[str, Any], user: User) -> list[dict[str, Any]]:
    """The path from the Fusion version (first) to this one (last)."""
    chain = [version]
    seen: set[str] = {version["id"]}
    while chain[0].get("parentId"):
        parent_id = str(chain[0]["parentId"])
        if parent_id in seen or len(chain) > 200:
            raise _err(ErrorCode.VALIDATION_FAILED, "This version's history is invalid.", 422)
        seen.add(parent_id)
        chain.insert(0, await get_version(a, parent_id, user))
    return chain


async def save_version(a: AgentApi, user: User, image: GeneratedImage, parent: dict[str, Any], operation: str,
                       instruction: str, reference_only: bool) -> dict[str, Any]:
    ext = EXT.get(image.content_type)
    if not ext:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The image provider returned an unsupported image format.", 502)
    version_id = new_id("labv")
    key = f"lab/{version_id}.{ext}"
    url = await a.files.put(key, image.data, image.content_type)
    doc = {"id": version_id, "kind": VERSION_KIND, "owner": user.id, "parentId": parent["id"],
           "runId": parent.get("runId"), "creatureId": parent.get("creatureId"), "title": parent.get("title"),
           "operation": operation, "instruction": instruction, "imageUrl": url, "imageKey": key,
           "responseId": image.response_id, "referenceOnly": reference_only, "createdAt": now_iso(), "isFinal": False}
    await a.services.db.put("assets", version_id, doc)
    return public_version(doc)


@router.get("/versions")
async def versions(request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    rows = [public_version(d) for d in await a.services.db.list("assets", "owner", user.id)
            if d.get("kind") == VERSION_KIND]
    rows.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""))
    return JSONResponse({"versions": rows}, headers={"Cache-Control": "no-store"})


def _file_key(a: AgentApi, url: str) -> str:
    base = a.files.url("")
    if not url.startswith(base):
        raise _err(ErrorCode.NOT_FOUND, "This creature's image is unavailable.", 404)
    return url[len(base):]


@router.post("/versions/from-run")
async def from_run(request: Request) -> JSONResponse:
    """Version 1 of a finished Fusion run: the agent's final image, ready to edit. Idempotent per run."""
    a = api(request)
    user, _ = await _user(request)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the run id.", 422) from exc
    run_id = body.get("runId") if isinstance(body, dict) else None
    if not isinstance(run_id, str) or not run_id:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the run id.", 422)
    run = await a.store.get(run_id)
    if not run or run.get("owner") != user.id:
        raise ChimeraError(ErrorCode.RUN_NOT_FOUND, "This run doesn't exist.")
    if run.get("status") != "succeeded" or not run.get("creatureId"):
        raise _err(ErrorCode.VALIDATION_FAILED, "This run has not finished a creature yet.", 409)
    version_id = f"labv_run_{run_id}"
    existing = await a.services.db.get("assets", version_id)
    if existing:
        return JSONResponse(public_version(existing))
    creature = await a.services.db.get("creatures", run["creatureId"])
    view = (creature or {}).get("view") or {}
    if not view.get("imageUrl"):
        raise _err(ErrorCode.NOT_FOUND, "This creature's image is unavailable.", 404)
    doc = {"id": version_id, "kind": VERSION_KIND, "owner": user.id, "parentId": None, "runId": run_id,
           "creatureId": run["creatureId"], "title": view.get("title"), "operation": "fusion",
           "instruction": f"{view.get('title')} ({run.get('mode')})", "imageUrl": view["imageUrl"],
           "imageKey": _file_key(a, view["imageUrl"]), "responseId": None, "referenceOnly": True,
           "createdAt": now_iso(), "isFinal": False}
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc), status_code=201)


def _instruction(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_INSTRUCTION:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the change in up to 2,000 characters.", 422)
    return value.strip()


async def _generate(a: AgentApi, doc: dict[str, Any], prompt: str, refs: list[bytes]) -> GeneratedImage:
    """An edit of `doc`: chained on the provider's response when the stored image is exactly that response, else
    with the stored image as the reference."""
    from app.evolution.live import RetryingImageGen

    gen = RetryingImageGen(a.services.image_gen, a.settings)
    chain = doc.get("responseId") if not doc.get("referenceOnly") and not refs else None
    image = await gen.generate(prompt, refs, "1:1", chain)
    if not image.data:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The image provider returned no image. Please try again.", 502)
    return image


@router.post("/versions/{version_id}/revise")
async def revise(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _charge(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the revision you want.", 422) from exc
    instruction = _instruction(body.get("instruction") if isinstance(body, dict) else None)
    day = await lab(request).caps.charge(user.id)

    async def work(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Revising the image")
        refs = [await version_image(a, doc)] if doc.get("referenceOnly") else []
        image = await _generate(a, doc, "Revise the image according to the creator's instruction. Keep the creature, "
                                "framing and everything not mentioned as similar as possible. " + instruction, refs)
        await stage("Saving the new version")
        # The stored image is exactly the provider's response, so its children can chain on that response.
        return await save_version(a, user, image, doc, "revise", instruction, reference_only=False)

    return await start_job(request, user, day, "revise", version_id, instruction, work)


def composite_region(original: bytes, candidate: bytes, mask: bytes) -> bytes:
    """Blend inside the painted alpha only. All pixels outside that alpha remain unchanged."""
    try:
        with Image.open(io.BytesIO(original)) as src, Image.open(io.BytesIO(candidate)) as edited, \
                Image.open(io.BytesIO(mask)) as painted:
            src.load()
            edited.load()
            painted.load()
            if painted.format != "PNG" or painted.mode not in ("RGBA", "LA") or painted.size != src.size:
                raise ValueError("mask dimensions or format")
            alpha = painted.getchannel("A")
            if not alpha.getbbox():
                raise ValueError("empty mask")
            if abs((edited.width / edited.height) - (src.width / src.height)) > 0.01:
                raise ValueError("image aspect ratio changed")
            base = src.convert("RGB")
            overlay = edited.convert("RGB").resize(src.size, Image.Resampling.LANCZOS)
            # Soften only *within* the painted area; never modify pixels outside it.
            feather = ImageChops.darker(alpha, alpha.filter(ImageFilter.GaussianBlur(max(1, min(src.size) / 200))))
            out = io.BytesIO()
            Image.composite(overlay, base, feather).save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Paint a nonempty region on the image and try again.", 422) from exc


@router.post("/versions/{version_id}/paint")
async def paint(version_id: str, request: Request) -> JSONResponse:
    """Edit only a painted area: the model edits the whole image, which is blended into the painted pixels."""
    a = api(request)
    user, _ = await _charge(request)
    doc = await get_version(a, version_id, user)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > a.settings.evo_max_upload_bytes + 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The painted mask is too large.", 413)
    try:
        form = await request.form(max_files=1, max_fields=2)
    except Exception as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send a painted mask and an edit instruction.", 422) from exc
    instruction = _instruction(form.get("instruction"))
    upload = form.get("mask")
    if not isinstance(upload, UploadFile):
        raise _err(ErrorCode.VALIDATION_FAILED, "Paint the area to change.", 422)
    mask = await upload.read(a.settings.evo_max_upload_bytes + 1)
    await upload.close()
    if len(mask) > a.settings.evo_max_upload_bytes:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The painted mask is too large.", 413)
    original = await version_image(a, doc)
    await asyncio.to_thread(composite_region, original, original, mask)  # validate before spending a call
    day = await lab(request).caps.charge(user.id)

    async def work(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Editing the painted area")
        refs = [original] if doc.get("referenceOnly") else []
        candidate = await _generate(a, doc, "Edit the image as follows, keeping its framing and everything else as "
                                    "similar as possible: " + instruction, refs)
        await stage("Blending the painted area")
        merged = await asyncio.to_thread(composite_region, original, candidate.data, mask)
        image = GeneratedImage(merged, "image/png", candidate.model, candidate.response_id)
        # The saved composite is not the provider's response; later edits must use it as a reference.
        return await save_version(a, user, image, doc, "paint", instruction, reference_only=True)

    return await start_job(request, user, day, "paint", version_id, instruction, work)


@router.put("/versions/{version_id}/final")
async def mark_final(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether this version is final.", 422) from exc
    if not isinstance(body, dict) or not isinstance(body.get("isFinal"), bool):
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether this version is final.", 422)
    doc["isFinal"] = body["isFinal"]
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc), headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/download")
async def download(version_id: str, request: Request) -> Response:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    key = doc["imageKey"]
    return Response(await version_image(a, doc), media_type=content_type_for(key), headers={
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="chimera-{version_id}.{key.rsplit(".", 1)[-1]}"'})


# ====================================================================== review and collaborator


def _brief(chain: list[dict[str, Any]]) -> str:
    return str(chain[0].get("instruction") or "")


def _latest_change(chain: list[dict[str, Any]]) -> str:
    return str(chain[-1].get("instruction") or "") if len(chain) > 1 else ""


async def review_image(settings: Any, image: bytes, brief: str, change: str) -> dict[str, str]:
    """Observe without the brief first, then suggest options with the creator's intent in view."""
    from app.evolution.live import LiveEvoSpark, build_collaborator_chat

    observation = await LiveEvoSpark(settings).describe(image)
    description = str(observation.get("description") or "").strip()
    if not description:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The visual reviewer could not describe this image.", 502)
    brain = build_collaborator_chat(settings)
    result = await brain.chat("lab_review", {"messages": [
        {"role": "system", "content": "You are a collaborative creature concept artist. Compare an independent visual "
         "description to the creator's creature. Give up to three concise, concrete, optional revision ideas. Mention "
         "apparent mismatches cautiously because the visual description can be wrong. Do not claim to see details "
         "not in the description, impose biological rules, or decide what the creator should choose."},
        {"role": "user", "content": json.dumps({"creature": brief, "latest_change": change,
                                                "visual_observation": observation}, ensure_ascii=False)},
    ], "max_tokens": 4096})
    choice = (result.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content")
    if choice.get("finish_reason") not in (None, "stop") or not isinstance(text, str) or not text.strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator did not return a complete review.", 502)
    return {"observation": description[:3000], "suggestions": text.strip()[:4000]}


@router.post("/versions/{version_id}/review")
async def review(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _charge(request)
    doc = await get_version(a, version_id, user)
    chain = await lineage(a, doc, user)
    image = await version_image(a, doc)
    day = await lab(request).caps.charge(user.id)
    async with charged_slot(request, user.id, day):
        result = await review_image(a.settings, image, _brief(chain), _latest_change(chain))
    doc["review"] = result
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/review")
async def saved_review(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    return JSONResponse({"review": doc.get("review")}, headers={"Cache-Control": "no-store"})


TOOLS = [
    {"type": "function", "function": {
        "name": "propose_revision",
        "description": "Propose one editable image revision for the selected version; never run it yourself.",
        "parameters": {"type": "object", "properties": {"instruction": {"type": "string"},
                                                        "reason": {"type": "string"}},
                       "required": ["instruction", "reason"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "inspect_image",
        "description": "Inspect the selected image with a visual model when the user asks you to look or an "
                       "observation is needed. This performs a model call.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"],
                       "additionalProperties": False}}},
]


def _one_call(response: dict[str, Any], what: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    calls = message.get("tool_calls") or []
    if len(calls) > 1 or (calls and choice.get("finish_reason") not in (None, "tool_calls")):
        raise _err(ErrorCode.UPSTREAM_ERROR, f"The collaborator returned too many actions{what}.", 502)
    return choice, message, calls


def _arguments(call: dict[str, Any], what: str) -> dict[str, Any]:
    try:
        args = json.loads((call.get("function") or {}).get("arguments") or "{}")
    except (ValueError, TypeError) as exc:
        raise _err(ErrorCode.UPSTREAM_ERROR, f"The collaborator returned an invalid {what}.", 502) from exc
    if not isinstance(args, dict) or not isinstance(args.get("reason"), str) or not args["reason"].strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, f"The collaborator returned an invalid {what}.", 502)
    return args


async def plan_collaboration(settings: Any, brief: str, selected_instruction: str,
                             conversation: list[dict[str, str]], observation: str,
                             inspect: Callable[[], Awaitable[dict[str, str]]]) -> dict[str, Any]:
    """At most one visual inspection, then answer or propose an editable revision (never run it)."""
    from app.evolution.live import build_collaborator_chat

    brain = build_collaborator_chat(settings)
    prompt = ("You are a creative collaborator in Chimera Lab. The user directs an imaginary creature fused from two "
              "animals. You cannot see the selected image directly. A separate visual review may be provided; its "
              "observations are uncertain and can be wrong. Do not imply that you personally saw the image. You may "
              "propose one revision with the tools, or respond conversationally or ask a clarifying question. Never "
              "change the user's explicit anatomy or assert biological rules. A proposed revision is shown for the "
              "user to edit and run. For a request to visually inspect the image, call inspect_image. You can "
              "inspect at most once per message. For a concrete visual change, call propose_revision. Do not create "
              "or modify an image yourself. If the user mentions painting an area, explain they should use the "
              "Paint tool; you cannot paint a mask.\n"
              + json.dumps({"creature": brief, "selected_version_change": selected_instruction,
                            "independent_visual_observation": observation or None}, ensure_ascii=False))
    messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}, *conversation]
    response = await brain.chat("lab_collaborate", {"messages": messages, "tools": TOOLS, "tool_choice": "auto",
                                                    "max_tokens": 4096})
    choice, message, calls = _one_call(response, "")
    review: dict[str, str] | None = None
    steps: list[dict[str, str]] = []
    if calls and (calls[0].get("function") or {}).get("name") == "inspect_image":
        if not calls[0].get("id"):
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator could not inspect this image.", 502)
        reason = _arguments(calls[0], "inspection")["reason"].strip()[:500]
        review = await inspect()
        steps.append({"tool": "inspect_image", "reason": reason})
        messages.extend([{"role": "assistant", "content": message.get("content") or None, "tool_calls": calls},
                         {"role": "tool", "tool_call_id": calls[0]["id"],
                          "content": json.dumps(review, ensure_ascii=False)}])
        # A second inspection is intentionally unavailable in this turn.
        response = await brain.chat("lab_collaborate_after_inspection", {
            "messages": messages, "tools": TOOLS[:1], "tool_choice": "auto", "max_tokens": 4096})
        choice, message, calls = _one_call(response, " after inspection")
    text = str(message.get("content") or "").strip()[:3000]
    if not calls:
        if not text or choice.get("finish_reason") not in (None, "stop"):
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator did not finish its response. Please try again.", 502)
        return {"message": text, "action": None, "review": review, "steps": steps}
    fn = calls[0].get("function") or {}
    args = _arguments(calls[0], "action")
    if fn.get("name") != "propose_revision" or not isinstance(args.get("instruction"), str) \
            or not args["instruction"].strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an unsupported action. Please try again.", 502)
    action = {"type": "revise", "instruction": args["instruction"].strip()[:MAX_INSTRUCTION],
              "reason": args["reason"].strip()[:500]}
    return {"message": text or "Here's a possible next step for this version.", "action": action, "review": review,
            "steps": steps}


@router.post("/versions/{version_id}/collaborate")
async def collaborate(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _charge(request)
    selected = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send a message to the collaborator.", 422) from exc
    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list) or not 1 <= len(messages) <= 12:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send between one and twelve conversation messages.", 422)
    conversation = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant") \
                or not isinstance(item.get("content"), str) or not 1 <= len(item["content"].strip()) <= 2000:
            raise _err(ErrorCode.VALIDATION_FAILED, "Each message must contain up to 2,000 characters.", 422)
        conversation.append({"role": item["role"], "content": item["content"].strip()})
    if conversation[-1]["role"] != "user":
        raise _err(ErrorCode.VALIDATION_FAILED, "The last message must be yours.", 422)
    chain = await lineage(a, selected, user)

    async def inspect_selected() -> dict[str, str]:
        result = await review_image(a.settings, await version_image(a, selected), _brief(chain), _latest_change(chain))
        selected["review"] = result
        await a.services.db.put("assets", version_id, selected)
        return result

    day = await lab(request).caps.charge(user.id)
    async with charged_slot(request, user.id, day):
        result = await plan_collaboration(a.settings, _brief(chain), str(selected.get("instruction") or ""),
                                          conversation, str((selected.get("review") or {}).get("observation") or ""),
                                          inspect_selected)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


# ====================================================================== publishing to the gallery


def _publication_id(version_id: str) -> str:
    return f"pub_{version_id}"


@router.post("/versions/{version_id}/publish")
async def publish(version_id: str, request: Request) -> JSONResponse:
    """Put this version in the gallery with its whole path (animals, Fusion run, every edit)."""
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    title = (body.get("title") if isinstance(body, dict) else None) or doc.get("title") or "Untitled creature"
    if not isinstance(title, str) or len(title.strip()) > 80:
        raise _err(ErrorCode.VALIDATION_FAILED, "Give the creature a title of up to 80 characters.", 422)
    chain = await lineage(a, doc, user)
    run = await a.store.get(str(chain[0].get("runId") or "")) or {}
    source = await a.services.db.get("creatures", str(chain[0].get("creatureId") or "")) or {}
    pub_id = _publication_id(version_id)
    publication = {
        "kind": PUBLICATION_KIND, "creatureId": pub_id, "owner": user.id, "versionId": version_id,
        "createdAt": now_iso(), "title": title.strip(), "imageUrl": doc["imageUrl"],
        "sire": run.get("sire"), "dam": run.get("dam"), "mode": run.get("mode"),
        "sourceCreatureId": chain[0].get("creatureId"),
        "steps": [{"versionId": v["id"], "operation": v.get("operation"), "instruction": v.get("instruction"),
                   "imageUrl": v.get("imageUrl"), "createdAt": v.get("createdAt")} for v in chain],
    }
    await a.services.db.put("creatures", pub_id, publication)
    if source:
        source["publications"] = sorted({*source.get("publications", []), pub_id})
        await a.services.db.put("creatures", source["creatureId"], source)
    doc["publicationId"] = pub_id
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc), status_code=201)


@router.delete("/versions/{version_id}/publish")
async def unpublish(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    pub_id = doc.get("publicationId")
    if pub_id:
        pub = await a.services.db.get("creatures", pub_id)
        if pub:
            pub["unpublished"] = True
            await a.services.db.put("creatures", pub_id, pub)
            source = await a.services.db.get("creatures", str(pub.get("sourceCreatureId") or ""))
            if source:
                source["publications"] = [p for p in source.get("publications", []) if p != pub_id]
                await a.services.db.put("creatures", source["creatureId"], source)
        doc["publicationId"] = None
        await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc))
