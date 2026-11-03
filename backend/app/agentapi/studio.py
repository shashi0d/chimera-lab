"""Creator-led concept and revision demo, separate from the anatomy-plan engine."""
from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError
from starlette.datastructures import UploadFile

from app.agentapi import uploads as U
from app.agentapi.files import EXT
from app.agentapi.routes import _clean_name, _err, _visitor, api
from app.models.schemas import ErrorCode
from app.errors import ChimeraError
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/studio", tags=["studio"])
log = logging.getLogger(__name__)


def public_job(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("id", "operation", "status", "stage", "createdAt", "updatedAt", "result", "error")}


async def start_background(request: Request, visitor: str, operation: str,
                           work: Callable[[Callable[[str], Awaitable[None]]], Awaitable[dict[str, Any]]]) -> JSONResponse:
    """Keep a paid operation alive independently of its initiating HTTP connection."""
    a = api(request)
    job_id = new_id("studiojob")
    doc: dict[str, Any] = {"id": job_id, "kind": "studio_job", "visitor": visitor, "operation": operation,
                           "status": "queued", "stage": "Waiting for a workspace slot", "createdAt": now_iso(),
                           "updatedAt": now_iso(), "result": None, "error": None}

    async def save(**fields: Any) -> None:
        doc.update(fields, updatedAt=now_iso())
        await a.services.db.put("assets", job_id, doc)

    async def stage(message: str) -> None:
        await save(status="running", stage=message)

    async def run() -> None:
        try:
            async with request.app.state.studio_slots:
                await stage("Starting")
                result = await work(stage)
                await save(status="succeeded", stage="Ready", result=result)
        except asyncio.CancelledError:
            await save(status="interrupted", stage="Interrupted", error="The server stopped while this was running. Please try again.")
            raise
        except ChimeraError as exc:
            await save(status="failed", stage="Failed", error=exc.message)
        except Exception:
            log.exception("Studio job %s failed", job_id)
            await save(status="failed", stage="Failed", error="The operation failed. Please try again.")
        finally:
            request.app.state.studio_tasks.pop(job_id, None)

    await save()
    task = asyncio.create_task(run(), name=job_id)
    request.app.state.studio_tasks[job_id] = task
    return JSONResponse(public_job(doc), status_code=202)


@router.get("/jobs")
async def jobs(request: Request) -> JSONResponse:
    a = api(request)
    visitor, _ = _visitor(request, a)
    docs = [d for d in await a.services.db.list("assets", "visitor", visitor) if d.get("kind") == "studio_job"]
    # Local storage is single-process. A nonterminal job missing from this process was interrupted by a restart.
    if a.services.local_backend:
        for doc in docs:
            if doc.get("status") in ("queued", "running") and doc["id"] not in request.app.state.studio_tasks:
                doc.update(status="interrupted", stage="Interrupted", updatedAt=now_iso(),
                           error="The server stopped while this was running. Please try again.")
                await a.services.db.put("assets", doc["id"], doc)
    docs.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""), reverse=True)
    return JSONResponse({"jobs": [public_job(d) for d in docs[:20]]}, headers={"Cache-Control": "no-store"})


async def creative_direction(settings: Any, names: list[str], brief: str) -> str:
    """A collaborator suggests phrasing; the creator's original words remain authoritative."""
    if settings.chimera_mode == "mock":
        return "Create a coherent, imaginative creature concept that follows the creator's direction."
    from app.adapters.baseten.client import BasetenEvoSpark

    brain = BasetenEvoSpark(settings)
    result = await brain.chat("studio_direction", {
        "messages": [
            {"role": "system", "content": "You are a creature concept artist collaborating with a human. Write a concise image-generation direction based on their exact request. Preserve all explicitly requested anatomy, positions and counts. Do not impose biological feasibility or invent conflicting anatomy. Output only the direction."},
            {"role": "user", "content": json.dumps({"animals": names, "creator_brief": brief}, ensure_ascii=False)},
        ],
        "max_tokens": 4096,
    })
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content")
    if choice.get("finish_reason") not in (None, "stop") or not isinstance(text, str) or not text.strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, "The creative collaborator did not return a complete direction. Please try again.", 502)
    return text.strip()[:3000]


def public_version(doc: dict[str, Any]) -> dict[str, Any]:
    return {key: doc.get(key) for key in ("id", "parentId", "imageUrl", "instruction", "direction", "createdAt", "mode")}


async def save_image(a: Any, image: Any, visitor: str, instruction: str, direction: str, parent_id: str | None,
                     reference_only: bool = False) -> dict[str, Any]:
    if not image.response_id:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The image provider did not return an editable response. Please try again.", 502)
    version_id = new_id("studio")
    ext = EXT.get(image.content_type)
    if not ext:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The image provider returned an unsupported image format.", 502)
    image_key = f"studio/{version_id}.{ext}"
    url = await a.files.put(image_key, image.data, image.content_type)
    doc = {"id": version_id, "parentId": parent_id, "imageUrl": url, "instruction": instruction,
           "direction": direction, "createdAt": now_iso(), "mode": a.settings.chimera_mode,
           "responseId": image.response_id, "imageKey": image_key, "visitor": visitor, "kind": "studio_version",
           "referenceOnly": reference_only}
    await a.services.db.put("assets", version_id, doc)
    return public_version(doc)


async def get_version(a: Any, version_id: str, visitor: str) -> dict[str, Any]:
    doc = await a.services.db.get("assets", version_id)
    if not doc or doc.get("visitor") != visitor or not doc.get("responseId") or not str(doc.get("id", "")).startswith("studio_"):
        raise _err(ErrorCode.NOT_FOUND, "This draft is unavailable in this session.", 404)
    return doc


async def version_image(a: Any, doc: dict[str, Any]) -> bytes:
    key = doc.get("imageKey") or ("studio/" + str(doc["imageUrl"]).rsplit("/", 1)[-1])
    return await a.files.get(key)


def composite_region(original: bytes, candidate: bytes, mask: bytes) -> bytes:
    """Blend inside the painted alpha only. All pixels outside that alpha remain unchanged."""
    try:
        with Image.open(io.BytesIO(original)) as src, Image.open(io.BytesIO(candidate)) as edited, Image.open(io.BytesIO(mask)) as painted:
            src.load(); edited.load(); painted.load()
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
            result = Image.composite(overlay, base, feather)
            out = io.BytesIO()
            result.save(out, format="PNG")
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Paint a nonempty region on the selected image and try again.", 422) from exc


@router.get("/versions")
async def versions(request: Request) -> JSONResponse:
    a = api(request)
    visitor, _ = _visitor(request, a)
    docs = await a.services.db.list("assets", "visitor", visitor)
    rows = [public_version(d) for d in docs if str(d.get("id", "")).startswith("studio_") and d.get("responseId")]
    rows.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""))
    return JSONResponse({"versions": rows}, headers={"Cache-Control": "no-store"})


async def review_image(settings: Any, image: bytes, brief: str, change: str) -> dict[str, str]:
    """Observe without the brief first, then suggest options with the creator's intent in view."""
    if settings.chimera_mode == "mock":
        return {"observation": "Mock preview: visual inspection is not available in mock mode.",
                "suggestions": "Describe what you want to change in the revision field."}
    from app.evolution.live import LiveEvoSpark
    from app.adapters.baseten.client import BasetenEvoSpark

    observation = await LiveEvoSpark(settings).describe(image)
    description = str(observation.get("description") or "").strip()
    if not description:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The visual reviewer could not describe this image.", 502)
    brain = BasetenEvoSpark(settings)
    result = await brain.chat("studio_review", {"messages": [
        {"role": "system", "content": "You are a collaborative creature concept artist. Compare an independent visual description to the creator's intent. Give up to three concise, concrete, optional revision ideas. Mention apparent mismatches cautiously because the visual description can be wrong. Do not claim to see details not in the description, impose biological rules, or decide what the creator should choose."},
        {"role": "user", "content": json.dumps({"creator_brief": brief, "latest_revision": change,
                                                  "visual_observation": observation}, ensure_ascii=False)},
    ], "max_tokens": 4096})
    choice = (result.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content")
    if choice.get("finish_reason") not in (None, "stop") or not isinstance(text, str) or not text.strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, "The creative collaborator did not return a complete review.", 502)
    return {"observation": description[:3000], "suggestions": text.strip()[:4000]}


@router.post("/versions/{version_id}/review")
async def review(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    a.caps.rate_limit(ip)
    await a.caps.check(visitor)
    selected = await get_version(a, version_id, visitor)
    root = selected
    seen: set[str] = set()
    while root.get("parentId"):
        parent_id = str(root["parentId"])
        if parent_id in seen or len(seen) >= 100:
            raise _err(ErrorCode.VALIDATION_FAILED, "This draft's history is invalid.", 422)
        seen.add(parent_id)
        root = await get_version(a, parent_id, visitor)
    image = await version_image(a, selected)
    await a.caps.take(visitor)
    async with request.app.state.studio_slots:
        result = await review_image(a.settings, image, str(root.get("instruction") or ""),
                                    str(selected.get("instruction") or "") if selected.get("parentId") else "")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.post("/concept")
async def concept(request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    a.caps.rate_limit(ip)
    await a.caps.check(visitor)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 2 * a.settings.evo_max_upload_bytes + 2 * 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, U.MSG_SIZE, 413)
    try:
        form = await request.form(max_files=2, max_fields=6)
    except Exception as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send two animal names or images and your idea.", 422) from exc
    brief = str(form.get("brief") or "").strip()
    if not brief or len(brief) > 2000:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe your creature in up to 2,000 characters.", 422)
    names: list[str] = []
    refs: list[bytes] = []
    labels: list[str] = []
    for index in (1, 2):
        name = _clean_name(form.get(f"animal{index}"), f"animal{index}")
        upload = form.get(f"image{index}")
        has_image = isinstance(upload, UploadFile) and bool(upload.filename or upload.size)
        if not name and not has_image:
            raise _err(ErrorCode.VALIDATION_FAILED, f"Add a name or image for animal {index}.", 422)
        names.append(name or f"animal {index} in its reference image")
        if has_image:
            data = await upload.read(a.settings.evo_max_upload_bytes + 1)
            await upload.close()
            refs.append(await U.prepare(data, f"animal{index}", a.services))
            labels.append(f"Reference image {len(refs)} depicts animal {index}: {names[-1]}.")
    await a.caps.take(visitor)
    async def render(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Developing your creative direction")
        direction = await creative_direction(a.settings, names, brief)
        prompt = ("Create one original chimera concept image, a single creature combining the following animals: "
                  + ", ".join(names) + ". " + " ".join(labels)
                  + "\nThe creator's exact brief is the highest authority for the creature's anatomy and appearance: "
                  + json.dumps(brief, ensure_ascii=False)
                  + "\nCreative collaborator's suggestions (ignore any that conflict with the creator's brief): " + direction)
        render_refs = refs
        if a.mock and not render_refs:
            # The mock renderer is an image compositor and needs input pixels even for named animals.
            from app.evolution.adapters import swatch
            render_refs = [swatch(name) for name in names]
        await stage("Generating your concept")
        image = await a.services.image_gen.generate(prompt, render_refs, "1:1")
        await stage("Saving your concept")
        return await save_image(a, image, visitor, brief, direction, None)
    if request.query_params.get("background") == "1":
        return await start_background(request, visitor, "concept", render)
    async with request.app.state.studio_slots:
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)


@router.post("/versions/{version_id}/revise")
async def revise(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    a.caps.rate_limit(ip)
    await a.caps.check(visitor)
    doc = await get_version(a, version_id, visitor)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the revision you want.", 422) from exc
    instruction = body.get("instruction") if isinstance(body, dict) else None
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 2000:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the revision in up to 2,000 characters.", 422)
    instruction = instruction.strip()
    await a.caps.take(visitor)
    async def render(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Revising the selected draft")
        refs = [await version_image(a, doc)] if doc.get("referenceOnly") else []
        image = await a.services.image_gen.generate(
            "Revise the selected image according to the creator's instruction. Preserve other details where possible. " + instruction,
            refs, "1:1", None if refs else doc["responseId"])
        await stage("Saving your revision")
        return await save_image(a, image, visitor, instruction, "", version_id)
    if request.query_params.get("background") == "1":
        return await start_background(request, visitor, "revision", render)
    async with request.app.state.studio_slots:
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)


@router.post("/versions/{version_id}/region")
async def region(version_id: str, request: Request) -> JSONResponse:
    from app.adapters.base import GeneratedImage

    a = api(request)
    visitor, ip = _visitor(request, a)
    a.caps.rate_limit(ip)
    await a.caps.check(visitor)
    doc = await get_version(a, version_id, visitor)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > a.settings.evo_max_upload_bytes + 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The painted mask is too large.", 413)
    try:
        form = await request.form(max_files=1, max_fields=2)
    except Exception as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send a painted mask and an edit instruction.", 422) from exc
    instruction = str(form.get("instruction") or "").strip()
    upload = form.get("mask")
    if not instruction or len(instruction) > 2000 or not isinstance(upload, UploadFile):
        raise _err(ErrorCode.VALIDATION_FAILED, "Paint a region and describe the change in up to 2,000 characters.", 422)
    mask = await upload.read(a.settings.evo_max_upload_bytes + 1)
    await upload.close()
    if len(mask) > a.settings.evo_max_upload_bytes:
        raise _err(ErrorCode.FILE_TOO_LARGE, "The painted mask is too large.", 413)
    original = await version_image(a, doc)
    await asyncio.to_thread(composite_region, original, original, mask)  # validate before spending a call
    await a.caps.take(visitor)

    async def render(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Generating an edit for your painted region")
        refs = [original] if doc.get("referenceOnly") else []
        candidate = await a.services.image_gen.generate(
            "Edit the selected image as follows, keeping its framing and everything else as similar as possible: " + instruction,
            refs, "1:1", None if refs else doc["responseId"])
        await stage("Blending the painted region")
        merged = await asyncio.to_thread(composite_region, original, candidate.data, mask)
        image = GeneratedImage(merged, "image/png", candidate.model, candidate.response_id)
        # The saved composite is not identical to the provider's response; future edits must use it as a reference.
        return await save_image(a, image, visitor, instruction, "", version_id, reference_only=True)

    if request.query_params.get("background") == "1":
        return await start_background(request, visitor, "region", render)
    async with request.app.state.studio_slots:
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)
