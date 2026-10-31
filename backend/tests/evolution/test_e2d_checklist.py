"""E2d: feature-checklist critic on the real-hybrid route.

1. Every known pair has a 4-to-6-item checklist of visible features from its R2 card(s).
2. On the real-hybrid route the critic gets the image plus the checklist and answers
   yes / no / unclear per item (JSON) plus a forced choice: either parent, the hybrid's
   name, or "other". Score = fraction yes, unclear 0.5. The forced choice is logged only.
3. The thumbnail critic uses the same checklist.
4. Chimera and same-genus routes keep the open critic, unchanged.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from PIL import Image

from app.adapters.mock.recorded import chat_payload
from app.evolution import live
from app.evolution.data import known_pairs
from app.evolution.judge import THUMB_PX, checklist_choices, checklist_for, checklist_score
from app.evolution.route import route
from tests.conftest import make_settings

MULE = ["horse-sized body and long legs relative to the head", "long donkey ears", "short upright mane",
        "tufted, short-haired tail base", "plain coat with no stripes"]


def _png(size: int = 1024) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), "white").save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ 1. data


def test_every_pair_has_a_checklist_of_4_to_6_items():
    pairs = known_pairs()
    assert len(pairs) == 7
    for p in pairs:
        items = p["checklist"]
        assert 4 <= len(items) <= 6 and len(set(items)) == len(items), p["id"]
        assert all(isinstance(x, str) and x.strip() == x and x for x in items)


def test_mule_checklist_is_the_specified_one():
    assert next(p for p in known_pairs() if p["id"] == "mule")["checklist"] == MULE


# ------------------------------------------------------------------ 2. scoring and choices


@pytest.mark.parametrize("answers,expected", [
    (["yes"] * 5, 1.0), (["no"] * 5, 0.0), (["unclear"] * 5, 0.5),
    (["yes", "yes", "no", "unclear", "yes"], 0.7), (["yes", "no", "no", "no"], 0.25),
])
def test_checklist_score(answers, expected):
    result = {"answers": [{"item": f"i{n}", "answer": a} for n, a in enumerate(answers)], "choice": "other"}
    assert checklist_score(result) == pytest.approx(expected)


def test_forced_choice_does_not_change_the_score():
    answers = [{"item": "a", "answer": "yes"}, {"item": "b", "answer": "no"}]
    scores = {checklist_score({"answers": answers, "choice": c}) for c in ("donkey", "horse", "mule", "other")}
    assert scores == {0.5}


def test_empty_checklist_answer_scores_zero():
    assert checklist_score({"answers": [], "choice": "mule"}) == 0.0


def test_checklist_only_on_the_real_hybrid_route(tax):
    a = tax.animals
    mule = route(a["donkey"], a["horse"], tax)
    assert checklist_for(mule) == MULE
    assert checklist_choices(a["donkey"], a["horse"], mule) == ["donkey", "horse", "mule", "other"]
    assert checklist_choices(a["lion"], a["tiger"], route(a["lion"], a["tiger"], tax)) == ["lion", "tiger", "liger",
                                                                                          "other"]
    assert checklist_for(route(a["lion"], a["golden_eagle"], tax)) == []  # chimera
    assert checklist_for(route(a["tiger"], a["leopard"], tax)) == []  # same genus, no documented cross


# ------------------------------------------------------------------ live request and parser (no network)


def test_checklist_request_has_items_choices_and_image():
    body = live.build_checklist_request("muse-spark", _png(), MULE, ["donkey", "horse", "mule", "other"])
    text = body["messages"][1]["content"][0]["text"]
    assert all(f"{i}. {item}" in text for i, item in enumerate(MULE, 1))
    assert "donkey, horse, mule, other" in text
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/")
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["choice"]["enum"] == ["donkey", "horse", "mule", "other"]
    assert schema["properties"]["answers"]["items"]["properties"]["answer"]["enum"] == ["yes", "no", "unclear"]
    assert body["temperature"] == 0 and "$ref" not in json.dumps(schema)


def test_checklist_parser_pads_and_cleans():
    choices = ["donkey", "horse", "mule", "other"]
    payload = chat_payload("plan", {"answers": [{"item": "x", "answer": "YES"}, {"item": "y", "answer": "maybe"}],
                                    "choice": "zebra", "notes": "n"})
    out = live.parse_checklist_response(payload, MULE, choices)
    assert [a["answer"] for a in out["answers"]] == ["yes", "unclear", "unclear", "unclear", "unclear"]
    assert [a["item"] for a in out["answers"]] == MULE  # matched by order, our item text kept
    assert out["choice"] == "other" and out["notes"] == "n"


async def test_live_checklist_goes_through_the_metered_client(tmp_path, monkeypatch):
    spark = live.LiveEvoSpark(make_settings(tmp_path, meta_api_key="k"))
    sent: list[dict[str, Any]] = []

    async def fake_call(kind, purpose, model, body, responses=False, raw=False):
        sent.append({"kind": kind, "purpose": purpose})
        return chat_payload("plan", {"answers": [{"item": i, "answer": "yes"} for i in MULE], "choice": "mule",
                                     "notes": "a mule"})

    monkeypatch.setattr(spark.http, "call", fake_call)
    out = await spark.checklist(_png(), MULE, ["donkey", "horse", "mule", "other"])
    assert sent == [{"kind": "spark", "purpose": "evo_checklist"}]
    assert checklist_score(out) == 1.0 and out["choice"] == "mule"


# ------------------------------------------------------------------ engine wiring (mock)


def _spy(engine) -> dict[str, list]:
    seen: dict[str, list] = {"critic": [], "checklist": []}
    open_critic, checklist = engine.spark.critic, engine.spark.checklist

    async def critic(image: bytes) -> dict[str, Any]:
        seen["critic"].append(_size(image))
        return await open_critic(image)

    async def spy_checklist(image: bytes, items: list[str], choices: list[str]) -> dict[str, Any]:
        seen["checklist"].append((_size(image), list(items), list(choices)))
        return await checklist(image, items, choices)

    engine.spark.critic = critic  # type: ignore[method-assign]
    engine.spark.checklist = spy_checklist  # type: ignore[method-assign]
    return seen


def _size(image: bytes) -> int:
    with Image.open(io.BytesIO(image)) as im:
        return max(im.size)


@pytest.mark.parametrize("sire,dam,name", [("donkey", "horse", "mule"), ("lion", "tiger", "liger")])
async def test_real_hybrid_uses_the_checklist_for_full_image_and_thumbnail(engine, sire, dam, name):
    seen = _spy(engine)
    doc = await engine.fuse(sire_name=sire, dam_name=dam)
    assert seen["critic"] == []  # the open critic is not called on this route
    (full, items, choices), (thumb, items2, choices2) = seen["checklist"]
    assert full > THUMB_PX and thumb == THUMB_PX
    assert items == items2 == next(p for p in known_pairs() if p["id"] == name)["checklist"]
    assert choices == choices2 and choices[2] == name and choices[-1] == "other"
    j = doc["judge"]
    assert j["critic_mode"] == "checklist" and j["third_animal"] == []
    assert j["forced_choice"] == {"full": name, "thumbnail": name}
    assert j["scores"]["critic"] == checklist_score(j["critic"]) == 1.0  # mock: every item visible at full size
    assert j["scores"]["thumbnail"] == checklist_score(j["critic_thumbnail"]) < 1.0  # fine detail unclear
    assert doc["meta_calls"] == {"spark": 4, "image": 1, "sam": 1}  # still 2 critic calls per render


@pytest.mark.parametrize("sire,dam", [("lion", "eagle"), ("eagle", "octopus"), ("tiger", "leopard")])
async def test_other_routes_keep_the_open_critic(engine, sire, dam):
    seen = _spy(engine)
    doc = await engine.fuse(sire_name=sire, dam_name=dam)
    assert seen["checklist"] == [] and len(seen["critic"]) == 2
    j = doc["judge"]
    assert j["critic_mode"] == "open" and "forced_choice" not in j and "animals" in j["critic"]


async def test_forced_choice_other_is_logged_not_scored(engine):
    async def scripted(image: bytes, items: list[str], choices: list[str]) -> dict[str, Any]:
        return {"answers": [{"item": i, "answer": "yes"} for i in items], "choice": "other", "notes": "s"}

    engine.spark.checklist = scripted  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="donkey", dam_name="horse")
    assert doc["judge"]["forced_choice"] == {"full": "other", "thumbnail": "other"}
    assert doc["judge"]["scores"]["critic"] == 1.0 and len(doc["render_attempts"]) == 1  # no re-render
