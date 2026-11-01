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


# ------------------------------------------------------------------ part 2: the anatomy map


async def test_anatomy_map_colors_parts_by_parent_and_never_guesses(eng, monkeypatch):
    import io

    from PIL import Image

    from app.errors import ChimeraError
    from app.evolution.anatomy import COLORS
    from app.models.schemas import ErrorCode

    real = eng.segmenter.segment

    async def segment(image: bytes, label: str) -> bytes:
        if label == "head horn":  # SAM finds nothing
            out = io.BytesIO()
            Image.new("L", (64, 64), 0).save(out, "PNG")
            return out.getvalue()
        if label == "tail":
            raise ChimeraError(ErrorCode.UPSTREAM_ERROR, "sam down")
        return await real(image, label)

    monkeypatch.setattr(eng.segmenter, "segment", segment)
    doc, run = await eng.agent_fuse("rhinoceros beetle", "brown bear")
    amap = doc["card"]["anatomy_map"]
    by = {p["part"]: p for p in amap["parts"]}
    horn = by["european rhinoceros beetle head horn"]
    assert (horn["found"], horn["status"], horn["color"], horn["parent_role"]) == (False, "not located", None, "donor")
    assert horn["mask_area"] == 0.0
    assert by["tail"]["status"] == "not located" and "sam down" in by["tail"]["error"]
    assert by["head"]["parent_role"] == "host" and by["head"]["color"] == "#{:02x}{:02x}{:02x}".format(*COLORS["host"])
    cov = next(p for p in amap["parts"] if p["part"].endswith("covering"))
    assert cov["parent_name"].lower().endswith("rhinoceros beetle") and cov["found"]
    assert cov["color"] == "#{:02x}{:02x}{:02x}".format(*COLORS["donor"])
    assert amap["not_located"] == 2 and amap["found"] == len(amap["parts"]) - 2
    files = eng.services.settings.resolved_local_dir() / "files"
    png = (files / amap["overlay_key"]).read_bytes()
    with Image.open(io.BytesIO(png)) as im:
        assert im.width == amap["image_size"][0] and im.height > amap["image_size"][1]  # the image plus a legend
    assert (run.image_dir / "anatomy_map.png").exists()


async def test_anatomy_map_parts_follow_the_plan(eng):
    from app.evolution.anatomy import planned_parts

    s = await eng.plan_session("red fox", "barn owl", "speculative")
    parts = {p["part"]: p["parent"] for p in planned_parts(s.plan, eng.tax)}
    assert parts["wings (in place of the forelegs)"] == "barn_owl" and parts["hind legs"] == "red_fox"
    h = await eng.plan_session("donkey", "horse", "realistic")
    hp = {p["part"]: p["parent"] for p in planned_parts(h.plan, eng.tax)}
    assert hp["head"] == "donkey" and hp["body"] == "horse" and hp["tail"] == "blend"


# ------------------------------------------------------------------ part 3: the fixed benchmark and its scores


FROZEN = "c36c202e5402ffa7c295153d8e1378a1c6d8072054a097ec7cbcb9433e42559f"


def test_the_benchmark_has_the_11_cases_and_never_changes():
    import hashlib

    from app.evolution.benchmark import BENCHMARK, cases

    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    assert hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest() == FROZEN
    assert [(c["sire"], c["dam"], c["mode"]) for c in cases()] == [
        ("axolotl", "Chinese pangolin", "realistic"), ("rhinoceros beetle", "brown bear", "speculative"),
        ("lion", "golden eagle", "mythic"), ("lion", "golden eagle", "realistic"), ("donkey", "horse", "realistic"),
        ("common octopus", "horse", "realistic"), ("emperor penguin", "cheetah", "realistic"),
        ("red fox", "barn owl", "speculative"), ("Indian pangolin", "horse", "realistic"),
        ("tortoise", "domestic goat", "realistic"), ("crab", "gray wolf", "speculative")]
    assert data["caps"] == {"max_renders": 4, "max_tool_calls": 30, "max_edits": 6}


def test_names_parent_matches_the_name_or_its_last_word_only():
    from app.evolution.benchmark import names_parent

    assert names_parent("Chinese pangolin", ["pangolin", "axolotl"])
    assert names_parent("red fox", ["Foxes"]) and names_parent("barn owl", "a barn owl")
    assert not names_parent("horse", ["seahorse", "zebra"]) and not names_parent("barn owl", ["bird"])
    assert not names_parent("gray wolf", None)


def _save(folder: Path, inspect: dict[str, Any], **meta: Any) -> None:
    folder.mkdir(parents=True)
    (folder / "inspect_final.json").write_text(json.dumps(inspect), encoding="utf-8")
    (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_scores_are_computed_from_the_saved_results(tmp_path, monkeypatch):
    from app.evolution import benchmark as B

    monkeypatch.setattr(B, "cases", lambda: [{"id": "b11", "sire": "crab", "dam": "gray wolf", "mode": "speculative"}])
    rows = [{"key": "on_top", "group": "integration", "status": "fail"},
            {"key": "abrupt_stop", "group": "coverage", "status": "fail"},
            {"key": "third_animal", "group": "structure", "status": "uncertain"},
            {"key": "identity_claws", "group": "identity", "status": "fail"}]
    descs = {"meta_spark": {"animals": ["wolf", "lobster"]}, "spark_open": {"animals": ["crab", "wolf"]}}
    _save(tmp_path / "b11" / "agent", {"failures": rows, "items": rows + [
        {"key": "origin_claws", "group": "identity", "status": "fail", "expect": "crab", "answers": {"meta_spark": "lobster"}}],
        "descriptions": descs}, case="b11", kind="agent", wall_seconds=300, renders=3, edits=1, tool_calls=21,
        calls_by_provider={"baseten": {"evo_agent": 20, "evo_ask": 4}, "meta": {"text_to_image": 4}})
    _save(tmp_path / "b11" / "fixed", {"failures": [], "items": [], "descriptions": {
        "meta_spark": {"animals": ["gray wolf", "crab"]}}}, case="b11", kind="fixed", wall_seconds=100, renders=1,
        edits=0, tool_calls=None, calls_by_provider={"baseten": {"evo_ask": 2}, "meta": {"text_to_image": 1}})
    out = B.score_all(tmp_path)
    a, f = out["cases"]["b11"]["agent"], out["cases"]["b11"]["fixed"]
    assert a["full_match"] is False and a["failures"] == {"total": 4, "structure": 1, "identity": 1, "integration": 2}
    assert a["identity"]["sire"]["named"] is False and a["identity"]["sire"]["named_by_spark_open"] is True
    assert a["identity"]["dam"]["named"] is True and a["both_parents_named"] is False
    assert a["donor_part_origin"][0]["answers"] == {"meta_spark": "lobster"}
    assert a["calls_by_provider"] == {"baseten": 24, "meta": 4} and a["calls_total"] == 28
    assert f["full_match"] and f["both_parents_named"]
    t = out["totals"]
    assert (t["agent"]["full_matches"], t["fixed"]["full_matches"]) == (0, 1)
    assert t["agent"]["avg_tool_calls"] == 21 and t["fixed"]["avg_tool_calls"] is None
