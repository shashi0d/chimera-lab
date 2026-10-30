"""D1-05: the full pipeline against both the invented sample and the real-schema fixture."""

import httpx
import pytest

from app.main import create_app
from tests.conftest import FIXTURES, fusion_graph, make_settings, start_run, two_assets, wait_run

FIXTURE_FILES = {"sample": "chimera_data.sample.json", "real": "chimera_data.real_schema.json"}


@pytest.fixture(params=sorted(FIXTURE_FILES))
async def data_client(request, tmp_path):
    app = create_app(make_settings(tmp_path, data_path=str(FIXTURES / FIXTURE_FILES[request.param])))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.schema = request.param  # type: ignore[attr-defined]
        yield c


async def test_lion_tiger_full_run(data_client):
    a, b = await two_assets(data_client)
    done = await wait_run(data_client, (await start_run(data_client, fusion_graph(a, b))).json()["id"])
    assert done["status"] == "succeeded", done
    spec = done["result"]["spec"]
    names = {h["name"].lower() for h in spec["realHybrids"]}
    assert {"liger", "tigon"} <= names
    rules_step = next(s for s in done["steps"] if s["key"] == "rules_check")
    assert spec["rulesSummary"]["mapped"] > 0 and "rules mapped" in rules_step["detail"]
    if data_client.schema == "real":
        tigon = next(h for h in spec["realHybrids"] if h["name"] == "tigon")
        assert tigon["cross"] == "father: tiger (Panthera tigris) × mother: lion (Panthera leo)"
        assert spec["rulesSummary"]["unmapped"] == 6
        assert any(w["ruleId"] == "R-A3-07" for w in spec["warnings"])
        assert spec["bodyPlan"] == "quadruped"


async def test_octopus_macaw_warnings(data_client):
    a, b = await two_assets(data_client, "common_octopus", "scarlet_macaw")
    done = await wait_run(data_client, (await start_run(data_client, fusion_graph(a, b))).json()["id"])
    assert done["status"] == "succeeded"
    assert [w for w in done["result"]["spec"]["warnings"] if w["severity"] == "warning"]


@pytest.mark.parametrize("fault,code", [("not_animal", "NOT_AN_ANIMAL"), ("refusal", "MODEL_REFUSED"), ("timeout", "UPSTREAM_TIMEOUT")])
async def test_faults_on_both_fixtures(data_client, fault, code):
    a, b = await two_assets(data_client)
    done = await wait_run(data_client, (await start_run(data_client, fusion_graph(a, b), key=f"f-{fault}", fault=fault)).json()["id"])
    assert done["error"]["code"] == code


async def test_health_reports_data_counts(data_client):
    body = (await data_client.get("/health")).json()
    assert body["status"] == "ok"
    d = body["data"]
    assert d["rulesMapped"] > 0 and d["hybridsResolved"] > 0 and d["problems"] == []
    if data_client.schema == "real":
        assert (d["animals"], d["hybrids"], d["hybridsResolved"], d["mythology"]) == (10, 5, 4, 4)


async def test_health_degraded_when_nothing_maps(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"animals": [], "rules": [{"rule_id": "R-Z9-99", "rule_text": "x"}], "hybrids": []}')
    app = create_app(make_settings(tmp_path, data_path=str(bad)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        body = (await c.get("/health")).json()
    assert body["status"] == "degraded" and "0 of 1 rules" in body["data"]["problems"][0]
