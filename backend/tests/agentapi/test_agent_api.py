"""The Fusion API with sign-in: runs, SSE events, uploads and identify, caps, queue, leases, files and serving.

Runs go through the real job runner, event store and SSE path. The work itself is a scripted driver (fast and
precise about events). No paid call is made.
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from app.agentapi.creatures import build_creature
from app.agentapi.jobs import Job
from app.main import create_app
from app.util import new_id, now_iso
from tests.conftest import IMAGES, SIGNED_OUT, auth, make_settings, visitor_id, offline_services
from tests.fakes.faults import current_fault


def png(color: str = "blue") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(out, "PNG")
    return out.getvalue()


class ScriptedDriver:
    """A run that emits one step, renders one image and saves a creature (optionally failing or waiting first)."""

    def __init__(self, fail: str | None = None, hold: asyncio.Event | None = None) -> None:
        self.fail, self.hold = fail, hold

    async def run(self, job: Job) -> dict[str, Any]:
        from app.agentapi.jobs import RunFailed

        await job.emit("step", n=1, tool="render", args={}, summary="rendered", reason="", cards=[], ok=True,
                       error=None)
        if self.hold is not None:
            await self.hold.wait()
        if self.fail:
            raise RunFailed(self.fail, "The model service returned an error.", True)
        url = await job.runner.files.put(f"runs/{job.run_id}/img1.png", png(), "image/png")
        await job.emit("render", n=1, imageId="img1", url=url, kind="render", parent=None, method="prompt",
                       rendersUsed=1, rendersLeft=0)
        doc = job.doc
        view = build_creature(creature_id=new_id("crt"), created_at=now_iso(), sire=doc["sire"], dam=doc["dam"],
                              image_url=url, generation={"operation": "fusion", "prompt": "p",
                                                         "parents": [doc["sire"], doc["dam"]]},
                              run_id=job.run_id, seconds=0.1)
        await job.runner.creatures.save(view, doc.get("owner"))
        return {"creatureId": view["creatureId"], "imageId": "img1", "imageUrl": url, "remainingFailures": [],
                "hiddenChecks": 0, "agree": True, "stop": "finalized"}


def api_settings(tmp_path: Path, **over: Any):  # type: ignore[no-untyped-def]
    base = dict(evo_runs_per_minute_per_ip=1000, evo_visitor_daily_runs=1000, evo_daily_runs=1000,
                evo_keepalive_seconds=15.0, evo_heartbeat_seconds=0.05)
    base.update(over)
    return make_settings(tmp_path, **base)


@pytest.fixture
async def make_client(tmp_path: Path) -> AsyncIterator[Any]:
    stack: list[Any] = []

    async def make(driver: Any = None, user: str = "user-1", **over: Any) -> httpx.AsyncClient:
        settings = api_settings(tmp_path / f"app{len(stack)}", **over)
        svc = offline_services(settings)
        app = create_app(settings, services=svc)
        app.state.agent.driver_factory = driver or (lambda: ScriptedDriver())
        ctx = app.router.lifespan_context(app)
        await ctx.__aenter__()
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=auth(user),
                              timeout=30)
        c.app = app  # type: ignore[attr-defined]
        stack.append((c, ctx))
        return c

    yield make
    for c, ctx in reversed(stack):
        await c.aclose()
        await ctx.__aexit__(None, None, None)


@pytest.fixture
async def client(make_client: Any) -> httpx.AsyncClient:
    return await make_client()


def photos(sire: str = "lion.jpg", dam: str = "red_fox.jpg") -> dict[str, Any]:
    return {"sireImage": (sire, (IMAGES / sire).read_bytes(), "image/jpeg"),
            "damImage": (dam, (IMAGES / dam).read_bytes(), "image/jpeg")}


async def post_run(c: httpx.AsyncClient, files: dict[str, Any] | None = None, data: dict[str, Any] | None = None,
                   headers: dict[str, str] | None = None) -> httpx.Response:
    return await c.post("/evo/agent/runs", data=data or {}, files=photos() if files is None else files,
                        headers=headers)


async def named_run(c: httpx.AsyncClient, **kw: Any) -> httpx.Response:
    return await post_run(c, files={}, data={"sireName": "lion", "damName": "red fox"}, **kw)


def parse_sse(text: str) -> tuple[list[dict[str, Any]], int]:
    """(events, pings). Checks that each message's id and event lines match its data."""
    events, pings = [], 0
    for block in text.split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln]
        if not lines:
            continue
        if all(ln.startswith(":") for ln in lines):
            pings += sum(ln == ": ping" for ln in lines)
            continue
        fields = dict(ln.split(": ", 1) for ln in lines if not ln.startswith(":") and ": " in ln)
        if "data" not in fields:
            continue
        data = json.loads(fields["data"])
        assert int(fields["id"]) == data["id"] and fields["event"] == data["type"]
        events.append(data)
    return events, pings


async def events_of(c: httpx.AsyncClient, run_id: str, **kw: Any) -> list[dict[str, Any]]:
    r = await c.get(f"/evo/agent/runs/{run_id}/events", **kw)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)[0]


async def wait_status(c: httpx.AsyncClient, run_id: str, status: str, timeout: float = 10) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while True:
        snap = (await c.get(f"/evo/agent/runs/{run_id}")).json()
        if snap["status"] == status:
            return snap
        assert loop.time() < end, snap
        await asyncio.sleep(0.01)


async def assert_served(c: httpx.AsyncClient, url: str) -> None:
    r = await c.get(url)
    assert r.status_code == 200, url
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    Image.open(io.BytesIO(r.content)).verify()


# ====================================================================== sign-in and ownership


async def test_starting_and_reading_a_run_needs_a_visitor_id(client):
    signed_out = SIGNED_OUT
    r = await post_run(client, headers=signed_out)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
    bad = await post_run(client, headers={"X-Visitor-Id": "not-a-uuid"})
    assert bad.status_code == 401
    rid = (await named_run(client)).json()["runId"]
    for path in (f"/evo/agent/runs/{rid}", f"/evo/agent/runs/{rid}/events"):
        assert (await client.get(path, headers=signed_out)).status_code == 401


async def test_a_run_is_visible_only_to_its_owner(client):
    rid = (await named_run(client)).json()["runId"]
    await events_of(client, rid)  # the run finishes first
    other = auth("user-2")
    for path in (f"/evo/agent/runs/{rid}", f"/evo/agent/runs/{rid}/events"):
        r = await client.get(path, headers=other)
        assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


# ====================================================================== events


async def test_a_run_streams_its_events_in_order(client):
    r = await named_run(client)
    assert r.status_code == 202
    body = r.json()
    assert body["sire"]["source"] == "name" and body["dam"]["commonName"] == "red fox"
    events = await events_of(client, body["runId"])
    assert [e["type"] for e in events] == ["started", "step", "render", "finalize"]
    assert [e["id"] for e in events] == [1, 2, 3, 4]
    await assert_served(client, events[2]["url"])
    snap = (await client.get(f"/evo/agent/runs/{body['runId']}")).json()
    assert snap["status"] == "succeeded" and snap["creatureId"] == events[-1]["creatureId"]


async def test_resume_from_last_event_id_and_after(client):
    rid = (await named_run(client)).json()["runId"]
    full = await events_of(client, rid)
    assert await events_of(client, rid, headers={"Last-Event-ID": "2"}) == full[2:]
    assert await events_of(client, rid, params={"after": 1}) == full[1:]
    assert await events_of(client, rid, params={"after": 1}, headers={"Last-Event-ID": "3"}) == full[3:]
    assert await events_of(client, rid, headers={"Last-Event-ID": "4"}) == []
    assert await events_of(client, rid, params={"after": "junk"}) == full


async def test_a_failed_run_ends_with_an_error_event(make_client):
    c = await make_client(driver=lambda: ScriptedDriver(fail="UPSTREAM_ERROR"))
    rid = (await named_run(c)).json()["runId"]
    events = await events_of(c, rid)
    assert events[-1]["type"] == "error" and events[-1]["code"] == "UPSTREAM_ERROR"
    assert (await c.get(f"/evo/agent/runs/{rid}")).json()["status"] == "failed"


async def test_unknown_run_is_404(client):
    for path in ("/evo/agent/runs/run_nope", "/evo/agent/runs/run_nope/events"):
        r = await client.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


# ====================================================================== uploads and identify


async def test_upload_checks(client):
    big = b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024)
    gif = b"GIF89a" + b"\x00" * 100
    corrupt = b"\xff\xd8\xff\xe0" + b"garbage" * 50
    cases = [({"sireImage": ("scan.gif", gif, "image/gif")}, 422, "UNSUPPORTED_FILE", "sire"),
             ({"sireImage": ("x.png", gif, "image/png")}, 422, "UNSUPPORTED_FILE", "sire"),  # sniffed, not trusted
             ({"damImage": ("big.jpg", big, "image/jpeg")}, 413, "FILE_TOO_LARGE", "dam"),
             ({"sireImage": ("bad.jpg", corrupt, "image/jpeg")}, 422, "IMAGE_CORRUPT", "sire")]
    for files, status, code, slot in cases:
        r = await post_run(client, files={**photos(), **files})
        assert r.status_code == status, (code, r.text)
        assert r.json()["error"]["code"] == code and r.json()["error"]["details"]["slot"] == slot


async def test_identify_refuses_people_and_non_animals(client):
    token = current_fault.set("human")
    try:
        r = await post_run(client)
    finally:
        current_fault.reset(token)
    assert r.status_code == 422 and r.json()["error"]["code"] == "HUMAN_DETECTED"
    assert r.json()["error"]["details"] == {"slot": "sire"}
    token = current_fault.set("not_animal")
    try:
        r = await post_run(client)
    finally:
        current_fault.reset(token)
    assert r.status_code == 422 and r.json()["error"]["code"] == "NOT_AN_ANIMAL"
    assert (await client.get("/evo/agent/limits")).json()["dailyTotal"]["used"] == 0  # a refused upload is free


async def test_photos_are_identified(client):
    r = await post_run(client)
    assert r.status_code == 202
    assert r.json()["sire"]["commonName"] == "Lion" and r.json()["sire"]["source"] == "image"


async def test_low_confidence_returns_needs_choice_and_no_run(make_client):
    c = await make_client(evo_identify_min_confidence=0.99)
    body = (await post_run(c)).json()
    assert body["status"] == "needs_choice" and body["choice"]["kind"] == "identify"
    assert body["choice"]["slot"] == "sire" and body["choice"]["options"][0]["commonName"] == "Lion"
    assert (await c.get("/evo/agent/limits")).json()["dailyTotal"]["used"] == 0
    assert (await named_run(c)).status_code == 202


async def test_validation_errors(client):
    r = await post_run(client, files={"sireImage": photos()["sireImage"]})
    assert r.status_code == 422 and r.json()["error"]["details"]["slot"] == "dam"
    r = await post_run(client, files={}, data={"sireName": "lion", "damName": "<script>"})
    assert r.status_code == 422 and r.json()["error"]["details"]["slot"] == "dam"


# ====================================================================== caps, queue, rate limit


async def test_daily_and_per_user_caps(make_client):
    c = await make_client(evo_daily_runs=2, evo_visitor_daily_runs=1)
    assert (await named_run(c)).status_code == 202
    r = await named_run(c)
    assert r.status_code == 429
    err = r.json()["error"]
    assert err["code"] == "CAP_REACHED" and err["details"]["scope"] == "visitor_daily" and err["details"]["limit"] == 1
    assert (await named_run(c, headers=auth("user-2"))).status_code == 202
    r = await named_run(c, headers=auth("user-3"))
    err = r.json()["error"]
    assert r.status_code == 429 and err["details"]["scope"] == "daily_total" and err["details"]["limit"] == 2
    assert err["details"]["resetsAt"].endswith("T00:00:00Z") and err["retryable"] is False
    limits = (await c.get("/evo/agent/limits")).json()
    assert limits["liveRuns"] == "capped" and limits["dailyTotal"]["used"] == 2


async def test_limits_signed_in_and_out(client):
    body = (await client.get("/evo/agent/limits")).json()
    assert body["liveRuns"] == "open" and set(body) == {"liveRuns", "unlimited", "dailyTotal", "visitor", "concurrent"}
    assert body["concurrent"] == {"running": 0, "limit": 3, "queued": 0}
    assert body["visitor"] == {"used": 0, "limit": 1000}
    out = await client.get("/evo/agent/limits", headers=SIGNED_OUT)
    assert out.status_code == 200 and out.json()["dailyTotal"]["used"] == 0


async def test_rate_limit_per_ip(make_client):
    c = await make_client(evo_runs_per_minute_per_ip=2)
    for _ in range(2):
        assert (await named_run(c)).status_code == 202
    r = await named_run(c, headers=auth("user-9"))
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) >= 1 and r.json()["error"]["retryAfterMs"] > 0
    assert (await named_run(c, headers={**auth("user-9"), "X-Forwarded-For": "203.0.113.9"})).status_code == 202


async def test_concurrent_limit_queues_and_gives_positions(make_client):
    hold = asyncio.Event()
    drivers = iter([ScriptedDriver(hold=hold), ScriptedDriver(), ScriptedDriver()])
    c = await make_client(driver=lambda: next(drivers), evo_max_concurrent_runs=1)
    first = (await named_run(c)).json()
    assert first["status"] == "running"
    second = (await named_run(c)).json()
    third = (await named_run(c)).json()
    assert (second["status"], second["position"]) == ("queued", 1)
    assert (third["status"], third["position"]) == ("queued", 2)
    assert (await c.get("/evo/agent/limits")).json()["concurrent"] == {"running": 1, "limit": 1, "queued": 2}
    hold.set()
    ev3 = await events_of(c, third["runId"])
    assert [(e["type"], e.get("position")) for e in ev3[:3]] == [("queued", 2), ("queued", 1), ("started", None)]
    assert ev3[-1]["type"] == "finalize"


# ====================================================================== lease and orphans


async def test_a_stale_run_is_interrupted_when_read(client):
    db = client.app.state.services.db
    old = "2026-01-01T00:00:00.000Z"
    await db.put("agent_runs", "run_stale", {"runId": "run_stale", "status": "running", "position": None,
                                             "sire": None, "dam": None, "mode": "realistic", "createdAt": old,
                                             "updatedAt": old, "lastEventId": 1, "creatureId": None,
                                             "error": None, "pendingChoice": None, "owner": visitor_id(),
                                             "events": [{"id": 1, "type": "started", "runId": "run_stale",
                                                         "at": old}]})
    snap = (await client.get("/evo/agent/runs/run_stale")).json()
    assert snap["status"] == "interrupted" and snap["error"]["code"] == "RUN_INTERRUPTED"
    events = await events_of(client, "run_stale")
    assert [e["type"] for e in events] == ["started", "error"] and events[1]["id"] == 2


async def test_orphans_are_interrupted_at_startup(tmp_path):
    s = api_settings(tmp_path)
    app = create_app(s, services=offline_services(s))
    await app.state.services.db.put("agent_runs", "run_orphan", {
        "runId": "run_orphan", "status": "queued", "position": 1, "lastEventId": 0, "events": [],
        "updatedAt": now_iso()})
    async with app.router.lifespan_context(app):
        doc = await app.state.services.db.get("agent_runs", "run_orphan")
    assert doc["status"] == "interrupted" and doc["events"][-1]["type"] == "error"


async def test_a_live_run_heartbeat_keeps_its_lease(make_client):
    hold = asyncio.Event()
    c = await make_client(driver=lambda: ScriptedDriver(hold=hold), run_lease_seconds=0.2)
    rid = (await named_run(c)).json()["runId"]
    await wait_status(c, rid, "running")
    await asyncio.sleep(0.3)
    doc = await c.app.state.services.db.get("agent_runs", rid)
    assert doc["status"] == "running"
    store = c.app.state.agent.store
    store.live.pop(rid)  # as if another process read it: fresh enough, not interrupted
    assert (await store.get(rid))["status"] == "running"
    hold.set()
    store.live[rid] = doc


# ====================================================================== files and serving


async def test_files_endpoint(client):
    url = await client.app.state.agent.files.put("runs/x/img1.png", png(), "image/png")
    r = await client.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert (await client.get("/evo/files/runs/x/nope.png")).status_code == 404
    assert (await client.get("/evo/files/..%2F..%2Fchimera.sqlite3")).status_code in (404, 422)


# ====================================================================== helpers and serving


async def test_single_origin_serves_the_frontend(tmp_path, make_client):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Chimera Lab</title>")
    (dist / "assets" / "index-abc123.js").write_text("console.log('app')")
    (dist / "favicon.svg").write_text("<svg/>")
    c = await make_client(frontend_dist=str(dist))
    for path in ("/", "/chimeras", "/run/run_x"):
        r = await c.get(path)
        assert r.status_code == 200 and "Chimera Lab" in r.text and r.headers["cache-control"] == "no-cache", path
    r = await c.get("/assets/index-abc123.js")
    assert r.status_code == 200 and "console.log" in r.text and "immutable" in r.headers["cache-control"]
    assert (await c.get("/favicon.svg")).status_code == 200
    r = await c.get("/evo/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert (await c.get("/health")).json()["status"] == "ok"
    assert (await c.get("/evo/agent/limits")).status_code == 200
    assert "root:" not in (await c.get("/..%2F..%2Fetc%2Fpasswd")).text


async def test_no_frontend_build_serves_the_api_only(client):
    assert (await client.get("/")).status_code == 404
    assert (await client.get("/evo/agent/limits")).status_code == 200
