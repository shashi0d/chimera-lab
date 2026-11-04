"""The Lab: version 1 from a Fusion run, revisions and painted edits as child versions, final, download and the
daily lab budget. No paid call: the image and vision models are fakes."""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image

from app.adapters.base import GeneratedImage
from app.errors import ChimeraError
from app.main import create_app
from app.models.schemas import ErrorCode
from tests.agentapi.test_agent_api import ScriptedDriver, events_of, named_run
from tests.conftest import FakeAuth, auth, make_settings, offline_services

OTHER = auth("user-2")


def image_bytes(color: str, size: int = 64) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (size, size), color).save(out, "PNG")
    return out.getvalue()


class Renderer:
    """Records every image call and answers with a solid colour."""

    def __init__(self, color: str = "red", fail: bool = False) -> None:
        self.calls: list[tuple[str, list[bytes], str | None]] = []
        self.color, self.fail = color, fail
        self.model_id = "fake"

    async def generate(self, prompt: str, refs: list[bytes], aspect: str | None,
                       previous_response_id: str | None = None) -> GeneratedImage:
        self.calls.append((prompt, refs, previous_response_id))
        if self.fail:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image provider is down.", retryable=False)
        return GeneratedImage(image_bytes(self.color), "image/png", "fake", f"resp-{len(self.calls)}")


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = make_settings(tmp_path, evo_runs_per_minute_per_ip=1000, lab_actions_per_minute_per_ip=1000,
                             retry_max_attempts=1)
    app = create_app(settings, services=offline_services(settings))
    app.state.auth = FakeAuth()
    app.state.agent.driver_factory = lambda: ScriptedDriver()
    app.state.services.image_gen = Renderer()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers=auth(), timeout=30) as c:
            c.app = app  # type: ignore[attr-defined]
            yield c


async def first_version(c: httpx.AsyncClient) -> dict[str, Any]:
    rid = (await named_run(c)).json()["runId"]
    await events_of(c, rid)
    r = await c.post("/evo/lab/versions/from-run", json={"runId": rid})
    assert r.status_code == 201, r.text
    return r.json()


async def finish(c: httpx.AsyncClient, job: dict[str, Any]) -> dict[str, Any]:
    await asyncio.wait_for(c.app.state.lab.tasks[job["id"]], 5)  # type: ignore[attr-defined]
    return next(j for j in (await c.get("/evo/lab/jobs")).json()["jobs"] if j["id"] == job["id"])


async def revise(c: httpx.AsyncClient, version_id: str, text: str = "Longer legs") -> dict[str, Any]:
    r = await c.post(f"/evo/lab/versions/{version_id}/revise", json={"instruction": text})
    assert r.status_code == 202, r.text
    return await finish(c, r.json())


def mask_png(size: int = 64, box: tuple[int, int, int, int] = (0, 0, 32, 64)) -> bytes:
    m = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    m.paste((255, 0, 0, 255), box)
    out = io.BytesIO()
    m.save(out, "PNG")
    return out.getvalue()


# ====================================================================== version 1


async def test_version_one_is_the_runs_final_image_and_is_idempotent(client):
    v1 = await first_version(client)
    assert v1["operation"] == "fusion" and v1["parentId"] is None and v1["title"] == "lion × red fox"
    assert v1["instruction"] == "lion × red fox" and v1["runId"] and v1["creatureId"]
    again = await client.post("/evo/lab/versions/from-run", json={"runId": v1["runId"]})
    assert again.status_code == 200 and again.json()["id"] == v1["id"]
    assert [v["id"] for v in (await client.get("/evo/lab/versions")).json()["versions"]] == [v1["id"]]


async def test_another_users_run_and_versions_are_unavailable(client):
    v1 = await first_version(client)
    r = await client.post("/evo/lab/versions/from-run", json={"runId": v1["runId"]}, headers=OTHER)
    assert r.status_code == 404
    assert (await client.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "x"},
                              headers=OTHER)).status_code == 404
    assert (await client.get("/evo/lab/versions", headers=OTHER)).json()["versions"] == []
    assert (await client.get("/evo/lab/versions", headers={"Authorization": ""})).status_code == 401


async def test_a_running_run_cannot_become_a_version(client):
    hold = asyncio.Event()
    client.app.state.agent.driver_factory = lambda: ScriptedDriver(hold=hold)
    rid = (await named_run(client)).json()["runId"]
    r = await client.post("/evo/lab/versions/from-run", json={"runId": rid})
    assert r.status_code == 409
    hold.set()
    await events_of(client, rid)


# ====================================================================== edits


async def test_revisions_branch_from_any_version_and_use_the_image_as_reference(client):
    renderer: Renderer = client.app.state.services.image_gen
    v1 = await first_version(client)
    job = await revise(client, v1["id"], "Longer legs")
    assert job["status"] == "succeeded" and job["operation"] == "revise" and job["parentId"] == v1["id"]
    v2 = job["result"]
    assert v2["parentId"] == v1["id"] and v2["operation"] == "revise" and v2["instruction"] == "Longer legs"
    assert v2["runId"] == v1["runId"] and v2["title"] == v1["title"]
    prompt, refs, chain = renderer.calls[-1]
    assert "Longer legs" in prompt and len(refs) == 1 and chain is None  # v1 is a run image: sent as reference
    assert (await client.get(v2["imageUrl"])).status_code == 200
    v3 = (await revise(client, v2["id"], "Blue fur"))["result"]
    assert renderer.calls[-1][1] == [] and renderer.calls[-1][2] == "resp-1"  # v2 is the provider's response: chained
    branch = (await revise(client, v1["id"], "Red fur"))["result"]
    assert branch["parentId"] == v1["id"] and v3["parentId"] == v2["id"]
    ids = [v["id"] for v in (await client.get("/evo/lab/versions")).json()["versions"]]
    assert ids == [v1["id"], v2["id"], v3["id"], branch["id"]]


async def test_a_painted_edit_changes_only_the_painted_pixels(client):
    v1 = await first_version(client)
    r = await client.post(f"/evo/lab/versions/{v1['id']}/paint", data={"instruction": "Make this half red"},
                          files={"mask": ("mask.png", mask_png(), "image/png")})
    assert r.status_code == 202, r.text
    job = await finish(client, r.json())
    v2 = job["result"]
    assert job["status"] == "succeeded" and v2["operation"] == "paint" and v2["parentId"] == v1["id"]
    with Image.open(io.BytesIO((await client.get(v2["imageUrl"])).content)) as im:
        im = im.convert("RGB")
        assert im.getpixel((60, 32)) == (0, 0, 255)  # outside the paint: unchanged (the run image is blue)
        assert im.getpixel((5, 32))[0] > 200  # inside: the edit
    renderer: Renderer = client.app.state.services.image_gen
    await revise(client, v2["id"], "Sharper")
    assert renderer.calls[-1][2] is None and len(renderer.calls[-1][1]) == 1  # a composite is always a reference


async def test_an_empty_or_wrong_size_mask_is_refused_without_charging(client):
    v1 = await first_version(client)
    for mask in (mask_png(box=(0, 0, 0, 0)), mask_png(size=32)):
        r = await client.post(f"/evo/lab/versions/{v1['id']}/paint", data={"instruction": "x"},
                              files={"mask": ("mask.png", mask, "image/png")})
        assert r.status_code == 422
    assert (await client.get("/evo/lab/limits")).json()["used"] == 0


async def test_validation_of_instructions(client):
    v1 = await first_version(client)
    for body in ({"instruction": ""}, {"instruction": "x" * 2001}, {}, []):
        r = await client.post(f"/evo/lab/versions/{v1['id']}/revise", json=body)
        assert r.status_code == 422


# ====================================================================== budget and jobs


async def test_lab_actions_are_counted_and_refunded_when_they_fail(client):
    v1 = await first_version(client)
    await revise(client, v1["id"])
    assert (await client.get("/evo/lab/limits")).json()["used"] == 1
    client.app.state.services.image_gen = Renderer(fail=True)
    job = await revise(client, v1["id"])
    assert job["status"] == "failed" and job["error"] == "The image provider is down."
    limits = (await client.get("/evo/lab/limits")).json()
    assert limits["used"] == 1 and limits["totalUsed"] == 1


async def test_the_daily_lab_budget(client):
    client.app.state.lab.caps.settings.evo_visitor_daily_runs = 1
    v1 = await first_version(client)
    await revise(client, v1["id"])
    r = await client.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "again"})
    assert r.status_code == 429 and "lab action limit" in r.json()["error"]["message"]
    assert (await client.get("/evo/agent/limits")).json()["visitor"]["used"] == 1  # separate from Fusion runs


async def test_a_stale_job_is_interrupted_on_shared_storage(client, monkeypatch):
    from app.util import now_iso

    monkeypatch.setattr(client.app.state.services, "local_backend", False)
    db = client.app.state.services.db
    base = {"kind": "lab_job", "owner": "user-1", "status": "running", "operation": "revise"}
    await db.put("assets", "labjob_old", {**base, "id": "labjob_old", "createdAt": "2026-01-01T00:00:00.000Z",
                                          "updatedAt": "2026-01-01T00:00:00.000Z"})
    await db.put("assets", "labjob_new", {**base, "id": "labjob_new", "createdAt": now_iso(), "updatedAt": now_iso()})
    jobs = {j["id"]: j["status"] for j in (await client.get("/evo/lab/jobs")).json()["jobs"]}
    assert jobs == {"labjob_old": "interrupted", "labjob_new": "running"}
    assert (await client.get("/evo/lab/jobs", headers=OTHER)).json()["jobs"] == []


# ====================================================================== final, download


async def test_final_mark_and_download(client):
    v1 = await first_version(client)
    r = await client.put(f"/evo/lab/versions/{v1['id']}/final", json={"isFinal": True})
    assert r.status_code == 200 and r.json()["isFinal"] is True
    assert (await client.get("/evo/lab/versions")).json()["versions"][0]["isFinal"] is True
    assert (await client.put(f"/evo/lab/versions/{v1['id']}/final", json={"isFinal": "yes"})).status_code == 422
    d = await client.get(f"/evo/lab/versions/{v1['id']}/download")
    assert d.status_code == 200 and d.headers["content-type"] == "image/png"
    assert "attachment" in d.headers["content-disposition"]
    assert (await client.get(f"/evo/lab/versions/{v1['id']}/download", headers=OTHER)).status_code == 404
