"""Creator-led concept and revision demo, separate from the anatomy-plan engine."""
from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError
from starlette.datastructures import UploadFile

from app.agentapi import uploads as U
from app.agentapi.files import EXT
from app.agentapi.caps import Caps, day_key, resets_at
from app.agentapi.routes import _clean_name, _err, _visitor, api
from app.models.schemas import ErrorCode
from app.errors import ChimeraError
from app.util import new_id, now_iso

router = APIRouter(prefix="/evo/studio", tags=["studio"])
log = logging.getLogger(__name__)


class StudioCaps(Caps):
    """A separate, configurable action budget for the iterative studio."""
    def __init__(self, db: Any, settings: Any) -> None:
        super().__init__(db, settings.model_copy(update={
            "evo_daily_runs": settings.studio_daily_actions,
            "evo_visitor_daily_runs": settings.studio_visitor_daily_actions,
            "evo_runs_per_minute_per_ip": settings.studio_actions_per_minute_per_ip,
        }))

    def _keys(self, visitor: str, day: str | None = None) -> tuple[str, str]:
        day = day or day_key()
        return f"studio_actions:{day}", f"studio_actions:{day}:v:{visitor}"

    async def charge(self, visitor: str) -> str:
        """Take one action and return the UTC day it was counted on, for a refund if the action fails."""
        day = day_key()
        await self.take(visitor)
        return day

    async def refund(self, visitor: str, day: str) -> None:
        """Give back an action that did not complete, on the day it was counted."""
        total, mine = self._keys(visitor, day)
        if await self.db.incr(mine, 0) > 0:
            await self.db.incr(mine, -1)
        if await self.db.incr(total, 0) > 0:
            await self.db.incr(total, -1)

    async def check(self, visitor: str) -> None:
        try:
            await super().check(visitor)
        except ChimeraError as exc:
            if exc.code == ErrorCode.CAP_REACHED:
                exc.message = "Today's studio action limit is reached. More actions are available at 00:00 UTC."
            raise

    async def take(self, visitor: str) -> None:
        try:
            await super().take(visitor)
        except ChimeraError as exc:
            if exc.code == ErrorCode.CAP_REACHED:
                exc.message = "Today's studio action limit is reached. More actions are available at 00:00 UTC."
            raise


@router.get("/limits")
async def studio_limits(request: Request) -> JSONResponse:
    visitor, _ = _visitor(request, api(request))
    caps = request.app.state.studio_caps
    total, mine = await caps.used(visitor)
    return JSONResponse({"used": mine, "limit": caps.settings.evo_visitor_daily_runs,
                         "totalUsed": total, "totalLimit": caps.settings.evo_daily_runs,
                         "resetsAt": resets_at()}, headers={"Cache-Control": "no-store"})


@asynccontextmanager
async def charged_slot(request: Request, visitor: str, day: str) -> AsyncIterator[None]:
    """Hold a model slot for an action already charged on `day`. An action that fails or is cancelled is refunded."""
    try:
        async with request.app.state.studio_slots:
            yield
    except BaseException:
        await request.app.state.studio_caps.refund(visitor, day)
        raise


def public_job(doc: dict[str, Any]) -> dict[str, Any]:
    return {k: doc.get(k) for k in ("id", "operation", "status", "stage", "createdAt", "updatedAt", "result", "error")}


async def start_background(request: Request, visitor: str, day: str, operation: str,
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
            async with charged_slot(request, visitor, day):
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
    a = api(request)
    visitor, _ = _visitor(request, a)
    docs = [d for d in await a.services.db.list("assets", "visitor", visitor) if d.get("kind") == "studio_job"]
    # A nonterminal job that this process is not running was interrupted by a restart: at once with local storage
    # (single-process), else once it has had no update for longer than any stage takes (it may live in another process).
    for doc in docs:
        if doc.get("status") in ("queued", "running") and doc["id"] not in request.app.state.studio_tasks:
            if a.services.local_backend or job_is_stale(doc, a.settings.studio_job_stale_seconds):
                doc.update(status="interrupted", stage="Interrupted", updatedAt=now_iso(),
                           error="The server stopped while this was running. Please try again.")
                await a.services.db.put("assets", doc["id"], doc)
    docs.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""), reverse=True)
    return JSONResponse({"jobs": [public_job(d) for d in docs[:20]]}, headers={"Cache-Control": "no-store"})


async def creative_direction(settings: Any, names: list[str], brief: str) -> str:
    """A collaborator suggests phrasing; the creator's original words remain authoritative."""
    if settings.chimera_mode == "mock":
        return "Create a coherent, imaginative creature concept that follows the creator's direction."
    from app.evolution.live import build_studio_chat

    brain = build_studio_chat(settings)
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
    result = {key: doc.get(key) for key in ("id", "parentId", "imageUrl", "instruction", "direction", "createdAt", "mode")}
    if doc.get("sources"):
        result["sources"] = [{"name": s["name"], "hasImage": bool(s.get("imageKey"))} for s in doc["sources"]]
    return result


async def save_image(a: Any, image: Any, visitor: str, instruction: str, direction: str, parent_id: str | None,
                     reference_only: bool = False, source_inputs: list[tuple[str, bytes | None]] | None = None) -> dict[str, Any]:
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
    if source_inputs is not None:
        doc["sources"] = []
        for index, (name, data) in enumerate(source_inputs, 1):
            key = f"studio-sources/{version_id}/{index}.jpg" if data else None
            if key and data:
                await a.services.storage.put(key, data, "image/jpeg")
            doc["sources"].append({"name": name, "imageKey": key})
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


async def root_version(a: Any, selected: dict[str, Any], visitor: str) -> dict[str, Any]:
    root = selected
    seen: set[str] = set()
    while root.get("parentId"):
        parent_id = str(root["parentId"])
        if parent_id in seen or len(seen) >= 100:
            raise _err(ErrorCode.VALIDATION_FAILED, "This draft's history is invalid.", 422)
        seen.add(parent_id)
        root = await get_version(a, parent_id, visitor)
    return root


@router.get("/versions/{version_id}/sources/{index}")
async def source_image(version_id: str, index: int, request: Request) -> Response:
    a = api(request)
    visitor, _ = _visitor(request, a)
    selected = await get_version(a, version_id, visitor)
    root = await root_version(a, selected, visitor)
    sources = root.get("sources") or []
    if index not in (1, 2) or index > len(sources) or not sources[index - 1].get("imageKey"):
        raise _err(ErrorCode.NOT_FOUND, "This reference image is unavailable.", 404)
    data = await a.services.storage.get(sources[index - 1]["imageKey"])
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


async def plan_collaboration(settings: Any, brief: str, selected_instruction: str,
                             conversation: list[dict[str, str]], observation: str = "",
                             inspect: Callable[[], Awaitable[dict[str, str]]] | None = None) -> dict[str, Any]:
    """Use at most one visual inspection, then answer or propose an editable revision."""
    if settings.chimera_mode == "mock":
        last = conversation[-1]["content"]
        if inspect and any(word in last.lower() for word in ("inspect", "review", "look at")):
            review = await inspect()
            return {"message": "I inspected the selected draft. " + review["observation"], "action": None,
                    "review": review, "steps": [{"tool": "inspect_draft", "reason": "You asked me to inspect it."}]}
        return {"message": "I can turn that into a revision of the selected draft.",
                "action": {"type": "revise", "instruction": last, "reason": "Follow your direction."}, "steps": []}
    from app.evolution.live import build_studio_chat
    brain = build_studio_chat(settings)
    tools = [
        {"type": "function", "function": {"name": "propose_revision", "description": "Propose one editable image revision for the selected draft; never run it yourself.",
         "parameters": {"type": "object", "properties": {"instruction": {"type": "string"}, "reason": {"type": "string"}}, "required": ["instruction", "reason"], "additionalProperties": False}}},
        {"type": "function", "function": {"name": "inspect_draft", "description": "Inspect the selected image with a visual model when the user asks you to look or an observation is needed. This performs a model call.",
         "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"], "additionalProperties": False}}},
    ]
    prompt = ("You are a creative collaborator in Chimera Lab. The user directs an imaginary creature. "
              "You cannot see the selected image directly. A separate visual review may be provided; its observations "
              "are uncertain and can be wrong. Do not imply that you personally saw the image. You may propose one available action "
              "using the tools, or respond conversationally or ask a clarifying question. Never change the user's explicit "
              "anatomy or assert biological rules. A proposed action will be shown for the user to edit and run. "
              "For a request to visually inspect the image, call inspect_draft. You can inspect at most once per message. "
              "For a concrete visual change, propose_revision. Do not create or modify an image yourself. "
              "If the user mentions painting an area, explain they should use the paint tool; you cannot paint a mask.\n"
              + json.dumps({"original_brief": brief, "selected_draft_instruction": selected_instruction,
                            "independent_visual_observation": observation or None}, ensure_ascii=False))
    messages: list[dict[str, Any]] = [{"role": "system", "content": prompt}, *conversation]
    response = await brain.chat("studio_collaborate", {"messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": 4096})
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    calls = message.get("tool_calls") or []
    if len(calls) > 1 or (calls and choice.get("finish_reason") not in (None, "tool_calls")):
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned too many actions. Please try again.", 502)
    review: dict[str, str] | None = None
    steps: list[dict[str, str]] = []
    if calls and (calls[0].get("function") or {}).get("name") == "inspect_draft":
        if inspect is None or not calls[0].get("id"):
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator could not inspect this draft.", 502)
        try:
            inspect_args = json.loads((calls[0].get("function") or {}).get("arguments") or "{}")
        except (ValueError, TypeError) as exc:
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an invalid inspection.", 502) from exc
        if not isinstance(inspect_args, dict) or not isinstance(inspect_args.get("reason"), str) or not inspect_args["reason"].strip():
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an invalid inspection.", 502)
        review = await inspect()
        steps.append({"tool": "inspect_draft", "reason": inspect_args["reason"].strip()[:500]})
        messages.extend([{ "role": "assistant", "content": message.get("content") or None, "tool_calls": calls },
                         {"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps(review, ensure_ascii=False)}])
        # A second inspection is intentionally unavailable in this turn.
        response = await brain.chat("studio_collaborate_after_inspection", {"messages": messages, "tools": tools[:1],
                                    "tool_choice": "auto", "max_tokens": 4096})
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []
        if len(calls) > 1 or (calls and choice.get("finish_reason") not in (None, "tool_calls")):
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned too many actions after inspection.", 502)
    text = str(message.get("content") or "").strip()[:3000]
    if not calls:
        if not text or choice.get("finish_reason") not in (None, "stop"):
            raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator did not finish its response. Please try again.", 502)
        return {"message": text, "action": None, "review": review, "steps": steps}
    fn = calls[0].get("function") or {}
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except (ValueError, TypeError) as exc:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an invalid action. Please try again.", 502) from exc
    if not isinstance(args, dict) or not isinstance(args.get("reason"), str) or not args["reason"].strip():
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an invalid action. Please try again.", 502)
    reason = args["reason"].strip()[:500]
    if fn.get("name") == "propose_revision" and isinstance(args.get("instruction"), str) and args["instruction"].strip():
        action = {"type": "revise", "instruction": args["instruction"].strip()[:2000], "reason": reason}
    else:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The collaborator returned an unsupported action. Please try again.", 502)
    return {"message": text or "Here's a possible next step for this draft.", "action": action, "review": review, "steps": steps}


@router.post("/versions/{version_id}/collaborate")
async def collaborate(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    request.app.state.studio_caps.rate_limit(ip)
    await request.app.state.studio_caps.check(visitor)
    selected = await get_version(a, version_id, visitor)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send a message to the collaborator.", 422) from exc
    messages = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(messages, list) or not 1 <= len(messages) <= 12:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send between one and twelve conversation messages.", 422)
    conversation = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant") or not isinstance(item.get("content"), str) or not 1 <= len(item["content"].strip()) <= 2000:
            raise _err(ErrorCode.VALIDATION_FAILED, "Each message must contain up to 2,000 characters.", 422)
        conversation.append({"role": item["role"], "content": item["content"].strip()})
    if conversation[-1]["role"] != "user":
        raise _err(ErrorCode.VALIDATION_FAILED, "The last message must be yours.", 422)
    root = await root_version(a, selected, visitor)
    async def inspect_selected() -> dict[str, str]:
        image = await version_image(a, selected)
        result = await review_image(a.settings, image, str(root.get("instruction") or ""),
                                    str(selected.get("instruction") or "") if selected.get("parentId") else "")
        selected["review"] = result
        await a.services.db.put("assets", version_id, selected)
        return result
    day = await request.app.state.studio_caps.charge(visitor)
    async with charged_slot(request, visitor, day):
        result = await plan_collaboration(a.settings, str(root.get("instruction") or ""),
                                          str(selected.get("instruction") or ""), conversation,
                                          str((selected.get("review") or {}).get("observation") or ""), inspect_selected)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


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
    finals = {d.get("versionId") for d in docs if d.get("kind") == "studio_final" and d.get("isFinal") is True}
    rows = [public_version(d) for d in docs if str(d.get("id", "")).startswith("studio_") and d.get("responseId")]
    for row in rows:
        row["isFinal"] = row["id"] in finals
    rows.sort(key=lambda d: (d.get("createdAt") or "", d.get("id") or ""))
    return JSONResponse({"versions": rows}, headers={"Cache-Control": "no-store"})


@router.put("/versions/{version_id}/final")
async def mark_final(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, _ = _visitor(request, a)
    await get_version(a, version_id, visitor)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether this version is final.", 422) from exc
    if not isinstance(body, dict) or not isinstance(body.get("isFinal"), bool):
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether this version is final.", 422)
    value = body["isFinal"]
    await a.services.db.put("assets", f"studiofinal_{version_id}", {"kind": "studio_final", "visitor": visitor,
                                                                    "versionId": version_id, "isFinal": value})
    return JSONResponse({"versionId": version_id, "isFinal": value}, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/download")
async def download_version(version_id: str, request: Request) -> Response:
    a = api(request)
    visitor, _ = _visitor(request, a)
    doc = await get_version(a, version_id, visitor)
    data = await version_image(a, doc)
    key = doc.get("imageKey") or str(doc.get("imageUrl") or "")
    from app.agentapi.files import content_type_for
    return Response(data, media_type=content_type_for(key), headers={"Cache-Control": "no-store",
                    "Content-Disposition": f'attachment; filename="chimera-{version_id}.{key.rsplit(".", 1)[-1]}"'})


async def review_image(settings: Any, image: bytes, brief: str, change: str) -> dict[str, str]:
    """Observe without the brief first, then suggest options with the creator's intent in view."""
    if settings.chimera_mode == "mock":
        return {"observation": "Mock preview: visual inspection is not available in mock mode.",
                "suggestions": "Describe what you want to change in the revision field."}
    from app.evolution.live import LiveEvoSpark, build_studio_chat

    observation = await LiveEvoSpark(settings).describe(image)
    description = str(observation.get("description") or "").strip()
    if not description:
        raise _err(ErrorCode.UPSTREAM_ERROR, "The visual reviewer could not describe this image.", 502)
    brain = build_studio_chat(settings)
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
    request.app.state.studio_caps.rate_limit(ip)
    await request.app.state.studio_caps.check(visitor)
    selected = await get_version(a, version_id, visitor)
    root = await root_version(a, selected, visitor)
    image = await version_image(a, selected)
    day = await request.app.state.studio_caps.charge(visitor)
    async with charged_slot(request, visitor, day):
        result = await review_image(a.settings, image, str(root.get("instruction") or ""),
                                    str(selected.get("instruction") or "") if selected.get("parentId") else "")
    selected["review"] = result
    await a.services.db.put("assets", version_id, selected)
    return JSONResponse(result, headers={"Cache-Control": "no-store"})


@router.get("/versions/{version_id}/review")
async def saved_review(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, _ = _visitor(request, a)
    doc = await get_version(a, version_id, visitor)
    return JSONResponse({"review": doc.get("review")}, headers={"Cache-Control": "no-store"})


@router.post("/concept")
async def concept(request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    request.app.state.studio_caps.rate_limit(ip)
    await request.app.state.studio_caps.check(visitor)
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
    slot_refs: list[bytes | None] = []
    labels: list[str] = []
    for index in (1, 2):
        name = _clean_name(form.get(f"animal{index}"), f"animal{index}")
        upload = form.get(f"image{index}")
        has_image = isinstance(upload, UploadFile) and bool(upload.filename or upload.size)
        if not name and not has_image:
            raise _err(ErrorCode.VALIDATION_FAILED, f"Add a name or image for animal {index}.", 422)
        names.append(name or f"animal {index} in its reference image")
        prepared: bytes | None = None
        if has_image:
            data = await upload.read(a.settings.evo_max_upload_bytes + 1)
            await upload.close()
            prepared = await U.prepare(data, f"animal{index}", a.services)
            refs.append(prepared)
            labels.append(f"Reference image {len(refs)} depicts animal {index}: {names[-1]}.")
        slot_refs.append(prepared)
    day = await request.app.state.studio_caps.charge(visitor)
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
        return await save_image(a, image, visitor, brief, direction, None, source_inputs=list(zip(names, slot_refs)))
    if request.query_params.get("background") == "1":
        return await start_background(request, visitor, day, "concept", render)
    async with charged_slot(request, visitor, day):
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)


@router.post("/versions/{version_id}/revise")
async def revise(version_id: str, request: Request) -> JSONResponse:
    a = api(request)
    visitor, ip = _visitor(request, a)
    request.app.state.studio_caps.rate_limit(ip)
    await request.app.state.studio_caps.check(visitor)
    doc = await get_version(a, version_id, visitor)
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the revision you want.", 422) from exc
    instruction = body.get("instruction") if isinstance(body, dict) else None
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 2000:
        raise _err(ErrorCode.VALIDATION_FAILED, "Describe the revision in up to 2,000 characters.", 422)
    use_sources = body.get("useSources", False) if isinstance(body, dict) else False
    if not isinstance(use_sources, bool):
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose whether to include the source images.", 422)
    source_refs: list[tuple[str, bytes]] = []
    if use_sources:
        root = await root_version(a, doc, visitor)
        for source in root.get("sources") or []:
            if source.get("imageKey"):
                source_refs.append((str(source.get("name") or "animal"), await a.services.storage.get(source["imageKey"])))
        if not source_refs:
            raise _err(ErrorCode.VALIDATION_FAILED, "This concept has no saved source images to include.", 422)
    instruction = instruction.strip()
    day = await request.app.state.studio_caps.charge(visitor)
    async def render(stage: Callable[[str], Awaitable[None]]) -> dict[str, Any]:
        await stage("Revising the selected draft")
        refs = [await version_image(a, doc)] if doc.get("referenceOnly") or source_refs else []
        source_note = ""
        if source_refs:
            refs.extend(data for _, data in source_refs)
            source_note = " Reference image 1 is the selected draft. " + " ".join(
                f"Reference image {i + 2} shows {name} and is only a source for its features."
                for i, (name, _) in enumerate(source_refs))
        image = await a.services.image_gen.generate(
            "Revise the selected image according to the creator's instruction. Preserve other details where possible. " + instruction + source_note,
            refs, "1:1", None if refs else doc["responseId"])
        await stage("Saving your revision")
        return await save_image(a, image, visitor, instruction, "", version_id)
    if request.query_params.get("background") == "1":
        return await start_background(request, visitor, day, "revision", render)
    async with charged_slot(request, visitor, day):
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)


@router.post("/versions/{version_id}/region")
async def region(version_id: str, request: Request) -> JSONResponse:
    from app.adapters.base import GeneratedImage

    a = api(request)
    visitor, ip = _visitor(request, a)
    request.app.state.studio_caps.rate_limit(ip)
    await request.app.state.studio_caps.check(visitor)
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
    day = await request.app.state.studio_caps.charge(visitor)

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
        return await start_background(request, visitor, day, "region", render)
    async with charged_slot(request, visitor, day):
        async def no_stage(_message: str) -> None:
            pass
        version = await render(no_stage)
    return JSONResponse(version, status_code=201)
