"""S2 part 3: the plan as small typed operations (ops.PlanSession), each validated on its own, with errors the
agent can act on. Code fills card_trace and every derived list. The legacy full-plan path still works."""

from __future__ import annotations

import json

import pytest

from app.evolution import live
from app.evolution.checks import Violation
from app.evolution.ops import OPS


async def _session(engine, sire="lion", dam="eagle", mode="speculative"):
    return await engine.plan_session(sire, dam, mode)


def _codes(res):
    return [e.code for e in res.errors]


# ------------------------------------------------------------------ the six operations


async def test_set_host_swaps_the_frame(engine):
    s = await _session(engine, "lion", "octopus")
    assert s.plan.host == "lion"
    res = s.apply("set_host", {"animal": "common octopus"})
    assert res.ok and s.plan.host == "common_octopus" and res.summary["host"].lower() == "common octopus"


async def test_set_region_patch_head_and_tail(engine):
    s = await _session(engine, "tiger", "octopus")
    assert s.apply("set_region", {"region": "head", "donor": "octopus", "operator": "PICK"}).ok
    assert s.plan.traits["head"].donor == "common_octopus" and s.plan.traits["skull"].donor == "common_octopus"
    assert s.apply("set_region", {"region": "tail", "donor": "tiger", "operator": "PICK"}).ok
    assert s.plan.traits["tail"].part is None and s.plan.traits["tail"].donor == "tiger"
    patches = set(s.summary()["patches"]["regions"])
    target = next(r for r in ("belly", "neck", "hindquarters") if r not in patches)
    if len(patches) >= 3:
        assert s.apply("set_region", {"region": sorted(patches)[0], "donor": "tiger", "operator": "PICK"}).ok
    assert s.apply("set_region", {"region": target, "donor": "octopus", "operator": "PATCH"}).ok
    assert target in s.summary()["patches"]["regions"]


async def test_set_region_forelimbs_back_to_the_host_removes_the_wings(engine):
    s = await _session(engine)
    assert s.plan.limb_plan.forelimbs.kind == "wings"
    assert s.apply("set_region", {"region": "forelimbs", "donor": "lion", "operator": "PICK"}).ok
    assert not s.plan.limb_plan.has_wings() and "wing" not in s.plan.silhouette


async def test_set_habitat_and_set_mode(engine):
    s = await _session(engine)
    assert s.apply("set_habitat", {"name": "Mountain"}).ok and s.plan.habitat.name == "mountain"
    assert s.plan.habitat.source == "user"
    assert s.apply("set_mode", {"mode": "mythic"}).ok and s.plan.design_mode == "mythic"
    assert s.plan.limb_plan.extra_wings is not None and s.plan.licenses


async def test_add_license_with_the_agents_compensation(engine):
    s = await _session(engine, mode="mythic")
    comp = "wings rooted in a deep, muscled shoulder hump that carries them"
    res = s.apply("add_license", {"rule": "RC-R3-02", "compensation": comp})  # by card id
    assert res.ok and s.plan.licenses[0].id == "six_limbs" and s.plan.licenses[0].compensation == comp
    assert comp in res.summary["checklist_preview"]


async def test_drop_part_removes_it_everywhere(engine):
    s = await _session(engine)
    res = s.apply("drop_part", {"part": "wings", "reason": "the agent wants a ground hunter"})
    assert res.ok and not s.plan.limb_plan.has_wings() and "wings" in res.summary["dropped"]
    assert "no wings" in res.summary["checklist_preview"]


# ------------------------------------------------------------------ errors the agent can act on


@pytest.mark.parametrize("op,args,code,field", [
    ("set_host", {"animal": "zebra"}, "not_a_parent", "animal"),
    ("set_region", {"region": "elbow", "donor": "lion", "operator": "PICK"}, "unknown_region", "region"),
    ("set_region", {"region": "head", "donor": "eagle", "operator": "PATCH"}, "bad_operator", "operator"),
    ("set_region", {"region": "back", "donor": "lion", "operator": "PATCH"}, "donor_is_host", "donor"),
    ("set_region", {"region": "back", "donor": "eagle", "operator": "OVERLAY"}, "no_pattern", "operator"),
    ("set_habitat", {"name": "swamp"}, "unknown_habitat", "name"),
    ("set_mode", {"mode": "cartoon"}, "unknown_mode", "mode"),
    ("add_license", {"rule": "RC-R9-01", "compensation": "x"}, "never_licensable", "rule"),
    ("add_license", {"rule": "flying_pigs", "compensation": "x"}, "not_bendable", "rule"),
    ("add_license", {"rule": "land_gills", "compensation": "x"}, "not_needed", "rule"),
    ("drop_part", {"part": "antlers", "reason": "r"}, "no_such_part", "part"),
    ("drop_part", {"part": "wings", "reason": " "}, "missing_reason", "reason"),
])
async def test_each_error_names_its_field_and_leaves_the_plan_unchanged(engine, op, args, code, field):
    s = await _session(engine)
    before = s.plan.id
    res = s.apply(op, args)
    assert not res.ok and _codes(res) == [code] and res.errors[0].field == field
    assert res.errors[0].valid or res.errors[0].hint
    assert s.plan.id == before and s.log[-1] == {"op": op, "args": args, "ok": False, "errors": [code]}


async def test_unknown_op_and_bad_arguments(engine):
    s = await _session(engine)
    assert _codes(s.apply("frobnicate", {})) == ["unknown_op"] and s.apply("frobnicate", {}).errors[0].valid == list(OPS)
    assert _codes(s.apply("set_mode", {"style": "x"})) == ["bad_arguments"]


async def test_over_budget_and_compensation_rules(engine):
    s = await _session(engine, mode="mythic")
    assert _codes(s.apply("add_license", {"rule": "six_limbs", "compensation": ""})) == ["bad_compensation"]
    assert s.apply("add_license", {"rule": "six_limbs", "compensation": "a heavy shoulder hump"}).ok
    res = s.apply("set_mode", {"mode": "speculative"})  # speculative budget 1: the one request still fits
    assert res.ok and res.warnings == []
    res = s.apply("set_mode", {"mode": "realistic"})
    assert res.ok and "removed" in res.warnings[0] and s.plan.licenses == []


async def test_a_hard_card_failure_is_reverted(engine, monkeypatch):
    s = await _session(engine)
    before = s.plan.id
    monkeypatch.setattr(engine, "_check", lambda g, r, final=True: [Violation("RC-R3-09", "forced for the test")]
                        if g.habitat.name == "desert" else [])
    res = s.apply("set_habitat", {"name": "desert"})
    assert not res.ok and _codes(res) == ["hard_card"] and "RC-R3-09" in res.errors[0].message
    assert s.plan.id == before and s.habitat is None


async def test_real_hybrids_reject_region_edits(engine):
    s = await _session(engine, "donkey", "horse")
    assert _codes(s.apply("set_region", {"region": "head", "donor": "horse", "operator": "PICK"})) == ["not_allowed"]
    assert _codes(s.apply("set_host", {"animal": "horse"})) == ["not_allowed"]


# ------------------------------------------------------------------ code fills the derived lists


async def test_code_fills_card_trace_and_derived_lists(engine):
    s = await _session(engine)
    s.apply("set_habitat", {"name": "forest"})
    g = s.plan
    assert g.card_trace and g.labels and g.audit and g.checks and g.silhouette and g.id.startswith("crt_")
    assert "RC-R3-01" in g.card_trace  # from the code's limb-budget check, not from any operation


def test_plan_schema_leaves_the_derived_lists_to_code():
    for f in ("card_trace", "labels", "processes", "render_details", "licenses", "audit", "checks"):
        assert f not in live.PLAN_SCHEMA["properties"] and f in live.CODE_FIELDS


def test_legacy_parser_ignores_a_model_card_trace(engine):
    from tests.evolution.conftest import plan_for

    g, _ = plan_for(engine, "lion", "eagle")
    sk = g.model_dump()
    model = {**sk, "card_trace": ["RC-R9-01"] * 500, "labels": ["a real animal"]}
    out = live.parse_plan_response({"choices": [{"message": {"content": json.dumps(model)}}]}, sk)
    assert out["card_trace"] == sk["card_trace"] and out["labels"] == sk["labels"]


async def test_a_session_plan_renders_like_any_plan(engine):
    s = await _session(engine, "tiger", "octopus")
    s.apply("set_habitat", {"name": "wetland"})
    doc = await engine.realize(s.plan, s.route, [])
    assert doc["genome"]["id"] == s.plan.id and doc["judge"]["scores"]["quality"] > 0


async def test_legacy_full_plan_path_still_works(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="eagle", host="sire")  # S3c (D2): a tie needs a host choice
    assert doc["model_plan"] == "accepted" and doc["genome"]["card_trace"]
