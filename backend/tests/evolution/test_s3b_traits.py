"""S3b (mock mode): trait transfer instead of part transfer. Cards (part 1), plan transfers and typed operations
(part 2), the covering compiler (part 3), growth by edit with the drift check (part 4) and the new plan-blind
critic items with the decision rule (part 5)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.evolution import critic as C
from app.evolution.data import cards
from app.evolution.engine import EvoEngine
from app.evolution.genome import LAYER, validate_plan
from app.evolution.prompt import compile_prompt
from app.evolution.transfer import TransferError, apply_edit, derive, fold_shapes
from tests.conftest import make_settings, offline_services

REPO = Path(__file__).resolve().parents[3]
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "recorded" / "s2"


@pytest.fixture
def eng(tmp_path: Path) -> EvoEngine:
    store = tmp_path / "learned.json"
    shutil.copy(REPO / "data" / "learned_animals.json", store)
    return EvoEngine(offline_services(make_settings(tmp_path, evo_learned_path=str(store))), offline=True)


async def _plan(eng: EvoEngine, a: str, b: str, host: str | None = None, mode: str = "speculative"):
    s, d = (await eng.resolve(a)).animal, (await eng.resolve(b)).animal
    g, r = eng.seed_plan(s, d, host_pick=host, design_mode=mode)
    return eng.finish(g, r), r


def _t(g, feature):
    return next(t for t in g.transfers if t.feature == feature)


# ------------------------------------------------------------------ part 1: cards


def test_new_cards_and_supersession():
    book = cards()
    for cid in ("RC-R10-15", "RC-R10-16"):
        assert book[cid].status == "VERIFIED" and book[cid].strength == "soft"
    assert "Transfer traits, not shapes" in book["RC-R10-15"].rule
    assert "flexible cuticle at the joints" in book["RC-R10-16"].rule
    assert book["RC-R10-13"].superseded_by == "RC-R10-15"
    assert "RC-R10-13" not in book.for_tags(["coat_texture"]) and "RC-R10-15" in book.for_tags(["coat_texture"])


# ------------------------------------------------------------------ part 2: transfers


async def test_beetle_bear_transfers(eng):
    g, _ = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    cov, horn = _t(g, "covering"), _t(g, "head horn")
    assert cov.cls == "material" and {"legs", "belly", "head", "tail"} <= set(cov.extent)
    assert cov.extent_reason.startswith("RC-R10-16") and "flexible cuticle at every joint" in cov.scale
    assert horn.cls == "non_homologous" and "frontal bone" in horn.anchor
    assert horn.identity_cues and not re.search(r"\b(not|no)\b", horn.identity_cues)
    assert "covering" in horn.connects and "head horn" in cov.connects
    assert LAYER in g.traits["coat_texture"].flags and g.traits["coat_texture"].region == cov.extent
    assert {"RC-R10-15", "RC-R10-16"} <= set(g.card_trace)


async def test_pangolin_scales_follow_the_donor_system(eng):
    g, _ = await _plan(eng, "axolotl", "chinese pangolin", "sire", "realistic")
    cov = _t(g, "covering")
    assert "belly" not in cov.extent and "legs" in cov.extent and "belly and face stay soft" in cov.extent_reason
    assert "each scale sized to the axolotl's own body segments" in cov.scale


async def test_vertebrate_wings_are_homologous_and_a_patch_keeps_its_plan_regions(eng):
    g, _ = await _plan(eng, "lion", "eagle")
    assert _t(g, "feathered wings").cls == "homologous"
    cov = _t(g, "covering")
    assert set(cov.extent) == {"neck", "forequarters"} and cov.extent_reason.startswith("plan regions")


async def test_an_older_plan_is_read_as_rendered(eng):
    raw = (REPO / "docs/evolution/live/s3a/experiment/beetle_bear/plan.json").read_text(encoding="utf-8")
    import json

    g = validate_plan(json.loads(raw))
    assert g.transfers == []
    cov = next(t for t in derive(g, eng.tax, "regions") if t.kind == "covering")
    assert cov.extent == ["back", "flanks"] and cov.extent_reason == "plan regions (as rendered)"


async def test_elytra_fold_into_material(eng):
    g, r = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    h = g.model_copy(deep=True)
    h.limb_plan.appendages.append("european rhinoceros beetle elytra")
    assert fold_shapes(h, eng.tax) == ["elytra"]
    assert "european rhinoceros beetle elytra" not in h.limb_plan.appendages
    assert any("elytra (RC-R10-15: material only" in f for f in h.traits["body"].flags)


async def test_transfer_edits_are_validated(eng):
    g, _ = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    ts = g.transfers
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "set_transfer_class", "args": {"feature": "head horn", "cls": "homologous"}}, g, eng.tax)
    assert e.value.code == "no_homologous_structure"
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "set_transfer_class", "args": {"feature": "covering", "cls": "b"}}, g, eng.tax)
    assert e.value.code == "covering_is_material"
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "set_extent", "args": {"feature": "covering", "extent": ["back", "flanks"],
                                                     "reason": "looks better on the back"}}, g, eng.tax)
    assert e.value.code == "unexplained_gap"  # RC-R10-16: say why the legs stay bare
    out = apply_edit(ts, {"op": "set_extent", "args": {"feature": "covering", "extent": ["back", "flanks", "head"],
                                                       "reason": "legs stay furred to keep the bear warm in winter"}},
                     g, eng.tax)
    cov = next(t for t in out if t.kind == "covering")
    assert cov.extent == ["head", "back", "flanks"] and cov.set_by == "agent"
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "set_identity_cues", "args": {"feature": "head horn", "cues": "not a rhinoceros horn"}},
                   g, eng.tax)
    assert e.value.code == "negative_cues"
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "connect_features", "args": {"a": "head horn", "b": "head horn"}}, g, eng.tax)
    assert e.value.code == "same_feature"
    with pytest.raises(TransferError) as e:
        apply_edit(ts, {"op": "set_extent", "args": {"feature": "head horn", "extent": ["back"],
                                                     "reason": "a long enough reason"}}, g, eng.tax)
    assert e.value.code == "not_a_covering"


async def test_plan_session_runs_the_transfer_operations(eng):
    sess = await eng.plan_session("rhinoceros beetle", "brown bear")
    res = sess.apply("set_identity_cues", {"feature": "head horn", "cues": "glossy black cuticle, curved upward"})
    assert res.ok and _t(sess.plan, "head horn").identity_cues == "glossy black cuticle, curved upward"
    bad = sess.apply("set_transfer_class", {"feature": "head horn", "cls": "homologous"})
    assert not bad.ok and bad.errors[0].code == "no_homologous_structure"
    assert _t(sess.plan, "head horn").identity_cues == "glossy black cuticle, curved upward"  # unchanged on error
    res = sess.apply("set_extent", {"feature": "covering", "extent": ["head", "neck", "back", "flanks", "legs"],
                                    "reason": "the belly stays furred for warmth on cold ground"})
    assert res.ok and "belly" not in _t(sess.plan, "covering").extent
    assert "belly" in compile_prompt(sess.plan, eng.tax).split("Details:")[1].split(";")[0]  # the host keeps it
    assert any(t["feature"] == "covering" for t in res.summary["transfers"])


async def test_a_layer_is_not_penalized_as_too_many_patches(eng):
    from app.evolution.checks import soft_penalties

    g, r = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    items, _ = soft_penalties(g, r, eng.tax)
    assert not any(i["card"] == "RC-R1-10" for i in items)


# ------------------------------------------------------------------ part 3: the compiler


async def test_covering_is_worded_by_material_extent_scale_and_joints(eng):
    g, _ = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    p = compile_prompt(g, eng.tax)
    assert "grown from the skin as the brown bear's own covering over the crown of the head" in p
    assert "conforms to the brown bear's body" in p and "flexible cuticle at every joint" in p
    assert "brown bear body and legs, with its own dense fur on the face" in p
    assert "bends at every joint" in p
    assert not re.search(r"elytra|shield|domed|patches|wing case", p, re.I)  # no donor-icon shapes
    assert "head horn grown from the frontal bone of the head" in p and "out of the covering" in p
    assert "smooth, glossy dark cuticle" in p


async def test_partial_covering_names_what_the_host_keeps(eng):
    g, _ = await _plan(eng, "axolotl", "chinese pangolin", "sire", "realistic")
    p = compile_prompt(g, eng.tax)
    assert "the face and belly keep the axolotl's own smooth, moist skin" in p
    assert "each scale sized to the axolotl" in p


# ------------------------------------------------------------------ part 4: growth by edit


async def test_growth_renders_host_with_parts_then_grows_the_covering(eng):
    doc = await eng.fuse(sire_name="rhinoceros beetle", dam_name="brown bear", host="dam", growth="edit")
    gr = doc["growth"]
    assert "head horn grown from the frontal bone" in gr["first_prompt"]  # discrete parts are never grown by edit
    assert "chitin plates" not in gr["first_prompt"]
    assert gr["instruction"].startswith("Now grow the covering:") and "head horn exactly where" in gr["instruction"]
    assert gr["used"] and not gr["drift"]["drifted"] and doc["meta_calls"]["image"] == 2


async def test_growth_falls_back_to_the_first_pass_render_on_drift(eng):
    real = eng.spark.describe
    seen: list[int] = []

    async def describe(image: bytes) -> dict[str, Any]:
        d = await real(image)
        seen.append(1)
        if len(seen) in (2, 4):  # the grown image, as seen by both drift critics: the tail changed
            d = {**d, "tails": 2}
        return d

    eng.spark.describe = describe  # type: ignore[method-assign]
    doc = await eng.fuse(sire_name="rhinoceros beetle", dam_name="brown bear", host="dam", growth="edit")
    gr = doc["growth"]
    assert gr["drift"]["drifted"] and gr["drift"]["changed"] == ["tails"] and not gr["used"]
    assert doc["meta_calls"]["image"] == 3 and doc["prompt"] == doc["prompt_compiled"]
    assert "growth edit drifted the host (tails)" in doc["warnings"][0]


async def test_growth_is_for_coverings_only(eng):
    doc = await eng.fuse(sire_name="lion", dam_name="tiger", growth="edit")
    assert "growth" not in doc and doc["meta_calls"]["image"] == 1


# ------------------------------------------------------------------ part 5: critic items and decision


async def test_new_plan_blind_items(eng):
    g, _ = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    q = {x.id: x for x in C.questions(g, eng.tax)}
    for key, expect in (("follows_body", "yes"), ("separate_outline", "no"), ("sized_to_body", "yes"),
                        ("wrong_scale", "no"), ("legs_covered", "yes"), ("abrupt_stop", "no"),
                        ("connects_head_horn", "yes"), ("separate_head_horn", "no")):
        assert q[key].expect == expect, key
    assert "cover_on_legs" not in q  # the legs are inside the extent (RC-R10-16)
    assert C.origin_parts(g, eng.tax) == [("head horn", "the head horn")]
    assert sum(x.expect == "no" for x in q.values()) * 2 >= len(q)


async def test_bare_plan_regions_make_placement_informational(eng):
    import json

    g = validate_plan(json.loads((REPO / "docs/evolution/live/s3a/experiment/axolotl_pangolin/plan.json")
                                 .read_text(encoding="utf-8")))
    q = {x.id: x for x in C.questions(g, eng.tax)}
    assert q["cover_on_shoulders"].group == "surface"


@pytest.mark.parametrize("said,expect", [("rhinoceros beetle", "ok"), ("beetle", "ok"), ("a stag beetle", "ok"),
                                         ("insect", "ok"), ("rhinoceros", "bad"), ("bear", "bad"),
                                         ("unclear", "unk"), ("", "unk")])
def test_origin_scoring(eng, said, expect):
    beetle = eng.tax.resolve("european_rhinoceros_beetle")
    assert C.origin_outcome(said, beetle) == expect


def test_absent_parts_and_sucker_spots_are_not_sightings():
    d = {"description": "an eagle", "parts": [{"part": "gills", "looks_like": "none visible", "where": "n/a"},
                                               {"part": "mane", "looks_like": "none; neck feathers ruffled",
                                                "where": "neck"},
                                               {"part": "horns", "looks_like": "", "where": "head"}],
         "attached_objects": []}
    assert C.seen_concepts(C.description_text(d)) == set()
    assert C.seen_concepts("circular sucker-like spots on the thighs") == {"tentacles"}


async def test_primary_decision_lets_one_critic_decide_and_keeps_the_other_as_information(eng):
    g, r = await _plan(eng, "rhinoceros beetle", "brown bear", "dam")
    qs = C.questions(g, eng.tax)
    on_top = next(q for q in qs if q.id == "on_top")
    base = {q.text: q.expect for q in qs}
    desc = {"description": "a bear with a glossy horn and a plated covering", "parts": [],
            "attached_objects": [], "animals": ["brown bear", "rhinoceros beetle"], "separate_bodies": 1, "heads": 1,
            "walking_legs": 4, "wings": 0, "extra_limb_pieces": 0, "tails": 1}
    raws = {"meta_spark": C.Raw(describe=desc, answers=dict(base)),
            "spark_open": C.Raw(describe=desc, answers={**base, on_top.text: "yes"})}
    pair = C.evaluate(raws, g, eng.tax, r, qs, decision="pair")
    prim = C.evaluate(raws, g, eng.tax, r, qs, decision="primary")
    assert any(s["key"] == "on_top" and s["status"] == "uncertain" for s in pair["signals"])
    row = next(x for x in prim["rows"] if x["key"] == "on_top")
    assert prim["verdict"] == "pass" and row["status"] == "pass" and row["pair_status"] == "uncertain"
    assert prim["decision"]["primary"] == "meta_spark" and "on_top" in prim["decision"]["disagreements"]


def test_the_ask_request_lists_parts_for_origins():
    import io

    from PIL import Image

    from app.evolution.live import build_ask_request, parse_ask_response

    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    body = build_ask_request("m", buf.getvalue(), ["Is there a horn?"], ["the head horn"])
    text = body["messages"][1]["content"][0]["text"]
    assert "Parts (which animal does each look like it came from?):\n1. the head horn" in text
    import json

    payload = {"choices": [{"message": {"content": json.dumps({"answers": ["yes"], "origins": ["rhinoceros beetle"],
                                                               "notes": ""})}}]}
    assert parse_ask_response(payload, ["Is there a horn?"], ["the head horn"])["origins"] == {
        "the head horn": "rhinoceros beetle"}


# ------------------------------------------------------------------ validation findings (part 6)


async def test_an_id_prefixed_appendage_still_transfers(eng):
    s, d = (await eng.resolve("rhinoceros beetle")).animal, (await eng.resolve("brown bear")).animal
    g, r = eng.seed_plan(s, d, host_pick="dam")
    g.limb_plan.appendages = ["european_rhinoceros_beetle head horn"]  # as a live model plan wrote it
    g = eng.finish(g, r)
    assert "european rhinoceros beetle head horn" in g.limb_plan.appendages
    assert any(t.feature == "head horn" for t in g.transfers)


async def test_a_count_that_reaches_the_plan_is_not_drift():
    from app.evolution.growth import drift

    class Crit:
        def __init__(self) -> None:
            self.n = 0

        async def describe(self, image: bytes) -> dict[str, int]:
            self.n += 1
            return {"heads": 1, "walking_legs": 4, "tails": 0 if self.n == 1 else 1}

    class M:
        async def call(self, kind, purpose, aw):
            return await aw

    planned = {"heads": 1, "walking_legs": 4, "tails": 1}
    d = await drift(b"a", b"b", {"x": Crit(), "y": Crit()}, M(), planned)
    assert not d["drifted"] and d["any_change"] == []
    d = await drift(b"a", b"b", {"x": Crit(), "y": Crit()}, M(), {**planned, "tails": 0})
    assert d["drifted"] and d["changed"] == ["tails"]


def test_a_tortoise_beak_is_expected(eng):
    from app.evolution.data import Animal

    tort = Animal(id="tortoise", common_name="tortoise", scientific_name="Testudo graeca", tax_class="Reptilia",
                  family="Testudinidae", body_plan="quadruped", covering="shell", mass_kg=1.5, habitats=("desert",),
                  climate=("arid",), active_time=("diurnal",), group="vertebrate", order="Testudines")
    eng.tax.add(tort, ["tortoise"])
    g, r = eng.seed_plan(tort, eng.tax.resolve("domestic goat"), host_pick="sire", design_mode="realistic")
    g = eng.finish(g, r)
    exp, _ = C.planned_concepts(g, eng.tax)
    assert "beak" in exp
