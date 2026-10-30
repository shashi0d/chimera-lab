from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
IMAGES = FIXTURES / "images"
EDGE = IMAGES / "edge"


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base: dict[str, Any] = dict(
        chimera_mode="mock",
        data_path=str(FIXTURES / "chimera_data.sample.json"),
        local_data_dir=str(tmp_path / "local"),
        mock_delay_scale=0.0,
        retry_base_seconds=0.001,
        runs_per_minute_per_session=1000,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Session-Id": "test-session-1"}
    ) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c


async def upload(client: httpx.AsyncClient, path: Path, name: str | None = None) -> httpx.Response:
    return await client.post("/assets", files={"file": (name or path.name, path.read_bytes(), "application/octet-stream")})


def fusion_graph(asset_a: str | None, asset_b: str | None, graph_id: str = "g1") -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {"id": "img-a", "type": "image-input", "version": 1, "position": {"x": 0, "y": 0}, "data": {"assetId": asset_a}},
        {"id": "img-b", "type": "image-input", "version": 1, "position": {"x": 0, "y": 200}, "data": {"assetId": asset_b}},
        {"id": "fuse", "type": "fusion", "version": 1, "position": {"x": 300, "y": 100}},
    ]
    edges = [
        {"id": "e1", "source": "img-a", "sourcePort": "out", "target": "fuse", "targetPort": "a"},
        {"id": "e2", "source": "img-b", "sourcePort": "out", "target": "fuse", "targetPort": "b"},
    ]
    return {"schemaVersion": 1, "graphId": graph_id, "nodes": nodes, "edges": edges}


async def start_run(client: httpx.AsyncClient, graph: dict[str, Any], key: str = "k1",
                    fault: str | None = None) -> httpx.Response:
    headers = {"Idempotency-Key": key}
    if fault:
        headers["X-Mock-Fault"] = fault
    return await client.post("/runs", json={"graph": graph, "nodeId": "fuse"}, headers=headers)


async def wait_run(client: httpx.AsyncClient, run_id: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        r = await client.get(f"/runs/{run_id}")
        body = r.json()
        if body["status"] in ("succeeded", "failed", "cancelled", "interrupted"):
            return body
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError(f"run did not finish: {body}")
        await asyncio.sleep(0.01)


async def two_assets(client: httpx.AsyncClient, a: str = "lion", b: str = "tiger") -> tuple[str, str]:
    ra = await upload(client, IMAGES / f"{a}.jpg")
    rb = await upload(client, IMAGES / f"{b}.jpg")
    return ra.json()["assetId"], rb.json()["assetId"]
