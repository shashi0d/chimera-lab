"""The agent API under /evo (docs/api_contract.md): runs, events (SSE), choices, limits, creatures, gallery, files.

Starting and following a run needs a signed-in user (app/auth.py); a run belongs to the user who started it. The
gallery, showcase and published creatures are public."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.datastructures import UploadFile

from app.agentapi import uploads as U
from app.agentapi.caps import Caps, client_ip
from app.agentapi.creature import parent_view
from app.agentapi.files import PublicFiles, content_type_for
from app.agentapi.fusion_prompt import DEFAULT_STYLE, STYLES
from app.agentapi.gallery import Creatures
from app.agentapi.jobs import AgentDriver, ChoiceRefused, Job, JobRunner, PromptDriver
from app.agentapi.store import TERMINAL, RunStore, snapshot
from app.auth import User, current_user, require_user
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.services import Services
from app.util import new_id, now_iso

log = logging.getLogger(__name__)
router = APIRouter(prefix="/evo", tags=["agent"])
NAME_RE = re.compile(r"^[^\W\d_](?:[\w'’ .()-]*[\w).])?$", re.UNICODE)


class AgentApi:
    """Everything the routes share, built once per app (app.state.agent)."""

    def __init__(self, services: Services, files: PublicFiles) -> None:
        self.services, self.settings, self.files = services, services.settings, files
        self.store = RunStore(services.db, services.settings.run_lease_seconds)
        self.creatures = Creatures(services.db, files, services.settings)
        self.runner = JobRunner(services, self.store, files, self.creatures)
        self.caps = Caps(services.db, services.settings)
        # Builds the driver for one run (EVO_FUSION_MODE: prompt or algorithm). Tests replace it.
        self.driver_factory: Any = lambda: (PromptDriver(services) if services.settings.evo_fusion_mode == "prompt"
                                            else AgentDriver(services))


def api(request: Request) -> AgentApi:
    return request.app.state.agent  # type: ignore[no-any-return]


def _err(code: ErrorCode, message: str, status: int, **details: Any) -> ChimeraError:
    return ChimeraError(code, message, retryable=False, details=details).with_status(status)


async def _owner(request: Request, a: AgentApi) -> tuple[User, str]:
    """The signed-in user (401 without one) and the client IP (per-IP rate limits)."""
    user = await require_user(request)
    return user, client_ip(request, a.settings.evo_proxy_hops)


def _clean_name(raw: Any, slot: str) -> str | None:
    if raw is None or isinstance(raw, UploadFile):
        return None
    name = " ".join(str(raw).split())
    if not name:
        return None
    if len(name) > 80 or not NAME_RE.match(name):
        raise _err(ErrorCode.VALIDATION_FAILED, "Give the animal's common or scientific name.", 422, slot=slot)
    return name


# ====================================================================== POST /evo/agent/runs


@router.post("/agent/runs", response_model=None)
async def start_run(request: Request) -> Response:
    a = api(request)
    svc, st = a.services, a.settings
    user, ip = await _owner(request, a)
    a.caps.rate_limit(ip)
    await a.caps.check(user.id)

    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 2 * st.evo_max_upload_bytes + 2 * 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, U.MSG_SIZE, 413, slot=None, maxBytes=st.evo_max_upload_bytes)
    try:
        form = await request.form(max_files=4, max_fields=16)
    except Exception as exc:  # malformed multipart
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the parents as multipart/form-data.", 422) from exc

    mode = str(form.get("mode") or "").strip().lower()
    if mode not in U.MODES:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose a mode: realistic, speculative or mythic.", 422,
                   field="mode", modes=list(U.MODES))
    style = str(form.get("style") or DEFAULT_STYLE).strip().lower()
    if style not in STYLES:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose an art style: " + ", ".join(STYLES) + ".", 422,
                   field="style", styles=list(STYLES))
    names: dict[str, str | None] = {s: _clean_name(form.get(f"{s}Name"), s) for s in U.SLOTS}
    photos: dict[str, bytes] = {}  # identified by the vision model
    refs: dict[str, bytes] = {}  # sent to the image model as references (prompt mode)
    versions: dict[str, str] = {}
    for s in U.SLOTS:
        vid = form.get(f"{s}VersionId")
        if isinstance(vid, str) and vid.strip():
            # An earlier generated creature: its image is the reference, its title the name.
            vdoc = await _own_version(a, vid.strip(), user, s)
            refs[s] = await a.files.get(vdoc["imageKey"])
            names[s] = names[s] or str(vdoc.get("title") or "an earlier creature")
            versions[s] = vdoc["id"]
            continue
        f = form.get(f"{s}Image")
        if isinstance(f, UploadFile) and (f.filename or f.size):
            data = await f.read()
            await f.close()
            if data:
                # Every photo is read (a person or a non-animal is refused); a typed name wins over the reading.
                photos[s] = refs[s] = await U.prepare(data, s, svc)
            del data
        if not photos.get(s) and not names[s]:
            raise _err(ErrorCode.VALIDATION_FAILED, f"Add a photo or a name for the {s}.", 422, slot=s)

    sire, dam, choice = await _identify(a, photos, names)
    del photos
    if choice is not None:
        return JSONResponse(choice, status_code=200)
    for s, parent in (("sire", sire), ("dam", dam)):
        if s in versions:
            parent.update(source="version", versionId=versions[s])
    driver = a.driver_factory()

    await a.caps.take(user.id)
    run_id = new_id("run")
    ts = now_iso()
    doc = {"runId": run_id, "status": "queued", "position": None, "sire": sire, "dam": dam, "mode": mode,
           "createdAt": ts, "updatedAt": ts, "lastEventId": 0, "creatureId": None, "error": None,
           "pendingChoice": None, "events": [], "owner": user.id, "style": style}
    job = Job(doc=doc, driver=driver, runner=a.runner)
    job.extra["refs"] = refs  # in memory only: photos are never stored
    await a.runner.submit(job)
    body = {"runId": run_id, "status": doc["status"], "position": doc["position"],
            "eventsUrl": f"/evo/agent/runs/{run_id}/events", "runUrl": f"/evo/agent/runs/{run_id}",
            "sire": sire, "dam": dam, "mode": mode, "style": style}
    return JSONResponse(body, status_code=202)


async def _own_version(a: AgentApi, version_id: str, user: User, slot: str) -> dict[str, Any]:
    doc = await a.services.db.get("assets", version_id)
    if not doc or doc.get("kind") != "lab_version" or doc.get("owner") != user.id or not doc.get("imageKey"):
        raise _err(ErrorCode.VALIDATION_FAILED, f"The image for the {slot} is unavailable.", 422, slot=slot)
    return doc


async def _identify(a: AgentApi, photos: dict[str, bytes], names: dict[str, str | None],
                    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    readings = await U.identify(a.services, photos) if photos else {}
    parents: dict[str, dict[str, Any] | None] = {}
    for s in U.SLOTS:
        if names[s]:
            parents[s] = parent_view(names[s], None, "name", None)
        else:
            r = readings[s]
            parents[s] = parent_view(r.common_name, r.scientific_name, "image", round(r.confidence, 2))
    for s in U.SLOTS:
        r = readings.get(s)
        if r is not None and not names[s] and (not r.common_name or
                                               r.confidence < a.settings.evo_identify_min_confidence):
            ident = {k: (None if k == s else v) for k, v in parents.items()}
            for k in U.SLOTS:
                rk = readings.get(k)
                if rk is not None and k != s and not names[k] and (not rk.common_name or
                                                  rk.confidence < a.settings.evo_identify_min_confidence):
                    ident[k] = None
            return parents["sire"], parents["dam"], U.needs_choice(s, r, ident)  # type: ignore[return-value]
    return parents["sire"], parents["dam"], None  # type: ignore[return-value]


# ====================================================================== runs


async def _doc(a: AgentApi, run_id: str, user: User) -> dict[str, Any]:
    """The user's own run. Another user's run reads as missing (no existence leak)."""
    doc = await a.store.get(run_id)
    if doc is None or doc.get("owner") != user.id:
        raise ChimeraError(ErrorCode.RUN_NOT_FOUND, "This run doesn't exist.")
    return doc


@router.get("/agent/runs/{run_id}", response_model=None)
async def get_run(run_id: str, request: Request) -> Response:
    doc = await _doc(api(request), run_id, await require_user(request))
    return JSONResponse(snapshot(doc), headers={"Cache-Control": "no-cache"})


def _sse(e: dict[str, Any]) -> str:
    return f"id: {e['id']}\nevent: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n"


def _after(request: Request) -> int:
    raw = request.headers.get("last-event-id") or request.query_params.get("after") or "0"
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


@router.get("/agent/runs/{run_id}/events", response_model=None)
async def run_events(run_id: str, request: Request) -> Response:
    a = api(request)
    await _doc(a, run_id, await require_user(request))
    after = _after(request)
    st = a.settings

    async def stream():  # type: ignore[no-untyped-def]
        last, last_sent = after, time.monotonic()
        yield "retry: 3000\n\n"
        while True:
            doc = await a.store.get(run_id)
            if doc is None:
                return
            for e in [e for e in doc["events"] if e["id"] > last]:
                yield _sse(e)
                last, last_sent = e["id"], time.monotonic()
            if doc["status"] in TERMINAL and last >= doc["lastEventId"]:
                return
            if await request.is_disconnected():
                return
            idle = time.monotonic() - last_sent
            wait = max(0.01, st.evo_keepalive_seconds - idle)
            if run_id not in a.store.live:
                wait = min(wait, st.evo_poll_seconds)
            changed = await a.store.wait(run_id, wait)
            if not changed and time.monotonic() - last_sent >= st.evo_keepalive_seconds:
                yield ": ping\n\n"
                last_sent = time.monotonic()

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@router.post("/agent/runs/{run_id}/choice", response_model=None)
async def answer_choice(run_id: str, request: Request) -> Response:
    a = api(request)
    await _doc(a, run_id, await require_user(request))
    try:
        body = await request.json()
    except ValueError as exc:
        raise _err(ErrorCode.VALIDATION_FAILED, "Send {choiceId, answer} as JSON.", 422) from exc
    if not isinstance(body, dict) or not isinstance(body.get("choiceId"), str):
        raise _err(ErrorCode.VALIDATION_FAILED, "Send {choiceId, answer} as JSON.", 422)
    try:
        a.runner.answer(run_id, body["choiceId"], body.get("answer"))
    except ChoiceRefused as e:
        raise _err(ErrorCode.VALIDATION_FAILED, e.message, e.status) from e
    return JSONResponse({"accepted": True})


@router.get("/agent/limits", response_model=None)
async def limits(request: Request) -> Response:
    a = api(request)
    user = await current_user(request)
    body = await a.caps.limits(user.id if user else None, len(a.runner.running), len(a.runner.queued_jobs))
    return JSONResponse(body, headers={"Cache-Control": "no-cache"})


@router.get("/config", response_model=None)
async def public_config(request: Request) -> Response:
    """What the browser needs to sign in: the project URL and its publishable key (both public by design)."""
    st = api(request).settings
    return JSONResponse({"supabaseUrl": st.supabase_url, "supabasePublishableKey": st.supabase_publishable_key,
                         "authConfigured": request.app.state.auth.configured}, headers={"Cache-Control": "no-cache"})


# ====================================================================== creatures, gallery, files


@router.get("/creatures/{creature_id}", response_model=None)
async def get_creature(creature_id: str, request: Request) -> Response:
    view = await api(request).creatures.get(creature_id, await current_user(request))
    if view is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "This creature doesn't exist.")
    return JSONResponse(view)


@router.get("/publications/{publication_id}", response_model=None)
async def get_publication(publication_id: str, request: Request) -> Response:
    view = await api(request).creatures.publication(publication_id)
    if view is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "This creation isn't in the gallery.")
    return JSONResponse(view)


@router.get("/gallery", response_model=None)
async def gallery(request: Request, limit: int = 24, cursor: str | None = None) -> Response:
    limit = max(1, min(100, limit))
    return JSONResponse(await api(request).creatures.gallery(limit, cursor), headers={"Cache-Control": "no-cache"})


@router.get("/files/{key:path}", response_model=None)
async def get_file(key: str, request: Request) -> Response:
    a = api(request)
    if not a.files.local:
        return RedirectResponse(a.files.url(key), status_code=307)
    try:
        data = await a.files.get(key)
    except ChimeraError as e:
        raise ChimeraError(ErrorCode.NOT_FOUND, "File not found.") from e
    return Response(data, media_type=content_type_for(key),
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
