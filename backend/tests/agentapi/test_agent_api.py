"""R1 Stream A: the agent API in mock mode against every contract fixture (docs/api_fixtures/).

The fixtures' event sequences are replayed through the real job runner, event store and SSE path (X-Mock-Scenario);
the `agent` scenario runs the engine's real agent loop over the mock adapters. No paid calls.
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

from app.agentapi.creature import HIDDEN_CHECKS, short_args, visible
from app.main import create_app
from app.util import now_iso
from tests.conftest import IMAGES, make_settings

REPO = Path(__file__).resolve().parents[3]
FX = REPO / "docs" / "api_fixtures"
SID = "test-visitor-0001"


def fx(name: str) -> dict[str, Any]:
    return json.loads((FX / name).read_text(encoding="utf-8"))


def api_settings(tmp_path: Path, **over: Any):  # type: ignore[no-untyped-def]
    base = dict(evo_mock_replay_scale=0.0, evo_runs_per_minute_per_ip=1000, evo_visitor_daily_runs=1000,
                evo_daily_runs=1000, evo_keepalive_seconds=15.0, evo_heartbeat_seconds=0.05)
    base.update(over)
    return make_settings(tmp_path, **base)


@pytest.fixture
async def make_client(tmp_path: Path) -> AsyncIterator[Any]:
    stack: list[Any] = []

    async def make(**over: Any) -> httpx.AsyncClient:
        app = create_app(api_settings(tmp_path / f"app{len(stack)}", **over))
        ctx = app.router.lifespan_context(app)
        await ctx.__aenter__()
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                              headers={"X-Session-Id": SID}, timeout=30)
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


async def post_run(c: httpx.AsyncClient, scenario: str | None = None, mode: str = "realistic",
                   files: dict[str, Any] | None = None, data: dict[str, Any] | None = None,
                   headers: dict[str, str] | None = None) -> httpx.Response:
    h = dict(headers or {})
    if scenario:
        h["X-Mock-Scenario"] = scenario
    return await c.post("/evo/agent/runs", data={"mode": mode, **(data or {})},
                        files=photos() if files is None else files, headers=h)


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


def norm(e: dict[str, Any]) -> dict[str, Any]:
    """Drop what differs per run: the run id, times, image URLs, the creature id and the choice id."""
    out = {k: v for k, v in e.items() if k not in ("runId", "at")}
    for k in ("url", "imageUrl"):
        if k in out:
            out[k] = Path(str(out[k])).name
    for k in ("creatureId", "choiceId", "expiresAt"):
        if k in out:
            out[k] = "*"
    return out


async def assert_served(c: httpx.AsyncClient, url: str) -> None:
    r = await c.get(url)
    assert r.status_code == 200, url
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    Image.open(io.BytesIO(r.content)).verify()


def fixture_post(name: str) -> tuple[str, dict[str, Any]]:
    f = fx(name)
    return f["request"]["fields"]["mode"], f


async def wait_status(c: httpx.AsyncClient, run_id: str, status: str, timeout: float = 10) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while True:
        snap = (await c.get(f"/evo/agent/runs/{run_id}")).json()
        if snap["status"] == status:
            return snap
        assert loop.time() < end, snap
        await asyncio.sleep(0.01)


# ====================================================================== fixture replays


@pytest.mark.parametrize("scenario,name", [("success", "run_success.json"), ("cap", "run_cap.json"),
                                           ("error", "run_error.json"), ("queued", "run_queued.json")])
async def test_run_replays_the_fixture_event_sequence(client, scenario, name):
    mode, f = fixture_post(name)
    r = await post_run(client, scenario, mode)
    assert r.status_code == f["response"]["status"] == 202
    body, want = r.json(), f["response"]["body"]
    rid = body["runId"]
    assert body["eventsUrl"] == f"/evo/agent/runs/{rid}/events" and body["runUrl"] == f"/evo/agent/runs/{rid}"
    drop = ("runId", "eventsUrl", "runUrl")
    assert {k: v for k, v in body.items() if k not in drop} == {k: v for k, v in want.items() if k not in drop}

    events = await events_of(client, rid)
    assert [e["id"] for e in events] == list(range(1, len(f["events"]) + 1))  # from 1, no gaps
    assert [norm(e) for e in events] == [norm(e) for e in f["events"]]
    assert all(e["runId"] == rid and e["at"].endswith("Z") for e in events)
    for e in events:
        if e["type"] == "render":
            assert e["url"].startswith(f"/evo/files/runs/{rid}/")
            await assert_served(client, e["url"])

    snap = (await client.get(f"/evo/agent/runs/{rid}")).json()
    assert set(snap) == set(fx("run_success.json")["snapshot"])
    assert snap["lastEventId"] == len(f["events"]) and snap["pendingChoice"] is None and snap["position"] is None
    if scenario == "error":
        assert snap["status"] == "failed" and snap["creatureId"] is None
        assert snap["error"] == {k: f["events"][-1][k] for k in ("code", "message", "retryable")}
    else:
        assert snap["status"] == "succeeded" and snap["creatureId"] == events[-1]["creatureId"]


async def test_success_snapshot_and_creature_match_the_fixtures(client):
    mode, f = fixture_post("run_success.json")
    rid = (await post_run(client, "success", mode)).json()["runId"]
    events = await events_of(client, rid)
    snap = (await client.get(f"/evo/agent/runs/{rid}")).json()
    want = f["snapshot"]
    for k in ("status", "position", "mode", "lastEventId", "error", "pendingChoice"):
        assert snap[k] == want[k], k
    cid = events[-1]["creatureId"]
    r = await client.get(f"/evo/creatures/{cid}")
    assert r.status_code == 200
    got, exp = r.json(), fx("creature_b09.json")["response"]["body"]
    assert set(got) == set(exp)
    assert got["creatureId"] == cid and got["runId"] == rid and got["showcase"] is False
    for k in ("title", "mode", "generatedLabel", "realHybrid", "host", "canItLive", "remainingFailures",
              "hiddenChecks", "stats", "card", "plan"):
        assert got[k] == exp[k], k
    assert [Path(i["url"]).name for i in got["images"]] == [Path(i["url"]).name for i in exp["images"]]
    for i in got["images"]:
        await assert_served(client, i["url"])
    await assert_served(client, got["anatomyMap"]["overlayUrl"])
    await assert_served(client, got["finalChoice"]["agentPick"]["imageUrl"])
    assert got["imageUrl"] == events[-1]["imageUrl"]


async def test_host_tie_waits_for_the_users_choice(client):
    mode, f = fixture_post("run_host_tie.json")
    rid = (await post_run(client, "host_tie", mode)).json()["runId"]
    snap = await wait_status(client, rid, "needs_choice")
    pc = snap["pendingChoice"]
    want = next(e for e in f["events"] if e["type"] == "needs_choice")
    assert pc["kind"] == "host_tie" and pc["options"] == want["options"] and pc["question"] == want["question"]
    reader = asyncio.create_task(events_of(client, rid))
    await asyncio.sleep(0.05)
    r = await client.post(f"/evo/agent/runs/{rid}/choice", json={"choiceId": pc["choiceId"],
                                                                 "answer": "domestic goat"})
    assert r.status_code == 200 and r.json() == f["choiceRequest"]["response"]["body"]
    events = await reader
    assert [norm(e) for e in events] == [norm(e) for e in f["events"]]
    nc = next(e for e in events if e["type"] == "needs_choice")
    assert nc["choiceId"] == pc["choiceId"] and nc["expiresAt"] == pc["expiresAt"]
    again = await client.post(f"/evo/agent/runs/{rid}/choice", json={"choiceId": pc["choiceId"],
                                                                     "answer": "domestic goat"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "VALIDATION_FAILED"
    cr = (await client.get(f"/evo/creatures/{events[-1]['creatureId']}")).json()
    assert cr["host"]["chosenBy"] == "user" and cr["hiddenChecks"] == 3
    assert not {f["key"] for f in cr["remainingFailures"]} & set(HIDDEN_CHECKS)
    assert not {f["key"] for f in cr["card"]["remaining_failures"]} & set(HIDDEN_CHECKS)


async def test_choice_errors(client):
    rid = (await post_run(client, "host_tie")).json()["runId"]
    pc = (await wait_status(client, rid, "needs_choice"))["pendingChoice"]
    url = f"/evo/agent/runs/{rid}/choice"
    bad = await client.post(url, json={"choiceId": pc["choiceId"], "answer": "giraffe"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_FAILED"
    wrong = await client.post(url, json={"choiceId": "choice_nope", "answer": "tortoise"})
    assert wrong.status_code == 409
    missing = await client.post("/evo/agent/runs/run_nope/choice", json={"choiceId": "x", "answer": "y"})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert (await client.post(url, json={"choiceId": pc["choiceId"], "answer": "tortoise"})).status_code == 200
    events = await events_of(client, rid)
    res = next(e for e in events if e["type"] == "choice_resolved")
    assert res["answer"] == "tortoise" and res["by"] == "user"
    ask = next(e for e in events if e["type"] == "step" and e["tool"] == "ask_user")
    assert ask["summary"] == "answer: tortoise" and ask["id"] == res["id"] + 1


async def test_choice_expires_and_the_agent_decides(make_client):
    c = await make_client(evo_choice_seconds=0.05)
    rid = (await post_run(c, "host_tie")).json()["runId"]
    events = await events_of(c, rid)
    res = next(e for e in events if e["type"] == "choice_resolved")
    assert res["answer"] is None and res["by"] == "timeout"
    ask = next(e for e in events if e["type"] == "step" and e["tool"] == "ask_user")
    assert ask["summary"].startswith("no answer")
    assert events[-1]["type"] == "finalize"
    late = await c.post(f"/evo/agent/runs/{rid}/choice", json={"choiceId": res["choiceId"], "answer": "tortoise"})
    assert late.status_code == 409


async def test_keep_alive_pings_while_waiting(make_client):
    c = await make_client(evo_choice_seconds=0.4, evo_keepalive_seconds=0.05)
    rid = (await post_run(c, "host_tie")).json()["runId"]
    r = await c.get(f"/evo/agent/runs/{rid}/events")
    events, pings = parse_sse(r.text)
    assert pings >= 2 and events[-1]["type"] == "finalize"


# ====================================================================== resume


async def test_resume_from_last_event_id_and_after(client):
    rid = (await post_run(client, "success")).json()["runId"]
    full = await events_of(client, rid)
    tail = await events_of(client, rid, headers={"Last-Event-ID": "10"})
    assert tail == full[10:]
    assert await events_of(client, rid, params={"after": 5}) == full[5:]
    assert await events_of(client, rid, params={"after": 2}, headers={"Last-Event-ID": "12"}) == full[12:]  # header wins
    assert await events_of(client, rid, headers={"Last-Event-ID": "16"}) == []  # ended: immediate close
    assert await events_of(client, rid, params={"after": "junk"}) == full


async def test_resume_mid_run_gets_the_replay_then_live_events(client):
    rid = (await post_run(client, "host_tie")).json()["runId"]
    pc = (await wait_status(client, rid, "needs_choice"))["pendingChoice"]
    snap = (await client.get(f"/evo/agent/runs/{rid}")).json()
    reader = asyncio.create_task(events_of(client, rid, headers={"Last-Event-ID": "3"}))
    await asyncio.sleep(0.05)
    await client.post(f"/evo/agent/runs/{rid}/choice", json={"choiceId": pc["choiceId"], "answer": "domestic goat"})
    events = await reader
    assert [e["id"] for e in events] == list(range(4, 30)) and snap["lastEventId"] == 5


async def test_unknown_run_is_404(client):
    for path in ("/evo/agent/runs/run_nope", "/evo/agent/runs/run_nope/events"):
        r = await client.get(path)
        assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


# ====================================================================== identify and refusals


@pytest.mark.parametrize("scenario,index", [("refused_human", 0), ("refused_type", 1), ("refused_size", 2)])
async def test_mock_refusals_match_the_fixture(client, scenario, index):
    case = fx("upload_refused.json")["cases"][index]
    r = await post_run(client, scenario)
    assert r.status_code == case["response"]["status"]
    err = r.json()["error"]
    want = case["response"]["body"]["error"]
    assert {k: err[k] for k in ("code", "message", "retryable", "details")} == want


async def test_real_upload_checks(client):
    big = b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024)
    gif = b"GIF89a" + b"\x00" * 100
    corrupt = b"\xff\xd8\xff\xe0" + b"garbage" * 50
    cases = [({"sireImage": ("scan.gif", gif, "image/gif")}, 422, "UNSUPPORTED_FILE", "sire"),
             ({"sireImage": ("x.png", gif, "image/png")}, 422, "UNSUPPORTED_FILE", "sire"),  # sniffed, not trusted
             ({"damImage": ("big.jpg", big, "image/jpeg")}, 413, "FILE_TOO_LARGE", "dam"),
             ({"sireImage": ("bad.jpg", corrupt, "image/jpeg")}, 422, "IMAGE_CORRUPT", "sire")]
    for files, status, code, slot in cases:
        both = {**photos(), **files}
        r = await post_run(client, "agent", files=both)
        assert r.status_code == status, (code, r.text)
        err = r.json()["error"]
        assert err["code"] == code and err["details"]["slot"] == slot
    r = await post_run(client, "agent", files={**photos(), "damImage": ("big.jpg", big, "image/jpeg")})
    assert r.json()["error"]["message"] == "Images must be 8 MB or smaller."
    assert r.json()["error"]["details"]["maxBytes"] == 8 * 1024 * 1024


async def test_real_identify_refuses_people_and_non_animals(client):
    r = await post_run(client, "agent", headers={"X-Mock-Fault": "human"})
    assert r.status_code == 422
    assert r.json()["error"] == {**r.json()["error"], "code": "HUMAN_DETECTED", "details": {"slot": "sire"},
                                 "message": "This looks like a photo of a person. Chimera Lab only uses animal photos."}
    r = await post_run(client, "agent", headers={"X-Mock-Fault": "not_animal"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "NOT_AN_ANIMAL"
    assert r.json()["error"]["details"] == {"slot": "dam"}
    assert r.json()["error"]["message"] == "We couldn't find an animal in this image."
    limits = (await client.get("/evo/agent/limits")).json()
    assert limits["dailyTotal"]["used"] == 0  # a refused upload uses no run


async def test_identify_choice_fixture_and_follow_up(client):
    f = fx("identify_choice.json")
    r = await post_run(client, "identify_choice")
    assert r.status_code == 200 and r.json() == f["response"]["body"]
    fields = f["followUp"]["request"]["fields"]
    r = await client.post("/evo/agent/runs", data=fields, headers={"X-Mock-Scenario": "identify_choice"})
    assert r.status_code == 202
    want = f["followUp"]["response"]["body"]
    assert r.json()["sire"] == want["sire"] and r.json()["dam"] == want["dam"] and r.json()["status"] == "running"


async def test_low_confidence_returns_needs_choice_and_no_run(make_client):
    c = await make_client(evo_identify_min_confidence=0.99)
    r = await post_run(c, "agent")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "needs_choice" and body["choice"]["kind"] == "identify"
    assert body["choice"]["slot"] == "sire" and body["choice"]["allowOther"] is True
    assert body["choice"]["options"][0]["commonName"] == "Lion"
    assert body["identified"] == {"sire": None, "dam": None}
    assert (await c.get("/evo/agent/limits")).json()["dailyTotal"]["used"] == 0
    named = await post_run(c, "agent", files={}, data={"sireName": "lion", "damName": "red fox"})
    assert named.status_code == 202 and named.json()["sire"]["source"] == "name"


async def test_validation_errors(client):
    r = await post_run(client, "agent", files={"sireImage": photos()["sireImage"]})
    assert r.status_code == 422 and r.json()["error"]["details"]["slot"] == "dam"
    r = await post_run(client, "agent", mode="goal")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"
    r = await post_run(client, "agent", files={}, data={"sireName": "lion", "damName": "<script>"})
    assert r.status_code == 422 and r.json()["error"]["details"]["slot"] == "dam"
    r = await post_run(client, "nonsense")
    assert r.status_code == 422


# ====================================================================== the real agent path


async def test_agent_scenario_runs_the_engine_agent(client):
    r = await post_run(client, "agent")
    assert r.status_code == 202
    body = r.json()
    assert body["sire"] == {"commonName": "Lion", "scientificName": "Panthera leo", "source": "image",
                            "confidence": body["sire"]["confidence"]}
    events = await events_of(client, body["runId"])
    types = [e["type"] for e in events]
    assert types[0] == "started" and types[-1] == "finalize"
    assert events[0]["caps"] == {"renders": 4, "toolCalls": 30, "seconds": 900}
    assert [e["id"] for e in events] == list(range(1, len(events) + 1))
    steps = [e for e in events if e["type"] == "step"]
    assert [s["n"] for s in steps] == list(range(1, len(steps) + 1))
    for s in steps:
        assert set(s) >= {"n", "tool", "args", "summary", "reason", "cards", "ok", "error"}
    for e in events:
        if e["type"] in ("render", "inspect"):  # pairing: the step with the same n comes first
            i = events.index(e)
            assert any(p["type"] == "step" and p["n"] == e["n"] for p in events[:i])
        if e["type"] == "render":
            await assert_served(client, e["url"])
            assert e["rendersUsed"] == 1 and e["rendersLeft"] == 3
    fin = events[-1]
    cr = (await client.get(f"/evo/creatures/{fin['creatureId']}")).json()
    assert set(cr) == set(fx("creature_b09.json")["response"]["body"])
    assert cr["imageUrl"] == fin["imageUrl"] and cr["runId"] == body["runId"]
    assert cr["anatomyMap"]["parts"] and cr["anatomyMap"]["overlayUrl"]
    await assert_served(client, cr["anatomyMap"]["overlayUrl"])
    assert cr["stats"]["renders"] == 1 and cr["plan"]["id"].startswith("crt_")
    doc = await client.app.state.services.db.get("creatures", fin["creatureId"])
    assert doc["trace"] and doc["kind"] == "evo_agent"


async def test_soft_time_cap_fires_and_hard_cap_stops(make_client):
    c = await make_client(evo_run_soft_seconds=0.0)
    events = await events_of(c, (await post_run(c, "agent")).json()["runId"])
    caps = [e for e in events if e["type"] == "cap_reached"]
    assert caps and caps[0]["scope"] == "time" and events[-1]["type"] == "error"
    c2 = await make_client(evo_run_hard_seconds=0.0, evo_mock_replay_scale=1.0)
    events = await events_of(c2, (await post_run(c2, "success")).json()["runId"])
    assert events[-1]["type"] == "error" and events[-1]["code"] == "RUN_INTERRUPTED"


async def test_deadline_brain_finalizes_the_best_image():
    from app.agentapi.jobs import DeadlineBrain

    class St:
        finalized = None
        order = ["img1", "img2"]
        images = {"img2": type("I", (), {"inspect": None})()}

    class R:
        state = St()

        def best_image_id(self):  # noqa: ANN201
            return "img1"

    class J:
        soft_deadline = 0.0
        runner = type("X", (), {"settings": type("S", (), {"evo_run_soft_seconds": 840})()})()
        extra: dict[str, Any] = {}
        capped: list[str] = []

        async def cap(self, scope, limit):  # noqa: ANN001, ANN201
            self.capped.append(scope)

    async def flush():  # noqa: ANN202
        return None

    j = J()
    j.extra["flush"] = flush
    b = DeadlineBrain(object(), j)
    b.bind(R())
    t = await b.next([], [])
    assert j.capped == ["time"] and t.calls[0]["name"] == "finalize" and t.calls[0]["arguments"]["image_id"] == "img1"
    await b.next([], [])
    assert j.capped == ["time"]  # once


# ====================================================================== caps, queue, rate limit


async def test_daily_and_visitor_caps(make_client):
    c = await make_client(evo_daily_runs=2, evo_visitor_daily_runs=1)
    assert (await post_run(c, "success")).status_code == 202
    r = await post_run(c, "success")
    assert r.status_code == 429
    err = r.json()["error"]
    assert err["code"] == "CAP_REACHED" and err["details"]["scope"] == "visitor_daily" and err["details"]["limit"] == 1
    other = {"X-Session-Id": "another-visitor-02"}
    assert (await post_run(c, "success", headers=other)).status_code == 202
    r = await post_run(c, "success", headers={"X-Session-Id": "third-visitor-003"})
    want = fx("cap_daily.json")["response"]
    assert r.status_code == want["status"]
    err = r.json()["error"]
    assert err["code"] == "CAP_REACHED" and err["message"] == want["body"]["error"]["message"]
    assert err["details"]["scope"] == "daily_total" and err["details"]["limit"] == 2
    assert err["details"]["resetsAt"].endswith("T00:00:00Z") and err["retryable"] is False
    limits = (await c.get("/evo/agent/limits")).json()
    assert set(limits) == set(fx("limits.json")["cases"][1]["response"]["body"])
    assert limits["liveRuns"] == "capped" and limits["dailyTotal"]["used"] == 2
    g = await c.get("/evo/gallery")  # the gallery works when live runs are capped
    assert g.status_code == 200 and len(g.json()["items"]) >= 6


async def test_mock_cap_daily_scenario(client):
    r = await post_run(client, "cap_daily")
    want = fx("cap_daily.json")["response"]
    assert r.status_code == 429 and r.json()["error"] == {**want["body"]["error"], **{
        k: v for k, v in r.json()["error"].items() if k not in want["body"]["error"]}}
    lim = (await client.get("/evo/agent/limits", headers={"X-Mock-Scenario": "cap_daily"})).json()
    assert lim["liveRuns"] == "capped"


async def test_limits_shape(client):
    body = (await client.get("/evo/agent/limits")).json()
    want = fx("limits.json")["cases"][0]["response"]["body"]
    assert body["liveRuns"] == "open" and set(body) == set(want)
    for k in want:
        if isinstance(want[k], dict):
            assert set(body[k]) == set(want[k]), k
    assert body["concurrent"] == {"running": 0, "limit": 3, "queued": 0}
    assert body["visitor"] == {"used": 0, "limit": 1000}


async def test_rate_limit_per_ip(make_client):
    c = await make_client(evo_runs_per_minute_per_ip=2)
    for _ in range(2):
        assert (await post_run(c, "identify_choice")).status_code == 200
    r = await post_run(c, "identify_choice", headers={"X-Session-Id": "other-session-9"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    assert int(r.headers["retry-after"]) >= 1 and r.json()["error"]["retryAfterMs"] > 0
    r = await post_run(c, "identify_choice", headers={"X-Forwarded-For": "203.0.113.9"})
    assert r.status_code == 200  # another client IP (as the proxy reports it)


async def test_concurrent_limit_queues_and_gives_positions(make_client):
    c = await make_client(evo_max_concurrent_runs=1)
    first = (await post_run(c, "host_tie")).json()
    assert first["status"] == "running"
    pc = (await wait_status(c, first["runId"], "needs_choice"))["pendingChoice"]
    second = (await post_run(c, "success")).json()
    third = (await post_run(c, "success")).json()
    assert (second["status"], second["position"]) == ("queued", 1)
    assert (third["status"], third["position"]) == ("queued", 2)
    lim = (await c.get("/evo/agent/limits")).json()
    assert lim["concurrent"] == {"running": 1, "limit": 1, "queued": 2}
    await c.post(f"/evo/agent/runs/{first['runId']}/choice", json={"choiceId": pc["choiceId"], "answer": "tortoise"})
    ev3 = await events_of(c, third["runId"])
    assert [(e["type"], e.get("position")) for e in ev3[:3]] == [("queued", 2), ("queued", 1), ("started", None)]
    assert all(e["ahead"] == e["position"] for e in ev3 if e["type"] == "queued")
    ev2 = await events_of(c, second["runId"])
    assert [e["type"] for e in ev2[:2]] == ["queued", "started"] and ev2[-1]["type"] == "finalize"


# ====================================================================== lease and orphans


async def test_a_stale_run_is_interrupted_when_read(client):
    db = client.app.state.services.db
    old = "2026-01-01T00:00:00.000Z"
    await db.put("agent_runs", "run_stale", {"runId": "run_stale", "status": "running", "position": None,
                                             "sire": None, "dam": None, "mode": "realistic", "createdAt": old,
                                             "updatedAt": old, "lastEventId": 1, "creatureId": None,
                                             "error": None, "pendingChoice": None,
                                             "events": [{"id": 1, "type": "started", "runId": "run_stale",
                                                         "at": old}]})
    snap = (await client.get("/evo/agent/runs/run_stale")).json()
    assert snap["status"] == "interrupted" and snap["error"]["code"] == "RUN_INTERRUPTED"
    events = await events_of(client, "run_stale")
    assert [e["type"] for e in events] == ["started", "error"] and events[1]["id"] == 2


async def test_orphans_are_interrupted_at_startup(tmp_path):
    s = api_settings(tmp_path)
    app = create_app(s)
    await app.state.services.db.put("agent_runs", "run_orphan", {
        "runId": "run_orphan", "status": "queued", "position": 1, "lastEventId": 0, "events": [],
        "updatedAt": now_iso()})
    async with app.router.lifespan_context(app):
        doc = await app.state.services.db.get("agent_runs", "run_orphan")
    assert doc["status"] == "interrupted" and doc["events"][-1]["type"] == "error"


async def test_a_live_run_heartbeat_keeps_its_lease(make_client):
    c = await make_client(evo_choice_seconds=0.5, run_lease_seconds=0.2)
    rid = (await post_run(c, "host_tie")).json()["runId"]
    await wait_status(c, rid, "needs_choice")
    await asyncio.sleep(0.3)
    doc = await c.app.state.services.db.get("agent_runs", rid)
    assert doc["status"] == "needs_choice"
    store = c.app.state.agent.store
    store.live.pop(rid)  # as if another process read it: fresh enough, not interrupted
    assert (await store.get(rid))["status"] == "needs_choice"
    store.live[rid] = doc


# ====================================================================== gallery and creatures


async def test_gallery_showcase_first_then_newest(client):
    want = fx("gallery.json")["response"]["body"]["items"]
    g = (await client.get("/evo/gallery")).json()
    items = g["items"]
    assert [i["title"] for i in items[:6]] == [w["title"] for w in want]
    assert [i["creatureId"] for i in items[:6]] == [f"crt_s5_{c}" for c in ("b09", "b01", "b03", "b08", "b11", "b05")]
    for got, exp in zip(items, want):
        assert set(got) == set(exp) and got["showcase"] is True
        assert (got["sire"], got["dam"], got["mode"]) == (exp["sire"], exp["dam"], exp["mode"])
        assert Path(got["imageUrl"]).name == Path(exp["imageUrl"]).name.split("_", 1)[1]
        await assert_served(client, got["imageUrl"])
    assert g["nextCursor"] is None
    a = (await post_run(client, "success")).json()["runId"]
    await events_of(client, a)
    b = (await post_run(client, "queued", mode="mythic")).json()["runId"]
    await events_of(client, b)
    items = (await client.get("/evo/gallery")).json()["items"]
    assert len(items) == 8 and [i["showcase"] for i in items] == [True] * 6 + [False, False]
    assert items[6]["title"] == "lion × golden eagle"  # newest first after the showcase
    page1 = (await client.get("/evo/gallery", params={"limit": 5})).json()
    page2 = (await client.get("/evo/gallery", params={"limit": 5, "cursor": page1["nextCursor"]})).json()
    assert [i["creatureId"] for i in page1["items"] + page2["items"]] == [i["creatureId"] for i in items]
    assert page2["nextCursor"] is None


async def test_showcase_creature_view(client):
    cr = (await client.get("/evo/creatures/crt_s5_b09")).json()
    exp = fx("creature_b09.json")["response"]["body"]
    assert set(cr) == set(exp) and cr["showcase"] is True and cr["runId"] is None
    for k in ("title", "sire", "dam", "mode", "realHybrid", "host", "canItLive", "remainingFailures", "hiddenChecks",
              "stats", "plan", "card"):
        assert cr[k] == exp[k], k
    assert cr["anatomyMap"]["parts"] == exp["anatomyMap"]["parts"]
    assert cr["finalChoice"]["agree"] is True and cr["finalChoice"]["agentPick"]["imageId"] == "img2"
    assert [i["imageId"] for i in cr["images"]] == ["img1", "img2"]
    r = await client.get("/evo/creatures/crt_nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


async def test_showcase_list_is_configurable(make_client):
    c = await make_client(evo_showcase="b05,b02")
    items = (await c.get("/evo/gallery")).json()["items"]
    assert [i["creatureId"] for i in items] == ["crt_s5_b05", "crt_s5_b02"]
    c2 = await make_client(evo_showcase="")
    assert (await c2.get("/evo/gallery")).json() == {"items": [], "nextCursor": None}


async def test_files_endpoint(client):
    await client.get("/evo/gallery")
    r = await client.get("/evo/files/showcase/b09/img2.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert (await client.get("/evo/files/showcase/b09/nope.jpg")).status_code == 404
    assert (await client.get("/evo/files/..%2F..%2Fchimera.sqlite3")).status_code in (404, 422)


# ====================================================================== helpers and serving


def test_visible_and_short_args():
    fails = [{"key": "material_look", "kind": "covering", "text": "a"}, {"key": "third_animal", "kind": "structural",
                                                                         "text": "b", "status": "fail"}]
    keep, hidden = visible(fails)
    assert keep == [{"key": "third_animal", "kind": "structural", "text": "b"}] and hidden == 1
    out = short_args({"a": "x" * 200, "b": ["k"] * 50, "c": 3, "d": ["ok"]})
    assert len(out["a"]) == 120 and out["a"].endswith("…") and isinstance(out["b"], str) and len(out["b"]) == 120
    assert out["c"] == 3 and out["d"] == ["ok"]


async def test_single_origin_serves_the_frontend(tmp_path, make_client):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Chimera Lab</title>")
    (dist / "assets" / "index-abc123.js").write_text("console.log('app')")
    (dist / "favicon.svg").write_text("<svg/>")
    c = await make_client(frontend_dist=str(dist))
    for path in ("/", "/gallery", "/creature/crt_s5_b09", "/run/run_x"):
        r = await c.get(path)
        assert r.status_code == 200 and "Chimera Lab" in r.text and r.headers["cache-control"] == "no-cache", path
    r = await c.get("/assets/index-abc123.js")  # Vite's bundle, not the v1 /assets/{asset_id} route
    assert r.status_code == 200 and "console.log" in r.text and "immutable" in r.headers["cache-control"]
    assert (await c.get("/favicon.svg")).status_code == 200
    r = await c.get("/evo/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert (await c.get("/health")).json()["status"] in ("ok", "degraded")
    assert (await c.get("/assets/ast_missing")).json()["error"]["code"] == "NOT_FOUND"
    assert (await c.get("/evo/gallery")).status_code == 200
    assert (await c.get("/../../etc/passwd")).status_code in (200, 404)  # never a file outside dist
    assert "root:" not in (await c.get("/..%2F..%2Fetc%2Fpasswd")).text


async def test_no_frontend_build_serves_the_api_only(client):
    assert (await client.get("/")).status_code == 404
    assert (await client.get("/evo/agent/limits")).status_code == 200
