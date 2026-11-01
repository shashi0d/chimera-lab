"""S5 (mock mode): the fixes the benchmark depends on (D1 material-only covering, D2 a reason against the code's
ranking, D3 typed tool schemas replaying S3c's 15 refused calls), the anatomy map and the fixed benchmark file."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.evolution import agent as A
from app.evolution.critic import questions
from app.evolution.engine import EvoEngine
from app.evolution.prompt import compile_prompt
from app.services import build_services
from tests.conftest import make_settings

REPO = Path(__file__).resolve().parents[3]
FIX = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def eng(tmp_path: Path) -> EvoEngine:
    store = tmp_path / "learned.json"
    shutil.copy(REPO / "data" / "learned_animals.json", store)
    return EvoEngine(build_services(make_settings(tmp_path, evo_learned_path=str(store))))


async def _run_to_plan(eng: EvoEngine, a: str, b: str, mode: str = "speculative", cand: str = "C1",
                       ops: list[dict[str, Any]] | None = None) -> A.AgentRun:
    run = A.AgentRun(eng, a, b, mode, brain=A.PolicyBrain(lambda r: None))
    for name in (a, b):
        assert (await run.call("resolve_animal", {"name": name, "reason": "parent"}))["ok"]
    await run.call("propose_candidates", {"reason": "options"})
    assert (await run.call("choose_candidate", {"candidate_id": cand, "reason": "pick"}))["ok"]
    for o in ops or []:
        assert (await run.call("plan_op", {**o, "reason": "replay"}))["ok"], o
    return run


def fake_inspect(seq: list[list[dict[str, Any]]]):
    """Each inspect returns the next failure list (the last one repeats)."""
    it = iter(seq)
    last: list[list[dict[str, Any]]] = [seq[-1]]

    async def _inspect(image: bytes, g: Any, r: Any, verdict: dict[str, Any]) -> dict[str, Any]:
        fails = next(it, last[0])
        rows = [{"status": "fail", "fix": f"fix {f['key']}", "text": f["key"], "answers": {}, **f} for f in fails]
        return {"failures": rows, "items": rows, "structural_failures": len(rows), "descriptions": {
            "meta_spark": {"heads": 1, "walking_legs": 4, "tails": 1}}, "expected_counts": {}, "third_animals": {}}
    return _inspect


# ------------------------------------------------------------------ D1: material-only covering


async def test_d1_material_only_keeps_the_host_covering_and_the_identity_part(eng):
    run = await _run_to_plan(eng, "rhinoceros beetle", "brown bear")
    before = compile_prompt(run.session.plan, eng.tax)
    assert "chitin plates" in before
    out = await run.call("set_covering_material_only", {"plan_reason": "two edits left the plates looking laid on top",
                                                        "reason": "two-failure rule, second route"})
    assert out["ok"] and out["changed"]
    g = run.session.plan
    cov = next(t for t in g.transfers if t.kind == "covering")
    assert (cov.form, cov.set_by) == ("material_only", "agent") and "laid on top" in cov.form_reason
    p = compile_prompt(g, eng.tax)
    assert "plates" not in p and "dense fur stays dense fur everywhere" in p
    assert "rhinoceros beetle's colors, gloss, surface texture and pattern" in p
    assert "head horn" in p and [i.part for i in g.identity_parts] == ["head horn"]  # the identity part is kept
    ids = [q.id for q in questions(g, eng.tax)]
    assert {"material_look", "host_cover_kept", "donor_pieces"} <= set(ids)
    assert not {"on_top", "grows_out", "cover_present", "abrupt_stop"} & set(ids)
    assert (await run.call("set_covering_material_only", {"plan_reason": "short", "reason": "x"}))["error"] == "schema"


async def test_d1_the_two_failure_rule_routes_to_material_only(eng, monkeypatch):
    monkeypatch.setattr(eng, "_inspect", fake_inspect([[{"key": "on_top", "group": "integration"}]]))
    run = await _run_to_plan(eng, "rhinoceros beetle", "brown bear")
    assert "set_covering_material_only" in run.system_prompt()
    assert "set_transfer_class with cls non_homologous" not in run.system_prompt()
    await run.call("audit_plan", {"reason": "check"})
    img = (await run.call("render", {"method": "single_pass", "reason": "go"}))["image_id"]
    await run.call("inspect", {"image_id": img, "reason": "check"})
    e1 = (await run.call("edit", {"image_id": img, "failure_keys": ["on_top"], "reason": "fix"}))["image_id"]
    second = await run.call("inspect", {"image_id": e1, "reason": "check"})
    assert "set_covering_material_only" in second["rule"]
    refused = await run.call("edit", {"image_id": e1, "failure_keys": ["on_top"], "reason": "again"})
    assert refused["error"] == "two_failure_rule" and "set_covering_material_only" in refused["valid"]
    assert (await run.call("set_covering_material_only", {"plan_reason": "the plates read as worn armor twice",
                                                          "reason": "rule"}))["changed"]
    assert run.state.edit_lock is None and run.state.covering_streak == 0


# ------------------------------------------------------------------ D2: a reason against the code's ranking


async def test_d2_finalizing_a_lower_ranked_image_needs_a_reason_and_the_card_keeps_both(eng, monkeypatch):
    monkeypatch.setattr(eng, "_inspect", fake_inspect([[{"key": "on_top", "group": "integration"}],
                                                       [{"key": "third_animal", "group": "structure"}]]))
    run = await _run_to_plan(eng, "rhinoceros beetle", "brown bear")
    await run.call("audit_plan", {"reason": "check"})
    i1 = (await run.call("render", {"method": "single_pass", "reason": "go"}))["image_id"]
    await run.call("inspect", {"image_id": i1, "reason": "check"})
    i2 = (await run.call("edit", {"image_id": i1, "failure_keys": ["on_top"], "reason": "fix"}))["image_id"]
    await run.call("inspect", {"image_id": i2, "reason": "check"})
    assert run.best_image_id() == i1  # 0 structural beats 1 structural
    refused = await run.call("finalize", {"image_id": i2, "reason": "fewest failures"})
    assert refused["error"] == "needs_why_not_best" and refused["valid"] == [i1, i2]
    out = await run.call("finalize", {"image_id": i2, "why_not_best": "the plates are grown in; the pill-bug read is "
                                      "a critic misread", "reason": "my pick"})
    assert out["ok"] and out["final_choice"] == {"agree": False, "shown_first": "agent"}
    fc = run.state.finalized["card"]["final_choice"]
    assert list(fc) == ["shown_first", "agree", "agent_pick", "code_pick"]
    assert (fc["agent_pick"]["image_id"], fc["agent_pick"]["rank"], fc["agent_pick"]["structural"]) == (i2, 2, 1)
    assert (fc["code_pick"]["image_id"], fc["code_pick"]["rank"], fc["code_pick"]["structural"]) == (i1, 1, 0)
    assert "pill-bug" in fc["agent_pick"]["reason"] and "fewest structural" in fc["code_pick"]["reason"]
    files = eng.services.settings.resolved_local_dir() / "files"
    assert (files / fc["agent_pick"]["image_key"]).exists() and (files / fc["code_pick"]["image_key"]).exists()


async def test_d2_agreeing_picks_need_no_extra_reason(eng):
    doc, run = await eng.agent_fuse("crab", "gray wolf")
    fc = doc["card"]["final_choice"]
    assert fc["agree"] and fc["agent_pick"]["image_id"] == fc["code_pick"]["image_id"]
    assert fc["agent_pick"]["reason"]


# ------------------------------------------------------------------ D3: the 15 refused S3c calls, replayed


REFUSED = json.loads((FIX / "s3c_refused_calls.json").read_text(encoding="utf-8"))
SCHEMA_CAUGHT = {"covering_is_material", "not_a_part", "no_such_part", "bad_arguments"}


def _as_tool_call(rec: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """An S3c plan_op call as a call to the S5 operation tool (`reason` inside the op is now `plan_reason`)."""
    args = dict(rec["args"])
    if rec["op"] == "set_extent":
        args.pop("feature", None)
    if "reason" in args:
        args["plan_reason"] = args.pop("reason")
    return rec["op"], {**args, "reason": rec["reason"]}


def test_d3_the_fixture_holds_the_15_refusals():
    assert len(REFUSED) == 15
    assert sorted({r["error"] for r in REFUSED}) == ["bad_arguments", "covering_is_material", "no_such_part",
                                                      "not_a_part", "unexplained_gap"]


@pytest.mark.parametrize("rec", REFUSED, ids=[f"{r['run'].split('/', 2)[2]}#{r['step']}-{r['error']}" for r in REFUSED])
async def test_d3_each_refused_call_is_stopped_by_the_new_schema_or_guided_by_its_description(eng, rec):
    run = await _run_to_plan(eng, rec["sire"], rec["dam"], rec["mode"], rec["candidate"], rec["ops_before"])
    name, args = _as_tool_call(rec)
    schema = next(t["function"] for t in run.tools() if t["function"]["name"] == name)
    out = await run.call(name, args)
    assert not out["ok"]
    if rec["error"] in SCHEMA_CAUGHT:
        # refused by the schema before the operation runs, with the reason in the message
        assert out["error"] == "schema", out
        if rec["error"] in ("covering_is_material", "not_a_part"):
            assert "'covering' is not one of" in out["message"] or "must be a string" in out["message"]
            assert "Parts only" in schema["description"] or "parts only" in schema["description"].lower()
        if rec["error"] == "no_such_part":
            assert "is not one of" in out["message"] and "not a part of the plan" in schema["description"]
        if rec["error"] == "bad_arguments":
            assert "missing 'plan_reason'" in out["message"]
    else:
        # unexplained_gap depends on the donor (an exoskeleton): the description now says what the code requires
        assert out["errors"][0]["code"] == "unexplained_gap"
        assert "name the legs in plan_reason" in schema["description"]
        fixed = {**args, "plan_reason": args["plan_reason"] + "; the legs stay furred for climbing grip"}
        assert (await run.call(name, fixed))["ok"]
