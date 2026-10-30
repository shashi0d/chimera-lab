from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse, Response

from app.api.deps import mock_fault, runs, services, session_id
from app.errors import ChimeraError
from app.models.schemas import ErrorCode, Run, StartRunRequest
from app.pipeline.registry import EXECUTORS
from app.pipeline.runner import RunManager
from app.services import Services
from app.util import new_id, now_iso

router = APIRouter()
_recent: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(sid: str, per_minute: int) -> None:
    now = time.monotonic()
    q = _recent[sid]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        retry_ms = int((60 - (now - q[0])) * 1000) + 1
        raise ChimeraError(ErrorCode.RATE_LIMITED, "You're starting fusions too quickly. Wait a moment.",
                           retry_after_ms=retry_ms)
    q.append(now)


def _etag(run: Run) -> str:
    return f'"{run.id}-{run.version}"'


def _run_response(run: Run, status: int = 200) -> JSONResponse:
    return JSONResponse(run.dump(), status_code=status, headers={"ETag": _etag(run), "Cache-Control": "no-cache"})


@router.post("/runs", response_model=None)
async def start_run(
    body: StartRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    svc: Services = Depends(services),
    mgr: RunManager = Depends(runs),
    sid: str = Depends(session_id),
    fault: str | None = Depends(mock_fault),
) -> Response:
    if not idempotency_key or len(idempotency_key) > 128:
        raise ChimeraError(ErrorCode.VALIDATION_FAILED, "Missing Idempotency-Key header.")
    idem_key = f"{sid}:{idempotency_key}"
    existing = await svc.db.get("idempotency", idem_key)
    if existing:
        run = await mgr.load(existing["runId"])
        if run:
            return _run_response(run)

    node = next((n for n in body.graph.nodes if n.id == body.node_id), None)
    if node is None or node.type not in EXECUTORS:
        raise ChimeraError(ErrorCode.GRAPH_INVALID, "That node can't be run.")
    _rate_limit(sid, svc.settings.runs_per_minute_per_session)

    ts = now_iso()
    run = Run(id=new_id("run"), graph_id=body.graph.graph_id, node_id=node.id, session_id=sid,
              steps=mgr.new_steps(node.type), created_at=ts, updated_at=ts)
    # Validates inputs (GRAPH_INVALID / DUPLICATE_INPUTS) before anything is stored.
    EXECUTORS[node.type].resolve_inputs(body.graph, node)
    EXECUTORS[node.type].configure(node)
    await mgr.save(run)
    await svc.db.put("idempotency", idem_key, {"runId": run.id})
    mgr.start(run, body.graph, node.type, fault)
    return _run_response(run, 201)


async def _get(mgr: RunManager, run_id: str) -> Run:
    run = await mgr.load(run_id)
    if run is None:
        raise ChimeraError(ErrorCode.RUN_NOT_FOUND, "This fusion run no longer exists.")
    return run


@router.get("/runs/{run_id}", response_model=None)
async def get_run(run_id: str, request: Request, mgr: RunManager = Depends(runs)) -> Response:
    run = await _get(mgr, run_id)
    if request.headers.get("if-none-match") == _etag(run):
        return Response(status_code=304, headers={"ETag": _etag(run)})
    return _run_response(run)


@router.post("/runs/{run_id}/cancel", response_model=None)
async def cancel_run(run_id: str, mgr: RunManager = Depends(runs)) -> Response:
    run = await _get(mgr, run_id)
    return _run_response(await mgr.cancel(run))
