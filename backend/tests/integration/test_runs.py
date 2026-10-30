"""Full fusion runs in mock mode, plus every fault from TASKSHEET 4.5."""

import asyncio

import httpx
import pytest

from app.main import create_app
from tests.conftest import IMAGES, fusion_graph, make_settings, start_run, two_assets, upload, wait_run

STEP_KEYS = ["load_inputs", "identify", "match", "hybrid_check", "rules_check", "compile", "generate", "store"]


async def test_happy_path_lion_tiger(client):
    a, b = await two_assets(client)
    r = await start_run(client, fusion_graph(a, b))
    assert r.status_code == 201
    run = r.json()
    assert [s["key"] for s in run["steps"]] == STEP_KEYS
    assert r.headers["etag"]
    done = await wait_run(client, run["id"])
    assert done["status"] == "succeeded", done
    assert all(s["status"] == "succeeded" for s in done["steps"])
    spec = done["result"]["spec"]
    assert [p["match"]["animalId"] for p in spec["parents"]] == ["lion", "tiger"]
    assert spec["realHybrid"]["name"] == "Liger"
    assert {w["ruleId"] for w in spec["warnings"]} == {"R-T1-02"}
    assert "Reference image 1 shows a lion" in spec["prompt"]
    assert spec["model"] == {"vision": "mock-muse-spark", "image": "mock-muse-image"}
    img = await client.get(done["result"]["imageUrl"])
    # Muse Image returns WebP; the mock replays that shape (L1-09)
    assert img.status_code == 200 and img.content[:4] == b"RIFF" and img.content[8:12] == b"WEBP"
    assert done["result"]["metaResponseId"].startswith("resp-mock-")


async def test_unmatched_and_warnings_path(client):
    a, b = await two_assets(client, "common_octopus", "scarlet_macaw")
    done = await wait_run(client, (await start_run(client, fusion_graph(a, b))).json()["id"])
    assert done["status"] == "succeeded"
    warn_ids = {w["ruleId"] for w in done["result"]["spec"]["warnings"] if w["severity"] == "warning"}
    assert "R-A2-01" in warn_ids and done["result"]["spec"]["realHybrid"] is None


async def test_mock_generation_is_deterministic(client):
    a, b = await two_assets(client)
    r1 = await wait_run(client, (await start_run(client, fusion_graph(a, b), key="x1")).json()["id"])
    r2 = await wait_run(client, (await start_run(client, fusion_graph(a, b), key="x2")).json()["id"])
    i1 = (await client.get(r1["result"]["imageUrl"])).content
    i2 = (await client.get(r2["result"]["imageUrl"])).content
    assert i1 == i2 and r1["result"]["assetId"] != r2["result"]["assetId"]


async def test_idempotency_key_returns_same_run(client):
    a, b = await two_assets(client)
    r1 = await start_run(client, fusion_graph(a, b), key="same")
    r2 = await start_run(client, fusion_graph(a, b), key="same")
    assert r1.json()["id"] == r2.json()["id"] and r2.status_code == 200


async def test_missing_idempotency_key(client):
    a, b = await two_assets(client)
    r = await client.post("/runs", json={"graph": fusion_graph(a, b), "nodeId": "fuse"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_etag_304(client):
    a, b = await two_assets(client)
    run = (await start_run(client, fusion_graph(a, b))).json()
    done = await wait_run(client, run["id"])
    r = await client.get(f"/runs/{run['id']}")
    r304 = await client.get(f"/runs/{run['id']}", headers={"If-None-Match": r.headers["etag"]})
    assert r304.status_code == 304 and done["version"] == r.json()["version"]


async def test_duplicate_inputs_rejected_before_run(client):
    a, _ = await two_assets(client)
    r = await start_run(client, fusion_graph(a, a))
    assert r.status_code == 422 and r.json()["error"]["code"] == "DUPLICATE_INPUTS"


async def test_duplicate_content_caught_by_load_inputs(client):
    a = (await upload(client, IMAGES / "lion.jpg")).json()["assetId"]
    b = (await upload(client, IMAGES / "lion.jpg", "copy.jpg")).json()["assetId"]
    done = await wait_run(client, (await start_run(client, fusion_graph(a, b))).json()["id"])
    assert done["status"] == "failed" and done["error"]["code"] == "DUPLICATE_INPUTS"
    assert done["steps"][0]["status"] == "failed" and done["steps"][1]["status"] == "skipped"


@pytest.mark.parametrize("graph_kind", ["missing_input", "not_uploaded", "bad_node"])
async def test_graph_invalid(client, graph_kind):
    a, b = await two_assets(client)
    g = fusion_graph(a, b)
    node = "fuse"
    if graph_kind == "missing_input":
        g["edges"] = g["edges"][:1]
    elif graph_kind == "not_uploaded":
        g["nodes"][1]["data"] = {}
    else:
        node = "img-a"
    r = await client.post("/runs", json={"graph": g, "nodeId": node}, headers={"Idempotency-Key": graph_kind})
    assert r.status_code == 422 and r.json()["error"]["code"] == "GRAPH_INVALID"


@pytest.mark.parametrize("fault,code,failed_step,slot", [
    ("timeout", "UPSTREAM_TIMEOUT", "identify", None),
    ("rate_limit", "RATE_LIMITED", "identify", None),
    ("server_error", "UPSTREAM_ERROR", "generate", None),
    ("refusal", "MODEL_REFUSED", "generate", None),
    ("not_animal", "NOT_AN_ANIMAL", "identify", "B"),
    ("human", "HUMAN_DETECTED", "identify", "A"),
    ("corrupt_output", "UPSTREAM_ERROR", "generate", None),
    ("budget", "BUDGET_EXCEEDED", "generate", None),
])
async def test_faults_map_to_error_codes(client, fault, code, failed_step, slot):
    a, b = await two_assets(client)
    run = (await start_run(client, fusion_graph(a, b), key=f"f-{fault}", fault=fault)).json()
    done = await wait_run(client, run["id"])
    assert done["status"] == "failed"
    assert done["error"]["code"] == code
    failed = [s["key"] for s in done["steps"] if s["status"] == "failed"]
    assert failed == [failed_step]
    assert done["failedInput"] == slot
    assert "Traceback" not in str(done)


async def test_retryable_flags(client):
    a, b = await two_assets(client)
    done = await wait_run(client, (await start_run(client, fusion_graph(a, b), "r1", "server_error")).json()["id"])
    assert done["error"]["retryable"] is True
    done = await wait_run(client, (await start_run(client, fusion_graph(a, b), "r2", "refusal")).json()["id"])
    assert done["error"]["retryable"] is False


async def test_slow_fault_still_succeeds(tmp_path):
    app = create_app(make_settings(tmp_path, mock_delay_scale=0.001))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        done = await wait_run(c, (await start_run(c, fusion_graph(a, b), fault="slow")).json()["id"])
    assert done["status"] == "succeeded"


async def test_fault_header_ignored_in_real_mode(tmp_path):
    from app.api.deps import mock_fault

    class Req:
        headers = {"x-mock-fault": "refusal"}

        class app:
            class state:
                class services:
                    class settings:
                        chimera_mode = "real"

    assert mock_fault(Req()) is None  # type: ignore[arg-type]


async def test_crash_mid_run_becomes_interrupted_after_lease(tmp_path):
    app = create_app(make_settings(tmp_path, run_lease_seconds=0.2))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        run = (await start_run(c, fusion_graph(a, b), fault="crash_mid_run")).json()
        await asyncio.sleep(0.1)
        mid = (await c.get(f"/runs/{run['id']}")).json()
        assert mid["status"] == "running"
        await asyncio.sleep(0.3)
        done = (await c.get(f"/runs/{run['id']}")).json()
    assert done["status"] == "interrupted"
    assert done["error"]["code"] == "RUN_INTERRUPTED" and done["error"]["retryable"] is True


async def test_backend_restart_interrupts_orphans(tmp_path):
    settings = make_settings(tmp_path, mock_delay_scale=1.0)
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        run = (await start_run(c, fusion_graph(a, b))).json()
        await asyncio.sleep(0.05)
    for t in list(app.state.runs.tasks.values()):
        t.cancel()
    app2 = create_app(settings)  # "restarted" process sharing the same SQLite file
    assert await app2.state.runs.interrupt_orphans() == 1
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app2), base_url="http://t") as c:
        assert (await c.get(f"/runs/{run['id']}")).json()["status"] == "interrupted"


async def test_cancel_running_run(tmp_path):
    app = create_app(make_settings(tmp_path, mock_delay_scale=1.0))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        run = (await start_run(c, fusion_graph(a, b))).json()
        await asyncio.sleep(0.2)
        r = await c.post(f"/runs/{run['id']}/cancel")
        body = r.json()
    assert body["status"] == "cancelled"
    assert not any(s["status"] in ("running", "pending") for s in body["steps"])


async def test_run_not_found(client):
    r = await client.get("/runs/run_nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "RUN_NOT_FOUND"


async def test_per_run_generation_cap(tmp_path):
    app = create_app(make_settings(tmp_path, max_generations_per_run=0))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        done = await wait_run(c, (await start_run(c, fusion_graph(a, b))).json()["id"])
    assert done["error"]["code"] == "BUDGET_EXCEEDED" and done["error"]["retryable"] is False


async def test_daily_generation_cap(tmp_path):
    app = create_app(make_settings(tmp_path, daily_generation_cap=1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        first = await wait_run(c, (await start_run(c, fusion_graph(a, b), "d1")).json()["id"])
        second = await wait_run(c, (await start_run(c, fusion_graph(a, b), "d2")).json()["id"])
    assert first["status"] == "succeeded"
    assert second["error"]["code"] == "BUDGET_EXCEEDED"


async def test_vision_cap_counts_retries(tmp_path):
    app = create_app(make_settings(tmp_path, max_vision_calls_per_run=2))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        done = await wait_run(c, (await start_run(c, fusion_graph(a, b))).json()["id"])
    # 2 identify calls fit, the planning call does not
    assert done["error"]["code"] == "BUDGET_EXCEEDED"
    assert [s["key"] for s in done["steps"] if s["status"] == "failed"] == ["compile"]


async def test_session_rate_limit_on_post_runs(tmp_path):
    app = create_app(make_settings(tmp_path, runs_per_minute_per_session=2))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t",
                                 headers={"X-Session-Id": "rate-limit-session"}) as c:
        a, b = await two_assets(c)
        codes = [(await start_run(c, fusion_graph(a, b), key=f"rl{i}")).status_code for i in range(3)]
        last = await start_run(c, fusion_graph(a, b), key="rl-final")
    assert codes == [201, 201, 429]
    assert last.json()["error"]["retryAfterMs"] > 0 and "retry-after" in last.headers
