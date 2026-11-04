"""Prompt mode: the plain-prompt Fusion with art styles, a white background, reference images (photos and earlier
creatures), the generation record kept on each image, and the on-demand animal card."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.adapters.base import GeneratedImage
from app.agentapi import animal_card as AC
from app.agentapi.fusion_prompt import STYLES, build_fusion_prompt
from app.agentapi.jobs import PromptDriver
from tests.agentapi.test_agent_api import (  # noqa: F401  (make_client is a fixture)
    assert_served,
    events_of,
    make_client,
    named_run,
    photos,
    png,
    post_run,
    wait_status,
)
from tests.conftest import make_settings


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def generate(self, prompt, refs, aspect, previous=None):  # type: ignore[no-untyped-def]
        self.calls.append((prompt, len(refs)))
        return GeneratedImage(data=png("white"), content_type="image/png", model="fake", response_id="resp_1")


async def prompt_client(make: Any, user: str = "user-1") -> tuple[Any, Recorder]:
    c = await make(user=user)
    svc = c.app.state.agent.services
    rec = Recorder()
    svc.image_gen.generate = rec.generate
    c.app.state.agent.driver_factory = lambda: PromptDriver(svc)
    return c, rec


async def finished_version(c: Any, rid: str) -> dict[str, Any]:
    await wait_status(c, rid, "succeeded")
    r = await c.post("/evo/lab/versions/from-run", json={"runId": rid})
    assert r.status_code == 201, r.text
    return r.json()


def test_the_prompt_names_the_parents_style_background_and_references(tmp_path):
    st = make_settings(tmp_path)
    a = {"commonName": "horse", "source": "image"}
    b = {"commonName": "Lion × Eagle", "source": "version"}
    plain = build_fusion_prompt(st, a, b, "anime", [])
    assert plain.startswith("create a hybrid of horse and Lion × Eagle.")
    assert STYLES["anime"] in plain and "plain pure white background" in plain
    assert "reference image" not in plain
    both = build_fusion_prompt(st, a, b, "real", ["sire", "dam"])
    assert "reference image 1 is a photo of horse" in both
    assert "reference image 2 is an earlier generated creature of Lion × Eagle" in both
    assert "plain pure white background" in build_fusion_prompt(st, a, b, "unknown-style", [])


async def test_named_parents_render_one_image_with_the_chosen_style(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    r = await post_run(c, files={}, data={"sireName": "horse", "damName": "pangolin", "style": "cartoon"})
    assert r.status_code == 202 and r.json()["style"] == "cartoon"
    v1 = await finished_version(c, r.json()["runId"])
    [(prompt, nrefs)] = rec.calls
    assert nrefs == 0 and STYLES["cartoon"] in prompt and "white background" in prompt
    assert v1["style"] == "cartoon"
    events = await events_of(c, r.json()["runId"])
    await assert_served(c, next(e for e in events if e["type"] == "render")["url"])


async def test_an_unknown_style_is_refused(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    r = await post_run(c, files={}, data={"sireName": "horse", "damName": "pangolin", "style": "oil"})
    assert r.status_code == 422 and r.json()["error"]["details"]["styles"] == list(STYLES)
    assert rec.calls == []


@pytest.mark.parametrize("style", list(STYLES))
async def test_every_style_is_accepted(make_client, style):  # noqa: F811
    c, _ = await prompt_client(make_client)
    r = await post_run(c, files={}, data={"sireName": "horse", "damName": "pangolin", "style": style})
    assert r.status_code == 202


async def test_photos_go_to_the_image_model_as_references(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    r = await post_run(c, files=photos())
    assert r.status_code == 202, r.text
    await wait_status(c, r.json()["runId"], "succeeded")
    [(prompt, nrefs)] = rec.calls
    assert nrefs == 2 and "reference image 1 is a photo of" in prompt


async def test_a_typed_name_with_a_photo_keeps_the_photo_as_a_reference(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    r = await post_run(c, files=photos(), data={"sireName": "lion", "damName": "fox"})
    assert r.status_code == 202, r.text
    await wait_status(c, r.json()["runId"], "succeeded")
    [(prompt, nrefs)] = rec.calls
    assert nrefs == 2 and prompt.startswith("create a hybrid of lion and fox.")


async def test_an_earlier_creature_can_be_a_parent(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    first = (await post_run(c, files={}, data={"sireName": "horse", "damName": "pangolin"})).json()["runId"]
    v1 = await finished_version(c, first)
    r = await post_run(c, files={}, data={"sireVersionId": v1["id"], "damName": "eagle", "style": "comic"})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["sire"]["source"] == "version" and body["sire"]["versionId"] == v1["id"]
    assert body["sire"]["commonName"] == v1["title"]
    await wait_status(c, body["runId"], "succeeded")
    prompt, nrefs = rec.calls[-1]
    assert nrefs == 1 and "reference image 1 is an earlier generated creature" in prompt


async def test_another_users_creature_cannot_be_a_parent(make_client):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await finished_version(c, (await named_run(c)).json()["runId"])
    # A second app (its own store) stands in for another user: the version id is unknown there, as it is to
    # another user on one server (the owner check is the same lookup).
    other, _ = await prompt_client(make_client, user="user-2")
    r = await post_run(other, files={}, data={"sireVersionId": v1["id"], "damName": "eagle"})
    assert r.status_code == 422 and r.json()["error"]["details"]["slot"] == "sire"


async def test_edits_ask_for_the_white_background_and_keep_their_record(make_client):  # noqa: F811
    c, rec = await prompt_client(make_client)
    v1 = await finished_version(c, (await named_run(c)).json()["runId"])
    r = await c.post(f"/evo/lab/versions/{v1['id']}/revise", json={"instruction": "longer legs"})
    assert r.status_code == 202, r.text
    job = r.json()["id"]
    doc: dict[str, Any] = {}
    for _ in range(500):
        jobs = (await c.get("/evo/lab/jobs")).json()["jobs"]
        doc = next(j for j in jobs if j["id"] == job)
        if doc["status"] in ("succeeded", "failed"):
            break
        await asyncio.sleep(0.01)
    assert doc["status"] == "succeeded", doc
    prompt, _ = rec.calls[-1]
    assert "longer legs" in prompt and "white background" in prompt
    stored = await c.app.state.agent.services.db.get("assets", doc["result"]["id"])
    assert stored["generation"]["instruction"] == "longer legs" and stored["generation"]["prompt"] == prompt


async def test_the_animal_card_builds_on_the_generation_record(make_client, monkeypatch):  # noqa: F811
    c, _ = await prompt_client(make_client)
    v1 = await finished_version(c, (await post_run(c, files={}, data={
        "sireName": "horse", "damName": "pangolin", "style": "drawing"})).json()["runId"])
    seen: dict[str, Any] = {}

    async def fake_card(settings, image, context):  # type: ignore[no-untyped-def]
        seen.update(context=context, image=image)
        return {"name": "Scaled steed", "reasoning": "the scales read as pangolin", "basedOn": context}

    monkeypatch.setattr(AC, "make_card", fake_card)
    assert (await c.get(f"/evo/lab/versions/{v1['id']}/card")).json() == {"card": None}
    r = await c.post(f"/evo/lab/versions/{v1['id']}/card")
    assert r.status_code == 200 and r.json()["name"] == "Scaled steed"
    ctx = seen["context"]
    assert ctx["style"] == "drawing" and "horse" in ctx["fusion"]["prompt"] and ctx["edits"] == []
    assert seen["image"]
    saved = (await c.get(f"/evo/lab/versions/{v1['id']}/card")).json()["card"]
    assert saved["reasoning"] == "the scales read as pangolin" and saved["createdAt"]
    versions = (await c.get("/evo/lab/versions")).json()["versions"]
    assert next(v for v in versions if v["id"] == v1["id"])["card"]["name"] == "Scaled steed"


def test_card_parsing_keeps_only_the_schema_fields():
    content = {"name": " Scaled steed ", "scientific_style_name": "Equus squamatus", "tagline": "t",
               "inherited": [{"parent": "horse", "traits": ["hooves"]}, "junk"], "appearance": "a", "size": "s",
               "habitat": "h", "diet": "d", "behaviour": "b", "abilities": ["run", " "], "weaknesses": ["heat"],
               "fun_fact": "f", "reasoning": "r", "extra": "dropped"}
    card = AC.parse_card({"choices": [{"message": {"content": json.dumps(content)}, "finish_reason": "stop"}]})
    assert card["name"] == "Scaled steed" and card["inherited"] == [{"parent": "horse", "traits": ["hooves"]}]
    assert card["abilities"] == ["run"] and "extra" not in card


def test_card_context_lists_the_fusion_record_then_each_edit():
    chain = [{"title": "Horse × Pangolin", "style": "real", "generation": {"prompt": "p", "style": "real"}},
             {"operation": "revise", "instruction": "longer legs"}, {"operation": "paint", "instruction": "blue"}]
    ctx = AC.card_context(chain)
    assert ctx["fusion"]["prompt"] == "p" and [e["instruction"] for e in ctx["edits"]] == ["longer legs", "blue"]


async def test_with_limits_off_nothing_is_refused(make_client):  # noqa: F811
    c = await make_client(evo_limits_enabled=False, evo_visitor_daily_runs=1, evo_daily_runs=1,
                          evo_runs_per_minute_per_ip=1, lab_user_daily_actions=1, lab_daily_actions=1)
    for _ in range(3):
        r = await named_run(c)
        assert r.status_code == 202, r.text
        await wait_status(c, r.json()["runId"], "succeeded")
    limits = (await c.get("/evo/agent/limits")).json()
    assert limits["liveRuns"] == "open" and limits["unlimited"] is True and limits["visitor"]["used"] == 3
    lab = (await c.get("/evo/lab/limits")).json()
    assert lab["limit"] is None and lab["totalLimit"] is None
    assert make_settings(__import__("pathlib").Path("x")).evo_limits_enabled is True  # tests default to limits on


def test_the_app_default_is_no_limits():
    from app.config import Settings

    assert Settings(_env_file=None).evo_limits_enabled is False
