"""Creator-led concept and revision demo, separate from the anatomy-plan engine."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from app.agentapi import uploads as U
from app.agentapi.files import EXT
from app.agentapi.routes import _clean_name, _err, _visitor, api
from app.models.schemas import ErrorCode
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/studio", tags=["studio"])


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


async def save_image(a: Any, image: Any, visitor: str, instruction: str, direction: str, parent_id: str | None) -> dict[str, Any]:
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
           "responseId": image.response_id, "imageKey": image_key, "visitor": visitor, "kind": "studio_version"}
    await a.services.db.put("assets", version_id, doc)
    return public_version(doc)


async def get_version(a: Any, version_id: str, visitor: str) -> dict[str, Any]:
    doc = await a.services.db.get("assets", version_id)
    if not doc or doc.get("visitor") != visitor or not doc.get("responseId") or not str(doc.get("id", "")).startswith("studio_"):
        raise _err(ErrorCode.NOT_FOUND, "This draft is unavailable in this session.", 404)
    return doc


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
    image_key = selected.get("imageKey")
    if not image_key:
        # Versions created by the original demo stored the URL but not the key.
        image_key = "studio/" + str(selected["imageUrl"]).rsplit("/", 1)[-1]
    image = await a.files.get(image_key)
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
    async with request.app.state.studio_slots:
        direction = await creative_direction(a.settings, names, brief)
        prompt = ("Create one original chimera concept image, a single creature combining the following animals: "
                  + ", ".join(names) + ". " + " ".join(labels)
                  + "\nThe creator's exact brief is the highest authority for the creature's anatomy and appearance: "
                  + json.dumps(brief, ensure_ascii=False)
                  + "\nCreative collaborator's suggestions (ignore any that conflict with the creator's brief): " + direction)
        if a.mock and not refs:
            # The mock renderer is an image compositor and needs input pixels even for named animals.
            from app.evolution.adapters import swatch
            refs = [swatch(name) for name in names]
        image = await a.services.image_gen.generate(prompt, refs, "1:1")
        version = await save_image(a, image, visitor, brief, direction, None)
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
    async with request.app.state.studio_slots:
        image = await a.services.image_gen.generate(
            "Revise the selected image according to the creator's instruction. Preserve other details where possible. " + instruction,
            [], "1:1", doc["responseId"])
        version = await save_image(a, image, visitor, instruction, "", version_id)
    return JSONResponse(version, status_code=201)
