"""F2: field-guide card node."""

import httpx
import pytest

from app.adapters.meta import client as meta
from app.main import create_app
from tests.conftest import fusion_graph, make_settings, start_run, two_assets, wait_run


def card_graph(fusion_graph_doc, run):
    g = fusion_graph_doc
    r = run["result"]
    g["nodes"].append({"id": "res", "type": "result", "version": 1, "position": {"x": 600, "y": 0},
                       "data": {"versions": [{"runId": run["id"], "creatureId": r["creatureId"], "assetId": r["assetId"]}],
                                "selected": 0}})
    g["nodes"].append({"id": "card", "type": "field-card", "version": 1, "position": {"x": 900, "y": 0}})
    g["edges"].append({"id": "e3", "source": "fuse", "sourcePort": "out", "target": "res", "targetPort": "in"})
    g["edges"].append({"id": "e4", "source": "res", "sourcePort": "out", "target": "card", "targetPort": "in"})
    return g


async def fused(client, a="lion", b="tiger"):
    ia, ib = await two_assets(client, a, b)
    g = fusion_graph(ia, ib)
    run = await wait_run(client, (await start_run(client, g, key=f"fuse-{a}-{b}")).json()["id"])
    assert run["status"] == "succeeded"
    return g, run


async def write(client, g, key="card", fault=None):
    headers = {"Idempotency-Key": key, **({"X-Mock-Fault": fault} if fault else {})}
    return await client.post("/runs", json={"graph": g, "nodeId": "card"}, headers=headers)


async def test_card_written_with_ranges_and_server_provenance(client):
    g, run = await fused(client)
    r = await write(client, card_graph(g, run))
    assert r.status_code == 201
    assert [s["key"] for s in r.json()["steps"]] == ["load_creature", "write_card", "store_card"]
    done = await wait_run(client, r.json()["id"])
    assert done["status"] == "succeeded", done
    card = done["result"]["card"]
    assert card["binomial"].startswith("Panthera ")
    assert "Lion 126-272 kg" in card["size"] and "Tiger 65-306 kg" in card["size"]  # verbatim ranges
    assert card["provenance"].startswith("Generated fusion. Not a real animal.")
    assert "Liger" in card["provenance"]
    assert done["result"]["creatureId"] == run["result"]["creatureId"]


@pytest.mark.parametrize("mutate,message", [
    (lambda g: g["edges"].pop(), "Connect a Result"),
    (lambda g: g["nodes"][3]["data"].update(versions=[]), "Fuse first"),
])
async def test_card_graph_invalid(client, mutate, message):
    g, run = await fused(client)
    cg = card_graph(g, run)
    mutate(cg)
    r = await write(client, cg, key=message)
    assert r.status_code == 422 and r.json()["error"]["code"] == "GRAPH_INVALID"
    assert message in r.json()["error"]["message"]


async def test_unknown_creature_is_not_found(client):
    g, run = await fused(client)
    cg = card_graph(g, run)
    cg["nodes"][3]["data"]["versions"][0]["creatureId"] = "crt_missing"
    done = await wait_run(client, (await write(client, cg, key="missing")).json()["id"])
    assert done["status"] == "failed" and done["error"]["code"] == "NOT_FOUND"


async def test_card_timeout_fault(client):
    g, run = await fused(client)
    done = await wait_run(client, (await write(client, card_graph(g, run), key="t", fault="timeout")).json()["id"])
    assert done["error"]["code"] == "UPSTREAM_TIMEOUT" and done["error"]["retryable"] is True


async def test_card_counts_against_vision_budget(tmp_path):
    app = create_app(make_settings(tmp_path))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        g, run = await fused(c)
        app.state.services.settings.max_vision_calls_per_run = 0
        done = await wait_run(c, (await write(c, card_graph(g, run))).json()["id"])
    assert done["error"]["code"] == "BUDGET_EXCEEDED"


def test_meta_card_request_and_parse():
    body = meta.build_card_request("m", {"parents": {}})
    assert body["response_format"]["json_schema"]["name"] == "field_card"
    import json
    card = meta.parse_card_response({"choices": [{"message": {"content": json.dumps({
        "common_name": "X", "binomial": "Y z", "habitat": "h", "diet": "d", "size": "s", "behaviour": "b"})},
        "finish_reason": "stop"}]})
    assert card.binomial == "Y z" and card.provenance == ""
