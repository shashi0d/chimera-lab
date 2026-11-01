"""S2 part 6: inspect (SAM presence for planned structural parts + the checklist critic for absences, third
animals and separate bodies) and one plan-worded Muse Image edit turn.

Regression cases: the E4 live beetle plan, and the S1 edit turn ("Remove the beetle bodies on the shoulders" also
removed the planned chitin plates, because it was worded from the symptom)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.adapters.meta.client import build_generate_request
from app.errors import ChimeraError
from app.evolution.critic import EXPECTED, questions
from app.evolution.engine import EvoEngine
from app.evolution.genome import validate_plan
from app.evolution.inspect import Item, edit_instruction, inspect_checklist, plan_items
from app.models.schemas import ErrorCode
from app.services import build_services
from tests.conftest import make_settings
from tests.evolution.conftest import plan_for

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"


class Meter:
    async def call(self, kind, purpose, aw):
        return await aw


def _mask(fill: bool) -> bytes:
    im = Image.new("L", (64, 64), 0)
    if fill:
        im.paste(255, (10, 10, 40, 40))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


class Seg:
    def __init__(self, found: dict[str, bool]) -> None:
        self.found, self.seen = found, []

    async def segment(self, image: bytes, label: str) -> bytes:
        self.seen.append(label)
        return _mask(self.found.get(label, False))


def _critic(items: list[Item], answers: dict[str, str], creatures: int = 1) -> dict[str, Any]:
    return {"answers": [{"item": i.text, "answer": answers.get(i.kind, "yes")} for i in items],
            "creatures": creatures, "animals": []}


@pytest.fixture
def e4_engine(tmp_path: Path) -> EvoEngine:
    store = tmp_path / "learned.json"
    shutil.copy(FIX / "learned_beetle_e4.json", store)
    return EvoEngine(build_services(make_settings(tmp_path, evo_learned_path=str(store))))


def _e4_plan(e4_engine):
    raw = json.loads((FIX / "e4_beetle_bear_plan.json").read_text(encoding="utf-8"))
    g0 = validate_plan({**raw, "id": "pending"})
    return e4_engine.finish(g0, e4_engine.route_for(g0))


# ------------------------------------------------------------------ the items


def test_plan_items_put_structural_claims_first(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    items = plan_items(g, engine.tax)
    kinds = [i.kind for i in items]
    assert kinds[:2] == ["frame", "head"] and "part" in kinds
    first_info = next(n for n, i in enumerate(items) if not i.structural)
    assert all(not i.structural for i in items[first_info:])
    wings = next(i for i in items if i.kind == "part")
    assert wings.sam == "wings" and wings.fix.startswith("Show the planned golden eagle wings")


def test_e4_beetle_plan_items(e4_engine):
    items = {i.kind: i for i in plan_items(_e4_plan(e4_engine), e4_engine.tax)}
    assert items["absent"].text == "no wings"
    assert items["part"].sam == "head horn" and "curved horn of hard, glossy chitin" in items["part"].text
    assert items["one_body"].text.startswith("only parts and materials of the european rhinoceros beetle")


# ------------------------------------------------------------------ inspect rules (S2 baseline, kept as inspect_checklist)


async def test_sam_confirms_a_part_the_critic_missed(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    items = plan_items(g, engine.tax)
    out = await inspect_checklist(b"img", g, engine.tax, items, _critic(items, {"part": "no"}), [], Seg({"wings": True}), Meter())
    part = next(r for r in out["items"] if r["kind"] == "part")
    assert part["sam_found"] and part["status"] == "pass" and out["failures"] == []


async def test_critic_no_and_no_mask_fails(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    items = plan_items(g, engine.tax)
    out = await inspect_checklist(b"img", g, engine.tax, items, _critic(items, {"part": "no"}), [], Seg({}), Meter())
    assert [f["kind"] for f in out["failures"]] == ["part"]


async def test_an_empty_mask_alone_never_proves_absence(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    items = plan_items(g, engine.tax)
    out = await inspect_checklist(b"img", g, engine.tax, items, _critic(items, {}), [], Seg({}), Meter())
    part = next(r for r in out["items"] if r["kind"] == "part")
    assert part["sam_found"] is False and part["status"] == "pass" and out["failures"] == []


async def test_absences_and_separate_bodies_come_from_the_critic(e4_engine):
    g = _e4_plan(e4_engine)
    items = plan_items(g, e4_engine.tax)
    seg = Seg({"head horn": True})
    out = await inspect_checklist(b"img", g, e4_engine.tax, items, _critic(items, {"absent": "no", "one_body": "no"}), [], seg,
                        Meter())
    assert sorted(f["kind"] for f in out["failures"]) == ["absent", "one_body"]
    assert "wings" not in seg.seen  # absences are never SAM-tested, so no mask can be read as proof


async def test_two_creatures_and_a_third_animal_fail(engine):
    g, _ = plan_for(engine, "lion", "eagle")
    items = plan_items(g, engine.tax)
    out = await inspect_checklist(b"img", g, engine.tax, items, _critic(items, {}, creatures=2), ["leopard"], Seg({}), Meter())
    assert [f["kind"] for f in out["failures"]] == ["count", "third_animal"]


# ------------------------------------------------------------------ the edit instruction (S1 regression)


def test_s1_edit_turn_request_shape_is_what_the_engine_sends():
    rec = json.loads((FIX / "s1_edit_turn.json").read_text(encoding="utf-8"))["request"]
    ours = build_generate_request("muse-image-1.0", "Show the planned plates.", [], "1:1", rec["previous_response_id"])
    assert set(ours) == set(rec) and ours["previous_response_id"] == rec["previous_response_id"]
    assert [c["type"] for c in ours["input"][0]["content"]] == [c["type"] for c in rec["input"][0]["content"]]


async def test_the_fix_is_worded_from_the_plan_not_the_symptom(e4_engine):
    rec = json.loads((FIX / "s1_edit_turn.json").read_text(encoding="utf-8"))["request"]
    s1_text = rec["input"][0]["content"][0]["text"]
    assert s1_text.startswith("Remove the beetle bodies")  # S1: symptom-worded, and it removed the planned plates
    g = _e4_plan(e4_engine)
    items = plan_items(g, e4_engine.tax)
    out = await inspect_checklist(b"img", g, e4_engine.tax, items, _critic(items, {"one_body": "no"}), [], Seg({}), Meter())
    text = edit_instruction(out["failures"])
    assert text.startswith("Show the planned european rhinoceros beetle contribution only as hard, glossy chitin plates")
    assert "not as separate animals" in text and "remove" not in text.lower()


@pytest.mark.parametrize("kinds", [{"frame": "no"}, {"head": "no"}, {"part": "no"}, {"compensation": "no"},
                                   {"absent": "no"}, {"one_body": "no"}])
async def test_no_instruction_is_worded_from_a_symptom(e4_engine, kinds):
    g = _e4_plan(e4_engine)
    items = plan_items(g, e4_engine.tax)
    out = await inspect_checklist(b"img", g, e4_engine.tax, items, _critic(items, kinds), ["zebra"], Seg({}), Meter())
    text = edit_instruction(out["failures"], limit=10)
    assert text and not any(w in text.lower() for w in ("remove", "delete", "zebra", "get rid"))
    assert all(f["fix"].startswith(("Show", "The plan has")) for f in out["failures"])


# ------------------------------------------------------------------ the loop in the engine


def _script(engine, per_render: list[dict[str, str]]):
    """S3a: balanced-checklist answers by question id for each render (both plan-blind critics answer alike);
    unlisted questions get their expected answer."""
    calls: list[int] = []

    async def ask(image: bytes, texts: list[str]) -> dict[str, Any]:
        calls.append(1)
        ids = {q.text: q.id for q in questions(engine._last_plan, engine.tax)}
        ans = per_render[min((len(calls) - 1) // 2, len(per_render) - 1)]
        return {"answers": [{"item": t, "answer": ans.get(ids.get(t, ""), EXPECTED.get(t, "yes"))} for t in texts],
                "notes": "scripted"}

    engine.spark.ask = ask  # type: ignore[method-assign]
    real = engine.realize

    async def realize(g, r, refs):
        engine._last_plan = g
        return await real(g, r, refs)

    engine.realize = realize  # type: ignore[method-assign]


class NoSeg:
    model_id = "no-sam"

    async def segment(self, image: bytes, label: str) -> bytes:
        return _mask(label == "animal")


async def test_a_structural_miss_gets_one_edit_and_is_fixed(engine):
    engine.segmenter = NoSeg()
    _script(engine, [{"wings_front": "no"}, {}])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert [a["prompt"] for a in doc["render_attempts"]][1] == "edit" and doc["inspect"]["kept"] == "edited"
    assert doc["inspect"]["after"]["failures"] == [] and doc["warnings"] == []
    assert doc["inspect"]["edit"]["instruction"].startswith("Show the planned golden eagle wings")
    assert doc["meta_calls"]["image"] == 2


async def test_still_failing_after_one_edit_is_kept_with_a_warning(engine):
    engine.segmenter = NoSeg()
    _script(engine, [{"wings_front": "no"}])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert len(doc["render_attempts"]) == 2 and doc["meta_calls"]["image"] == 2  # one edit, no loop
    assert doc["warnings"] == ["structural miss after one edit turn: Does it have golden eagle wings in place of its "
                               "front legs?"]
    assert doc["inspect"]["kept"] == "edited"


async def test_an_edit_that_makes_it_worse_keeps_the_first_render(engine):
    engine.segmenter = NoSeg()
    _script(engine, [{"wings_front": "no"}, {"wings_front": "no", "frame": "no"}])
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert doc["inspect"]["kept"] == "first" and doc["image_key"] != doc["first_image_key"]
    assert "first render kept" in doc["warnings"][0]


async def test_a_failed_edit_call_keeps_the_first_render(engine, monkeypatch):
    engine.segmenter = NoSeg()
    _script(engine, [{"wings_front": "no"}])
    real = engine.renderer.generate

    async def gen(prompt, refs, aspect, previous_response_id=None):
        if previous_response_id:
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "edit refused")
        return await real(prompt, refs, aspect)

    monkeypatch.setattr(engine.renderer, "generate", gen)
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert len(doc["render_attempts"]) == 1 and "edit turn failed" in doc["warnings"][0]


async def test_a_budget_stop_during_the_edit_is_raised(engine, monkeypatch):
    engine.segmenter = NoSeg()
    _script(engine, [{"wings_front": "no"}])
    real = engine.renderer.generate

    async def gen(prompt, refs, aspect, previous_response_id=None):
        if previous_response_id:
            raise ChimeraError(ErrorCode.BUDGET_EXCEEDED, "cap", retryable=False)
        return await real(prompt, refs, aspect)

    monkeypatch.setattr(engine.renderer, "generate", gen)
    with pytest.raises(ChimeraError):
        await engine.fuse(sire_name="lion", dam_name="eagle")


async def test_a_clean_render_makes_no_edit(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    assert doc["inspect"]["edit"] is None and len(doc["render_attempts"]) == 1


async def test_real_hybrids_get_the_plan_blind_protocol_too(engine):
    # S3a: the hand-written pair checklist still scores the render, but inspect runs the balanced protocol on every
    # route; a mule is asked about stripes and spots (planned plain) and must not grow wings.
    doc = await engine.fuse(sire_name="donkey", dam_name="horse")
    keys = {it["key"] for it in doc["inspect"]["before"]["items"]}
    assert {"no_wings", "whole_animal", "plain_fur", "walking_legs"} <= keys
    assert doc["inspect"]["before"]["failures"] == [] and doc["inspect"]["edit"] is None
