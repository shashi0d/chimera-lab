"""The Lab after a Fusion run: every edit of a generated creature is a new version on the user's canvas.

A finished Fusion run becomes version 1 (`POST /evo/lab/versions/from-run`); Revise, Paint and Draw of any version make
a child version, so the canvas shows the whole path from the two animals to the final image. Each version keeps how it
was made and the creature's profile; its animal card (one per image) is made on demand in the background.

Everything here belongs to the signed-in user (app/auth.py). Image edits run as background jobs that survive the
request (and a page reload); each lab action counts against the user's daily lab budget and is refunded if it
fails."""

from __future__ import annotations

import asyncio
import io
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
from app.agentapi import edit_pipeline
from app.agentapi.caps import Caps, client_ip, day_key, resets_at
from app.agentapi.creature_ai import check_topic
from app.agentapi.files import EXT, content_type_for
from app.agentapi.routes import AgentApi, api
from app.auth import User, require_user
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/lab", tags=["lab"])
log = logging.getLogger(__name__)

VERSION_KIND = "lab_version"
GARDEN_PUBLIC = "public"  # doc["garden"] of a version shared to the Garden (a string, so the database can match it)
JOB_KIND = "lab_job"
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
    unlimited = not caps.enabled  # no limits: the counts are shown, the limits are null
    return JSONResponse({"used": mine, "limit": None if unlimited else caps.settings.evo_visitor_daily_runs,
                         "totalUsed": total, "totalLimit": None if unlimited else caps.settings.evo_daily_runs,
                         "resetsAt": resets_at()}, headers={"Cache-Control": "no-store"})


# ====================================================================== versions


def public_version(doc: dict[str, Any]) -> dict[str, Any]:
    view = {k: doc.get(k) for k in ("id", "parentId", "runId", "creatureId", "operation", "instruction", "imageUrl",
                                    "createdAt", "isFinal", "title", "style", "card", "profile",
                                    "saved", "savedAt", "workspaceId", "sharedAt")}
    view["shared"] = doc.get("garden") == GARDEN_PUBLIC
    return view


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
        parent = await a.services.db.get("assets", parent_id)
        if not parent or parent.get("kind") != VERSION_KIND or parent.get("owner") != user.id:
            break  # a deleted earlier image: the path starts at the oldest image that still exists
        chain.insert(0, parent)
    return chain


async def save_version(a: AgentApi, user: User, image: GeneratedImage, parent: dict[str, Any], operation: str,
                       instruction: str, reference_only: bool, prompt: str = "",
                       profile: dict[str, Any] | None = None, record: dict[str, Any] | None = None,
                       chain_depth: int = 0) -> dict[str, Any]:
    ext = EXT.get(image.content_type)
    if not ext:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The image provider returned an unsupported image format.", 502)
    version_id = new_id("labv")
    key = f"lab/{version_id}.{ext}"
    url = await a.files.put(key, image.data, image.content_type)
    doc = {"id": version_id, "kind": VERSION_KIND, "owner": user.id, "parentId": parent["id"],
           "runId": parent.get("runId"), "creatureId": parent.get("creatureId"), "title": parent.get("title"),
           "operation": operation, "instruction": instruction, "imageUrl": url, "imageKey": key,
           "responseId": image.response_id, "referenceOnly": reference_only, "chainDepth": chain_depth, "createdAt": now_iso(), "isFinal": False,
           "style": parent.get("style"), "profile": profile or parent.get("profile"),
           "workspaceId": parent.get("workspaceId"),
           # How this image was made, kept so later steps (the animal card) can build on it.
           "generation": {"operation": operation, "instruction": instruction, "prompt": prompt,
                          "model": image.model, **({"edit": record} if record else {}),
                          "parents": (parent.get("generation") or {}).get("parents")}}
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
           "instruction": f"{(run.get('sire') or {}).get('commonName')} × {(run.get('dam') or {}).get('commonName')}",
           "imageUrl": view["imageUrl"],
           "imageKey": _file_key(a, view["imageUrl"]), "responseId": None, "referenceOnly": True,
           "createdAt": now_iso(), "isFinal": False, "style": run.get("style"),
           "generation": _run_generation(run, view), "profile": (view.get("plan") or {}).get("profile"),
           "workspaceId": run.get("workspaceId") or (body.get("workspaceId") if isinstance(body, dict) else None)}
    await a.services.db.put("assets", version_id, doc)
    return JSONResponse(public_version(doc), status_code=201)


def _run_generation(run: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """How a Fusion run made its image (prompt, style, parents, references, profile), kept with V1."""
    return dict(view.get("plan") or {"operation": "fusion", "style": run.get("style"),
                                      "parents": [run.get("sire"), run.get("dam")]})


def parent_animals(doc: dict[str, Any]) -> list[str]:
    """The creature's parent animals, from its generation record (an edit keeps its Fusion's parents)."""
    return edit_pipeline.parent_animals(doc)


async def _edit_profile(a: AgentApi, doc: dict[str, Any], image: bytes, operation: str,
                        instruction: str) -> dict[str, Any] | None:
    """The edited creature's entry: the previous one updated for this change (the name is kept)."""
    from app.agentapi.creature_ai import make_profile

    previous = doc.get("profile")
    context = {"previous": previous, "change": {"operation": operation, "instruction": instruction},
               "style": doc.get("style"), "parents": (doc.get("generation") or {}).get("parents")}
    profile = await make_profile(a.services.vision, image, context)
    if profile and previous and previous.get("name"):
        profile["name"] = previous["name"]
    return profile or previous


def _with_background(settings: Any, prompt: str) -> str:
    rule = str(settings.evo_fusion_background).strip()
    return f"{prompt} {rule}" if rule else prompt


def _instruction(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_INSTRUCTION:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the change in up to 2,000 characters.", 422)
    return value.strip()


# Chain an edit on the provider's previous response (the model keeps its own context) only when the stored image is
# exactly that response, and only for a few turns in a row: drift adds up along a chain.
MAX_CHAIN = 4


def chain_for(doc: dict[str, Any]) -> str | None:
    if doc.get("referenceOnly") or not doc.get("responseId") or int(doc.get("chainDepth") or 0) >= MAX_CHAIN:
        return None
    return str(doc["responseId"])


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
    await check_topic(a.services.vision, [], [instruction], "instruction")
    day = await lab(request).caps.charge(user.id)

    async def work(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Reading your request")
        original = await version_image(a, doc)
        chain = chain_for(doc)
        await stage("Revising the image")
        res = await edit_pipeline.revise(a.services, a.settings, doc, original, instruction, chain)
        await stage("Updating the creature's entry")
        profile = await _edit_profile(a, doc, res.image.data, "revise", instruction)
        await stage("Saving the new version")
        # The stored image is exactly the provider's response, so its children can chain on that response.
        depth = int(doc.get("chainDepth") or 0) + 1 if chain else 0
        return await save_version(a, user, res.image, doc, "revise", instruction, reference_only=False,
                                  prompt=res.prompt, profile=profile, record=res.record, chain_depth=depth)

    return await start_job(request, user, day, "revise", version_id, instruction, work)


def composite_region(original: bytes, candidate: bytes, mask: bytes) -> bytes:
    """Blend inside the painted alpha only (all pixels outside it unchanged). The endpoint calls it with the original
    twice to check the mask before spending a model call; the edit itself is put back by edit_pipeline."""
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
    await check_topic(a.services.vision, [], [instruction], "instruction")
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
        await stage("Reading the painted area")
        res = await edit_pipeline.paint(a.services, a.settings, doc, original, mask, instruction)
        await stage("Updating the creature's entry")
        profile = await _edit_profile(a, doc, res.image.data, "paint", instruction)
        # A blended image is not the provider's response; later edits must use it as a reference.
        return await save_version(a, user, res.image, doc, "paint", instruction, reference_only=res.reference_only,
                                  prompt=res.prompt, profile=profile, record=res.record)

    return await start_job(request, user, day, "paint", version_id, instruction, work)


def composite_sketch(original: bytes, sketch: bytes) -> bytes:
    """The creator's drawing (a transparent layer) laid over the image, at the image's size, as a PNG."""
    try:
        with Image.open(io.BytesIO(original)) as base_img, Image.open(io.BytesIO(sketch)) as layer_img:
            base = base_img.convert("RGBA")
            layer = layer_img.convert("RGBA").resize(base.size)
    except (UnidentifiedImageError, OSError) as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "The drawing could not be read. Draw again.", 422) from exc
    if layer.getchannel("A").getbbox() is None:
        raise _err(ErrorCode.VALIDATION_FAILED, "Draw on the image first.", 422)
    out = io.BytesIO()
    Image.alpha_composite(base, layer).convert("RGB").save(out, "PNG")
    return out.getvalue()


@router.post("/versions/{version_id}/sketch")
async def sketch(version_id: str, request: Request) -> JSONResponse:
    """Draw on an image and generate from the drawing: the model turns the marks into parts of the creature."""
    a = api(request)
    user, _ = await _charge(request)
    doc = await get_version(a, version_id, user)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > a.settings.evo_max_upload_bytes + 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The drawing is too large.", 413)
    try:
        form = await request.form(max_files=1, max_fields=2)
    except Exception as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send a drawing and, if you like, a note.", 422) from exc
    raw = form.get("instruction")
    instruction = " ".join(str(raw).split())[:MAX_INSTRUCTION] if isinstance(raw, str) else ""
    if instruction:
        await check_topic(a.services.vision, [], [instruction], "instruction")
    upload = form.get("sketch")
    if not isinstance(upload, UploadFile):
        raise _err(ErrorCode.VALIDATION_FAILED, "Draw on the image first.", 422)
    drawing = await upload.read(a.settings.evo_max_upload_bytes + 1)
    await upload.close()
    if len(drawing) > a.settings.evo_max_upload_bytes:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The drawing is too large.", 413)
    original = await version_image(a, doc)
    await asyncio.to_thread(composite_sketch, original, drawing)  # validate before spending a call
    day = await lab(request).caps.charge(user.id)

    async def work(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Reading your drawing")
        res = await edit_pipeline.sketch(a.services, a.settings, doc, original, drawing, instruction)
        await stage("Updating the creature's entry")
        profile = await _edit_profile(a, doc, res.image.data, "sketch", instruction or "a drawn change")
        await stage("Saving the new version")
        return await save_version(a, user, res.image, doc, "sketch", instruction or "Drawn change",
                                  reference_only=res.reference_only, prompt=res.prompt, profile=profile,
                                  record=res.record)

    return await start_job(request, user, day, "sketch", version_id, instruction or "Drawn change", work)


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


def card_task_key(version_id: str) -> str:
    return f"card:{version_id}"


def card_is_live(request: Request, card: dict[str, Any] | None, version_id: str) -> bool:
    """A card that is ready, or running in this process (a card whose task is gone was interrupted)."""
    from app.agentapi.animal_card import is_stale

    if not card or card.get("status") not in ("ready", "running"):
        return False
    if card.get("status") == "ready":
        return True
    return not is_stale(card, api(request).settings.lab_job_stale_seconds) and         card_task_key(version_id) in lab(request).tasks


async def start_card(request: Request, user: User, doc: dict[str, Any]) -> dict[str, Any]:
    """Make the image's card in the background (one per image); returns the card as it is now."""
    from app.agentapi.animal_card import build_card, new_card

    a, state = api(request), lab(request)
    version_id = doc["id"]
    if card_is_live(request, doc.get("card"), version_id):
        return doc["card"]
    day = await state.caps.charge(user.id)
    doc["card"] = new_card()
    await a.services.db.put("assets", version_id, doc)

    async def run() -> None:
        result: dict[str, Any] = {}
        try:
            async with charged_slot(request, user.id, day):
                image = await version_image(a, doc)
                result = await build_card(a, doc, image)
        except asyncio.CancelledError:
            result = {"status": "failed", "error": INTERRUPTED, "profile": None, "angles": []}
            raise
        except Exception:
            log.exception("animal card %s failed", version_id)
            result = {"status": "failed", "error": "The card could not be made. Try again.", "profile": None,
                      "angles": []}
        finally:
            fresh = await a.services.db.get("assets", version_id)
            if fresh is not None:  # the image may have been deleted meanwhile
                fresh["card"] = {**fresh.get("card", {}), **result}
                if result.get("profile") and not fresh.get("profile"):
                    fresh["profile"] = result["profile"]
                await a.services.db.put("assets", version_id, fresh)
            state.tasks.pop(card_task_key(version_id), None)

    state.tasks[card_task_key(version_id)] = asyncio.create_task(run(), name=f"card-{version_id}")
    return doc["card"]


@router.post("/versions/{version_id}/card")
async def animal_card(version_id: str, request: Request) -> JSONResponse:
    """The animal card (one per image, made in the background): asking again returns the same card; only a failed or
    interrupted card is made again."""
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    if card_is_live(request, doc.get("card"), version_id):
        return JSONResponse(doc["card"], status_code=200, headers={"Cache-Control": "no-store"})
    await _charge(request)
    card = await start_card(request, user, doc)
    return JSONResponse(card, status_code=202, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/card")
async def saved_card(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    user, _ = await _user(request)
    doc = await get_version(a, version_id, user)
    card = doc.get("card")
    if card and card.get("status") == "running" and not card_is_live(request, card, version_id):
        card = {**card, "status": "failed", "error": INTERRUPTED}
    return JSONResponse({"card": card}, headers={"Cache-Control": "no-store"})
