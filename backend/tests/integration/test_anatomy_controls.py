"""F1: anatomy controls (part donor pins on the Fusion node)."""

import httpx
import pytest

from app.adapters.mock.image_gen import head_donor_index
from app.main import create_app
from tests.conftest import fusion_graph, make_settings, start_run, two_assets, wait_run

ALL_B = {"head": "B", "body": "B", "limbs": "A", "covering": "B", "tail": "A"}


def with_donors(graph, donors):
    graph["nodes"][2]["config"] = {"donors": donors}
    graph["nodes"][2]["version"] = 2
    return graph


async def test_pins_override_the_plan_and_are_attributed(client):
    a, b = await two_assets(client, "common_octopus", "scarlet_macaw")
    g = with_donors(fusion_graph(a, b), {"head": "B", "body": "auto", "limbs": "auto", "covering": "A", "tail": "auto"})
    done = await wait_run(client, (await start_run(client, g)).json()["id"])
    spec = done["result"]["spec"]
    assert spec["partDonors"]["head"] == "B" and spec["partDonors"]["covering"] == "A"
    assert spec["donorSource"] == {"head": "user", "body": "model", "limbs": "model", "covering": "user", "tail": "model"}
    assert "Reference image 2 shows a scarlet macaw. Use it only for the head" in spec["prompt"]
    assert "2 parts chosen by you" in next(s for s in done["steps"] if s["key"] == "compile")["detail"]


async def test_all_pinned_skips_the_planning_call(tmp_path):
    # With a vision budget of exactly 2, only the two identify calls fit: a plan call would fail the run.
    app = create_app(make_settings(tmp_path, max_vision_calls_per_run=2))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        a, b = await two_assets(c)
        done = await wait_run(c, (await start_run(c, with_donors(fusion_graph(a, b), ALL_B))).json()["id"])
    assert done["status"] == "succeeded", done
    spec = done["result"]["spec"]
    assert set(spec["donorSource"].values()) == {"user"}
    assert spec["rationale"].startswith("Every part was chosen by you")


async def test_pins_change_the_mock_image(client):
    a, b = await two_assets(client)
    r1 = await wait_run(client, (await start_run(client, fusion_graph(a, b), key="p1")).json()["id"])
    r2 = await wait_run(client, (await start_run(client, with_donors(fusion_graph(a, b), ALL_B), key="p2")).json()["id"])
    i1 = (await client.get(r1["result"]["imageUrl"])).content
    i2 = (await client.get(r2["result"]["imageUrl"])).content
    assert i1 != i2


@pytest.mark.parametrize("donors", [{"head": "C"}, {"wings": "A"}, "nope"])
async def test_invalid_donor_config_is_graph_invalid(client, donors):
    a, b = await two_assets(client)
    r = await start_run(client, with_donors(fusion_graph(a, b), donors), key=f"bad-{donors}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "GRAPH_INVALID"


def test_head_donor_parsed_from_prompt():
    assert head_donor_index("Reference image 1 shows a lion. Use it only for the head and tail. Reference image 2 shows a tiger.") == 0
    assert head_donor_index("Reference image 1 shows a lion. Use it only for the torso. Reference image 2 shows a tiger. Use it only for the head.") == 1
