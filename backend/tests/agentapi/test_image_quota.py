"""The lifetime image quota per visitor: a Fusion or an edit costs 1 image, an animal card 4. Images are taken before
the model is called and given back when nothing is delivered; at the limit every generation is refused (429)."""

from __future__ import annotations

from typing import Any

from app.errors import ChimeraError
from app.models.schemas import ErrorCode
from tests.agentapi.test_agent_api import make_client, post_run, wait_status  # noqa: F401  (make_client: fixture)
from tests.agentapi.test_prompt_mode import finished_version, prompt_client, wait_card, wait_job


def set_limit(c: Any, limit: int) -> None:
    c.app.state.agent.quota.settings.evo_visitor_image_limit = limit


async def images(c: Any) -> dict[str, Any]:
    return (await c.get("/evo/agent/limits")).json()["images"]


async def fusion(c: Any) -> Any:
    return await post_run(c, files={}, data={"sireName": "horse", "damName": "pangolin"})


async def test_fusion_edits_and_cards_count_until_the_limit(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    set_limit(c, 6)
    assert await images(c) == {"used": 0, "limit": 6, "left": 6, "costs": {"fusion": 1, "edit": 1, "card": 4}}

    v1 = await finished_version(c, (await fusion(c)).json()["runId"])
    assert (await images(c))["used"] == 1

    await c.put(f"/evo/lab/versions/{v1['id']}/saved", json={"saved": True})
    assert (await wait_card(c, v1["id"]))["status"] == "ready"
    assert (await images(c))["used"] == 5

    r = await c.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "Longer legs"})
    assert r.status_code == 202, r.text
    assert (await wait_job(c, r.json()["id"]))["status"] == "succeeded"
    assert await images(c) == {"used": 6, "limit": 6, "left": 0, "costs": {"fusion": 1, "edit": 1, "card": 4}}
    lab_limits = (await c.get("/evo/lab/limits")).json()
    assert lab_limits["images"]["left"] == 0

    r = await c.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "Shorter tail"})
    assert r.status_code == 429 and r.json()["error"]["details"]["scope"] == "visitor_images"
    r = await fusion(c)
    assert r.status_code == 429 and "all 6 of your images" in r.json()["error"]["message"]
    assert (await images(c))["used"] == 6


async def test_saving_with_too_few_images_left_saves_without_a_card(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    set_limit(c, 3)
    v1 = await finished_version(c, (await fusion(c)).json()["runId"])
    calls = len(rec.calls)
    r = await c.put(f"/evo/lab/versions/{v1['id']}/saved", json={"saved": True})
    assert r.status_code == 200 and r.json()["saved"] is True
    card = r.json()["card"]
    assert card["status"] == "failed" and "needs 4 images" in card["error"]
    assert len(rec.calls) == calls  # no model call
    assert (await images(c))["used"] == 1
    r = await c.post(f"/evo/lab/versions/{v1['id']}/card")
    assert r.status_code == 429 and r.json()["error"]["details"]["need"] == 4


async def test_a_failed_run_gives_its_image_back(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    set_limit(c, 1)

    async def down(*args: Any, **kwargs: Any) -> Any:
        raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "The image provider is down.", retryable=False)

    c.app.state.agent.services.image_gen.generate = down
    rid = (await fusion(c)).json()["runId"]
    await wait_status(c, rid, "failed")
    assert (await images(c))["used"] == 0
    assert (await fusion(c)).status_code == 202  # the image is free again


async def test_no_limit_when_set_to_zero(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    set_limit(c, 0)
    assert await images(c) == {"used": 0, "limit": None, "left": None, "costs": {"fusion": 1, "edit": 1, "card": 4}}
    await finished_version(c, (await fusion(c)).json()["runId"])
    assert (await images(c))["used"] == 1  # still counted
