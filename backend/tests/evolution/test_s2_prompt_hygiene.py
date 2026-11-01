"""S2 part 2: the render prompt is compiled only from structured plan fields (plus data tables and the code-made
render_details). Model-written notes never reach it, on any route. The forced choice is gone everywhere."""

from __future__ import annotations

import pytest

from app.evolution import live
from app.evolution.audit import apply_judgment
from app.evolution.prompt import compile_prompt
from tests.evolution.conftest import plan_for

MARK = "zqx model note"


def _poison(g):
    for tag, tr in g.traits.items():
        g.traits[tag] = tr.model_copy(update={"note": f"{MARK} on {tag}: wings, four legs, stripes"})
    return g


@pytest.mark.parametrize("sire,dam,myth", [("lion", "eagle", False), ("lion", "eagle", True),
                                           ("tiger", "octopus", False), ("tiger", "leopard", False),
                                           ("donkey", "horse", False), ("lion", "tiger", False)])
def test_trait_notes_never_reach_the_prompt(engine, sire, dam, myth):
    g, _ = plan_for(engine, sire, dam, myth=myth)
    assert MARK not in compile_prompt(_poison(g), engine.tax)


async def test_a_model_plan_full_of_notes_renders_without_them(engine):
    real = engine.spark.write_plan

    async def chatty(prompt, skeleton):
        plan = await real(prompt, skeleton)
        for tag in plan["traits"]:
            plan["traits"][tag]["note"] = f"{MARK} ({tag})"
        plan["render_details"] = [f"{MARK} injected"]  # code-owned: the model cannot write it
        return live.parse_plan_response({"choices": [{"message": {"content": __import__("json").dumps(plan)}}]},
                                        skeleton)

    engine.spark.write_plan = chatty  # type: ignore[method-assign]
    doc = await engine.fuse(sire_name="tiger", dam_name="octopus")
    assert doc["model_plan"] == "accepted"
    assert MARK not in doc["prompt"] and MARK not in doc["prompt_compiled"]


def test_code_repairs_reach_the_prompt_through_render_details(engine):
    g, _ = plan_for(engine, "tiger", "octopus")  # octopus arms as a tail: jointless soft part (RC-R3-10)
    assert "jointless and smoothly curving; longer means thinner" in g.render_details
    p = compile_prompt(g, engine.tax)
    assert all(d in p for d in g.render_details)


def test_license_compensation_reaches_the_prompt_once(engine):
    g, _ = plan_for(engine, "lion", "eagle", myth=True)
    comp = g.licenses[0].compensation
    assert comp not in g.render_details and compile_prompt(g, engine.tax).count(comp) == 1


def test_a_model_judged_repair_stays_on_the_card_not_in_the_prompt(engine):
    g, _ = plan_for(engine, "moon_jellyfish", "lion", host_pick="sire")
    pending = [i.function for i in g.audit if i.result == "pending"]
    assert pending
    apply_judgment(g, [{"function": f, "result": "repaired", "detail": "d", "repair": f"{MARK} repair"}
                       for f in pending])
    assert MARK not in compile_prompt(g, engine.tax)
    assert any(MARK in (i.detail or "") for i in g.audit)  # still on the card


def test_render_details_are_code_owned():
    assert "render_details" in live.CODE_FIELDS and "render_details" not in live.PLAN_SCHEMA["properties"]


def test_finish_rebuilds_render_details(engine):
    g, r = plan_for(engine, "tiger", "octopus")
    g.render_details.append("stale text")
    assert "stale text" not in engine.finish(g, r).render_details


def test_no_forced_choice_anywhere():
    schema = live.checklist_schema()
    assert "choice" not in schema["properties"] and "choice" not in live.CHECKLIST_INSTRUCTIONS
