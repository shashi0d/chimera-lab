"""The agent API under /evo (docs/api_contract.md): runs, events (SSE), choices, limits, creatures, gallery, files."""

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
from app.agentapi.caps import Caps, client_ip, visitor_key
from app.agentapi.creature import parent_view
from app.agentapi.files import PublicFiles, content_type_for
from app.agentapi.fixtures import REFUSED, RUN_SCENARIOS, SCENARIOS, load
from app.agentapi.gallery import Creatures
from app.agentapi.jobs import AgentDriver, ChoiceRefused, Job, JobRunner, ReplayDriver
from app.agentapi.store import TERMINAL, RunStore, snapshot
from app.api.deps import SESSION_RE, mock_fault
from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from app.services import Services
from app.util import new_id, now_iso, parse_iso

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

    @property
    def mock(self) -> bool:
        return self.settings.chimera_mode == "mock"

    @property
    def fixtures_dir(self) -> Any:
        return self.settings.repo_path(self.settings.evo_fixtures_dir)


def api(request: Request) -> AgentApi:
    return request.app.state.agent  # type: ignore[no-any-return]


def _err(code: ErrorCode, message: str, status: int, **details: Any) -> ChimeraError:
    return ChimeraError(code, message, retryable=False, details=details).with_status(status)


def _scenario(request: Request, a: AgentApi) -> str | None:
    """X-Mock-Scenario, honoured only in mock mode (default success)."""
    if not a.mock:
        return None
    s = (request.headers.get("x-mock-scenario") or "success").strip().lower()
    if s not in SCENARIOS:
        raise _err(ErrorCode.VALIDATION_FAILED, f"Unknown X-Mock-Scenario {s!r}.", 422, scenarios=list(SCENARIOS))
    return s


def _visitor(request: Request, a: AgentApi) -> tuple[str, str]:
    sid = request.headers.get("x-session-id", "")
    sid = sid if SESSION_RE.match(sid) else "anonymous"
    ip = client_ip(request, a.settings.evo_proxy_hops)
    return visitor_key(sid, ip), ip


def _fixture_error(case: dict[str, Any]) -> ChimeraError:
    body, status = case["response"]["body"]["error"], case["response"]["status"]
    return ChimeraError(ErrorCode(body["code"]), body["message"], retryable=bool(body.get("retryable")),
                        details=dict(body.get("details") or {})).with_status(status)


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
    scenario = _scenario(request, a)
    visitor, ip = _visitor(request, a)
    a.caps.rate_limit(ip)
    if scenario == "cap_daily":
        raise _fixture_error({"response": load(a.fixtures_dir, "cap_daily.json")["response"]})
    await a.caps.check(visitor)

    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 2 * st.evo_max_upload_bytes + 2 * 1024 * 1024:
        raise _err(ErrorCode.FILE_TOO_LARGE, U.MSG_SIZE, 413, slot=None, maxBytes=st.evo_max_upload_bytes)
    try:
        form = await request.form(max_files=4, max_fields=16)
    except Exception as exc:  # malformed multipart
        raise _err(ErrorCode.VALIDATION_FAILED, "Send the parents as multipart/form-data.", 422) from exc
    if scenario in REFUSED:
        raise _fixture_error(load(a.fixtures_dir, "upload_refused.json")["cases"][REFUSED[scenario]])

    mode = str(form.get("mode") or "").strip().lower()
    if mode not in U.MODES:
        raise _err(ErrorCode.VALIDATION_FAILED, "Choose a mode: realistic, speculative or mythic.", 422,
                   field="mode", modes=list(U.MODES))
    names: dict[str, str | None] = {s: _clean_name(form.get(f"{s}Name"), s) for s in U.SLOTS}
    photos: dict[str, bytes] = {}
    for s in U.SLOTS:
        f = form.get(f"{s}Image")
        if isinstance(f, UploadFile) and (f.filename or f.size):
            data = await f.read()
            await f.close()
            if data and not names[s]:  # a name confirms an identify choice: the photo is not needed then
                photos[s] = await U.prepare(data, s, svc)
            del data
        if not photos.get(s) and not names[s]:
            raise _err(ErrorCode.VALIDATION_FAILED, f"Add a photo or a name for the {s}.", 422, slot=s)

    if scenario is not None and scenario != "agent":
        parents = _mock_parents(a, scenario, names, photos)
        if isinstance(parents, dict) and parents.get("status") == "needs_choice":
            return JSONResponse(parents, status_code=200)
        fixture_name, sire, dam = parents  # type: ignore[misc]
        driver: Any = ReplayDriver(load(a.fixtures_dir, fixture_name), a.fixtures_dir)
    else:
        sire, dam, choice = await _identify(a, photos, names, mock_fault(request))
        del photos
        if choice is not None:
            return JSONResponse(choice, status_code=200)
        driver = AgentDriver(svc)

    await a.caps.take(visitor)
    run_id = new_id("run")
    ts = now_iso()
    doc = {"runId": run_id, "status": "queued", "position": None, "sire": sire, "dam": dam, "mode": mode,
           "createdAt": ts, "updatedAt": ts, "lastEventId": 0, "creatureId": None, "error": None,
           "pendingChoice": None, "events": [], "visitor": visitor, "scenario": scenario}
    job = Job(doc=doc, driver=driver, runner=a.runner)
    holds = None
    if scenario == "queued":
        holds, gate = _queue_script(a)
        job.not_before = time.monotonic() + gate
    await a.runner.submit(job, holds)
    body = {"runId": run_id, "status": doc["status"], "position": doc["position"],
            "eventsUrl": f"/evo/agent/runs/{run_id}/events", "runUrl": f"/evo/agent/runs/{run_id}",
            "sire": sire, "dam": dam, "mode": mode}
    return JSONResponse(body, status_code=202)


def _mock_parents(a: AgentApi, scenario: str, names: dict[str, str | None],
                  photos: dict[str, bytes]) -> Any:
    """Mock mode: the fixture's parents for photo slots; a named slot keeps its name (source 'name')."""
    if scenario == "identify_choice":
        fx = load(a.fixtures_dir, "identify_choice.json")
        if "sire" in photos:
            return fx["response"]["body"]
        scenario = "host_tie"  # the follow-up post (names): the host-tie run, as in the fixture's followUp
    fixture_name = RUN_SCENARIOS[scenario]
    body = load(a.fixtures_dir, fixture_name)["response"]["body"]
    out = []
    for s in U.SLOTS:
        fx_parent = body[s]
        if names[s]:
            same = names[s].lower() == (fx_parent["commonName"] or "").lower()
            out.append(parent_view(names[s], fx_parent["scientificName"] if same else None, "name", None))
        else:
            out.append(fx_parent)
    return fixture_name, out[0], out[1]


def _queue_script(a: AgentApi) -> tuple[list[float], float]:
    """Mock 'queued': the fixture's waits (position 2, then 1, then start), scaled like every replayed gap."""
    ev = load(a.fixtures_dir, "run_queued.json")["events"]
    st = a.settings

    def gap(i: int, j: int) -> float:
        secs = (parse_iso(ev[j]["at"]) - parse_iso(ev[i]["at"])).total_seconds()
        return min(secs * st.evo_mock_replay_scale, st.evo_mock_max_event_delay)

    first = gap(0, 1)
    return [first], first + gap(1, 2) + 0.001


async def _identify(a: AgentApi, photos: dict[str, bytes], names: dict[str, str | None],
                    fault: str | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    readings = await U.identify(a.services, photos, fault) if photos else {}
    parents: dict[str, dict[str, Any] | None] = {}
    for s in U.SLOTS:
        if names[s]:
            parents[s] = parent_view(names[s], None, "name", None)
        else:
            r = readings[s]
            parents[s] = parent_view(r.common_name, r.scientific_name, "image", round(r.confidence, 2))
    for s in U.SLOTS:
        r = readings.get(s)
        if r is not None and (not r.common_name or r.confidence < a.settings.evo_identify_min_confidence):
            ident = {k: (None if k == s else v) for k, v in parents.items()}
            for k in U.SLOTS:
                rk = readings.get(k)
                if rk is not None and k != s and (not rk.common_name or
                                                  rk.confidence < a.settings.evo_identify_min_confidence):
                    ident[k] = None
            return parents["sire"], parents["dam"], U.needs_choice(s, r, ident)  # type: ignore[return-value]
    return parents["sire"], parents["dam"], None  # type: ignore[return-value]


# ====================================================================== runs


async def _doc(a: AgentApi, run_id: str) -> dict[str, Any]:
    doc = await a.store.get(run_id)
    if doc is None:
        raise ChimeraError(ErrorCode.RUN_NOT_FOUND, "This run doesn't exist.")
    return doc


@router.get("/agent/runs/{run_id}", response_model=None)
async def get_run(run_id: str, request: Request) -> Response:
    doc = await _doc(api(request), run_id)
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
    await _doc(a, run_id)
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
    await _doc(a, run_id)
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
    visitor, _ = _visitor(request, a)
    body = await a.caps.limits(visitor, len(a.runner.running), len(a.runner.queued_jobs))
    if a.mock and request.headers.get("x-mock-scenario", "").lower() == "cap_daily":
        body = {**body, "liveRuns": "capped", "dailyTotal": {**body["dailyTotal"], "used": body["dailyTotal"]["limit"]}}
    return JSONResponse(body, headers={"Cache-Control": "no-cache"})


# ====================================================================== creatures, gallery, files


@router.get("/creatures/{creature_id}", response_model=None)
async def get_creature(creature_id: str, request: Request) -> Response:
    view = await api(request).creatures.get(creature_id)
    if view is None:
        raise ChimeraError(ErrorCode.NOT_FOUND, "This creature doesn't exist.")
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
