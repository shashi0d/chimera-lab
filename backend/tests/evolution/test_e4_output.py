"""E4 step 5: checklist generated from the plan, the output card ("Can it live?", licenses, kind,
provenance per fact) and the prosaic-detail line in every render prompt."""

from __future__ import annotations

import pytest

from app.evolution.card import output_card, safe_text
from app.evolution.data import config, known_pairs
from app.evolution.genome import validate_plan
from app.evolution.judge import CHECKLIST_MAX, CHECKLIST_MIN, checklist_for, generated_checklist
from app.evolution.prompt import compile_prompt
from tests.evolution.conftest import plan_for


def _plan(engine, sire, dam, mode="speculative", **kw):
    a, b = engine.tax.resolve(sire), engine.tax.resolve(dam)
    g, r = engine.seed_plan(a, b, design_mode=mode, **kw)
    return engine.finish(g, r), r


# ------------------------------------------------------------------ checklist generation


@pytest.mark.parametrize("sire,dam,mode", [("lion", "eagle", "speculative"), ("lion", "eagle", "mythic"),
                                           ("eagle", "octopus", "speculative"), ("guanaco", "llama", "realistic"),
                                           ("tiger", "leopard", "speculative"), ("lion", "goldfish", "realistic")])
def test_generated_checklist_has_4_to_6_visible_items(engine, sire, dam, mode):
    g, _ = _plan(engine, sire, dam, mode)
    items = generated_checklist(g, engine.tax)
    assert CHECKLIST_MIN <= len(items) <= CHECKLIST_MAX and len(set(items)) == len(items)
    assert "_" not in " ".join(items)  # common names, never ids


def test_checklist_from_the_plan_names_frame_head_and_parts(engine):
    g, _ = _plan(engine, "lion", "eagle")
    items = generated_checklist(g, engine.tax)
    assert items[0] == "a lion body shape" and items[1] == "a lion head with visible eyes"
    assert "golden eagle wings in place of the front legs" in items
    assert any("golden eagle feathers patches" in x for x in items)


def test_checklist_puts_license_compensations_first(engine):
    g, _ = _plan(engine, "lion", "eagle", "mythic")
    items = generated_checklist(g, engine.tax)
    assert items[2] == g.licenses[0].compensation
    assert "four legs plus a separate pair of golden eagle wings" in items


async def test_checklist_shows_kept_gills_and_size_compensation(engine):
    await engine.resolve("pangolin")
    g, _ = _plan(engine, "axolotl", "pangolin")
    assert "axolotl external gills on the sides of the head" in generated_checklist(g, engine.tax)
    await engine.resolve("rhinoceros beetle")
    b, _ = _plan(engine, "rhinoceros beetle", "brown bear")
    assert b.licenses[0].compensation in generated_checklist(b, engine.tax)


def test_hand_written_checklists_take_priority(engine):
    g, r = plan_for(engine, "donkey", "horse")
    mule = next(p for p in known_pairs() if p["id"] == "mule")["checklist"]
    assert checklist_for(r) == mule


async def test_judge_keeps_count_third_animal_and_logs_the_open_critic(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="eagle")
    j = doc["judge"]
    assert j["critic"]["creatures"] == 1 and "animals" in j["critic"] and j["third_animal"] == []
    assert j["checklist"] == generated_checklist(validate_plan(doc["genome"]), engine.tax)
    assert "animals" in j["open_critic"] and j["forced_choice"]["full"] in ("lion", "golden eagle", "a mix of both", "other")


# ------------------------------------------------------------------ output card


async def test_card_has_can_it_live_panel_licenses_kind_and_provenance(engine):
    doc = await engine.fuse(sire_name="lion", dam_name="eagle", mode="mythic")
    card = doc["card"]
    assert card["kind"] == "mythic composite" and card["design_mode"] == "mythic"
    assert [p["function"] for p in card["can_it_live"]] == ["breathing", "feeding", "support", "movement", "heat",
                                                             "senses"]
    move = next(p for p in card["can_it_live"] if p["function"] == "movement")
    assert move["result"] == "licensed" and "RC-R3-02" in move["cards"] and move["decided_by"].startswith("code")
    assert card["licenses"][0]["card"] == "RC-R3-02" and card["licenses"][0]["compensation"]
    assert card["provenance"]["sire"]["facts"]["family"] == "chimera_data.json"


async def test_card_provenance_marks_gbif_and_model_estimated_facts(engine):
    doc = await engine.fuse(sire_name="woolly mammoth", dam_name="lion")
    facts = doc["card"]["provenance"]["sire"]
    assert facts["kind"] == "extinct" and facts["source"] == "learned"
    assert facts["facts"]["family"] == "gbif" and facts["facts"]["diet"] == "model-estimated"


@pytest.mark.parametrize("sire,dam,kind", [("donkey", "horse", "hybrid"), ("guanaco", "llama", "hybrid"),
                                           ("lion", "eagle", "chimera")])
def test_card_kind_vocabulary(engine, sire, dam, kind):
    g, r = plan_for(engine, sire, dam)
    card = output_card(g, r, engine.tax)
    assert card["kind"] == kind
    if r.mode == "hybrid" and not r.pair:
        assert card["label"].startswith("speculative hybrid")  # the plain word hybrid: real-hybrid route only


def test_card_model_judged_entries_are_marked(engine):
    g, r = plan_for(engine, "moon_jellyfish", "lion", host_pick="sire")
    panel = output_card(g, r, engine.tax)["can_it_live"]
    assert next(p for p in panel if p["function"] == "breathing")["decided_by"] == "model-judged"


def test_card_text_never_states_oxygen_as_settled():
    assert "debated" in safe_text("giant insects were large because of high oxygen", distant=True)


# ------------------------------------------------------------------ prosaic detail in every mode


@pytest.mark.parametrize("sire,dam,mode", [("lion", "eagle", "realistic"), ("lion", "eagle", "speculative"),
                                           ("lion", "eagle", "mythic"), ("donkey", "horse", "speculative")])
def test_prosaic_detail_line_in_every_mode(engine, sire, dam, mode):
    g, _ = _plan(engine, sire, dam, mode)
    assert f"Prosaic detail: {config()['prosaic_detail']}." in compile_prompt(g, engine.tax)
