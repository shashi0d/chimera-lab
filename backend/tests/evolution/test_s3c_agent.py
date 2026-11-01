"""S3c (mock mode): plan fixes from the S3b images (part 1: owner decisions D1 to D4, fiction clauses from the donor's
traits, plate layout from the donor, coverings keep the host's outline, RC-R10-17) and the agent core (part 2: the
tool loop, guardrails, caps and the trace)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.errors import ChimeraError
from app.evolution import agent as A
from app.evolution.critic import questions
from app.evolution.data import Animal, cards, config
from app.evolution.engine import EvoEngine
from app.evolution.fiction import trait_compensation
from app.evolution.identity import candidates, validate_pick
from app.evolution.parts import class_entry
from app.evolution.prompt import compile_prompt
from app.evolution.route import host_tie, route
from app.evolution.transfer import plate_pattern
from app.services import build_services
from tests.conftest import make_settings

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def eng(tmp_path: Path) -> EvoEngine:
    store = tmp_path / "learned.json"
    shutil.copy(REPO / "data" / "learned_animals.json", store)
    return EvoEngine(build_services(make_settings(tmp_path, evo_learned_path=str(store))))


async def _session(eng: EvoEngine, a: str, b: str, mode: str = "speculative", host: str | None = None):
    s = await eng.plan_session(a, b, mode)
    if host:
        assert s.apply("set_host", {"animal": host}).ok
    return s


def _cov(g):
    return next(t for t in g.transfers if t.kind == "covering")


# ------------------------------------------------------------------ part 1 (a): fiction clauses from the donor


async def test_a_crab_gets_no_flank_openings(eng):
    s = await _session(eng, "crab", "gray wolf")
    lic = s.plan.licenses[0]
    assert lic.id == "arthropod_large" and lic.compensation == "thick supporting legs"
    assert "breathes with gills" in lic.reason and "model-estimated" in lic.reason
    assert "breathing openings" not in compile_prompt(s.plan, eng.tax)


async def test_a_beetle_shows_spiracles_from_its_own_breathing_trait(eng):
    s = await _session(eng, "rhinoceros beetle", "brown bear")
    comp, why = trait_compensation("arthropod_large", s.plan, eng.tax)
    assert "spiracles" in comp and "tracheae" in why
    assert "spiracles" in compile_prompt(s.plan, eng.tax)


async def test_an_agent_compensation_cannot_add_openings_a_crab_lacks(eng):
    s = await _session(eng, "crab", "gray wolf")
    res = s.apply("add_license", {"rule": "arthropod_large", "compensation": "thick legs and breathing openings"})
    assert not res.ok and res.errors[0].code == "not_a_donor_trait"
    assert s.apply("add_license", {"rule": "arthropod_large", "compensation": "thick, short supporting legs"}).ok


# ------------------------------------------------------------------ part 1 (b, d): identity parts and the outline


async def test_crab_identity_is_its_claws_and_the_class_tail_is_dropped(eng):
    s = await _session(eng, "crab", "gray wolf")
    g = s.plan
    [ip] = g.identity_parts
    assert (ip.part, ip.donor, ip.set_by) == ("claws", "crab", "code")
    assert "claws" in ip.feature and ip.source == "model-estimated"
    assert g.traits["tail"].donor == "gray_wolf" and g.traits["tail"].part is None
    assert "in place of the tail" not in g.silhouette
    assert any(c.step == "identity" and "segmented tail" in c.detail for c in g.checks)
    p = compile_prompt(g, eng.tax)
    assert "the tail stays the gray wolf's own tail" in p and "every covered part keeps the gray wolf's own" in p
    assert "pincer" in p and "segmented tail" not in p


async def test_identity_part_must_be_a_part_the_donor_has_in_that_form(eng):
    s = await _session(eng, "crab", "gray wolf")
    bad = s.apply("set_identity_part", {"donor": "crab", "part": "segmented tail", "reason": "looks crabby"})
    assert not bad.ok and bad.errors[0].code == "not_a_donor_part" and "claws" in (bad.errors[0].valid or [])
    assert not s.apply("set_identity_part", {"donor": "crab", "part": "claws", "reason": ""}).ok  # a reason is needed
    ok = s.apply("set_identity_part", {"donor": "crab", "part": "claws", "reason": "the claws say crab"})
    assert ok.ok and s.plan.identity_parts[0].set_by == "agent"


async def test_identity_candidates_skip_coverings_back_shapes_and_walking_legs(eng):
    beetle = (await eng.resolve("rhinoceros beetle")).animal
    parts = [c.part for c in candidates(beetle)]
    assert parts[0] == "head horn" and "elytra" not in parts and "jointed legs" not in parts
    assert candidates(beetle)[0].feature == "long curved head horn"  # "in males" is dropped from the form
    crab = (await eng.resolve("crab")).animal
    assert "carapace" not in [c.part for c in candidates(crab)]
    with pytest.raises(ValueError):
        validate_pick(crab, "segmented tail")


async def test_one_identity_part_per_donor_drops_insect_wings_too(eng):
    s = await _session(eng, "rhinoceros beetle", "brown bear")
    g = s.plan
    assert [p.part for p in g.identity_parts] == ["head horn"]
    assert [t.feature for t in g.transfers if t.kind == "part"] == ["head horn"]
    assert not g.limb_plan.has_wings()


async def test_realistic_mode_shows_the_donor_by_material_only(eng):
    s = await _session(eng, "crab", "gray wolf", "realistic")
    g = s.plan
    assert g.identity_parts == [] and [t.kind for t in g.transfers] == ["covering"]
    assert g.traits["tail"].part is None


async def test_a_vertebrate_donor_declares_its_identity_part_without_dropping(eng):
    s = await _session(eng, "axolotl", "chinese pangolin", host="chinese pangolin")
    assert [p.part for p in s.plan.identity_parts] == ["external gills"]  # owner decision D3
    assert any(t.feature == "external gills" for t in s.plan.transfers)


async def test_code_never_refills_a_slot_the_agent_cleared(eng):
    s = await _session(eng, "tiger", "octopus")
    assert s.apply("set_region", {"region": "tail", "donor": "tiger", "operator": "PICK"}).ok
    assert not any("tentacle" in p for p in s.summary()["parts"])


async def test_the_critic_asks_whether_the_identity_part_came_from_the_donor(eng):
    s = await _session(eng, "crab", "gray wolf")
    qs = [q for q in questions(s.plan, eng.tax) if q.group == "identity"]
    assert [q.text for q in qs] == ["Do the claws look like they came from a crab?"] and qs[0].expect == "yes"
    assert "claws" in s.summary()["checklist_preview"][0] or qs[0].fix.startswith("Show the claws")


async def test_card_lists_the_identity_part_with_its_source(eng):
    from app.evolution.card import output_card

    s = await _session(eng, "crab", "gray wolf")
    card = output_card(s.plan, s.route, eng.tax)
    assert card["identity_parts"][0]["part"] == "claws" and card["identity_parts"][0]["source"] == "model-estimated"


# ------------------------------------------------------------------ part 1 (c): plate layout from the donor


async def test_plate_layout_comes_from_the_donors_own_features(eng):
    beetle = await _session(eng, "rhinoceros beetle", "brown bear")
    crab = await _session(eng, "crab", "gray wolf")
    pang = await _session(eng, "axolotl", "chinese pangolin")
    b, c, p = _cov(beetle.plan), _cov(crab.plan), _cov(pang.plan)
    assert b.plate_pattern.startswith("a few large fused plates") and "wing cases" in b.plate_pattern
    assert c.plate_pattern.startswith("one broad carapace shield") and "carapace" in c.plate_pattern
    assert p.plate_pattern.startswith("many overlapping scales")
    assert {b.plate_source, c.plate_source, p.plate_source} == {"model-estimated"}
    pb = compile_prompt(beetle.plan, eng.tax)
    assert "a few large, smooth, fused plates" in pb and "one plate per segment" not in pb
    assert "pie-crust frilled edge" in compile_prompt(crab.plan, eng.tax)
    assert not any(x.plate_pattern.startswith("repeated transverse bands") for x in (b, c, p))


def test_bands_only_when_the_donor_has_them_and_a_class_default_is_marked():
    def animal(features: tuple[str, ...]) -> Animal:
        return Animal(id="x", common_name="test isopod", scientific_name="Testus isopodus", tax_class="Malacostraca",
                      family="", body_plan="multi_legged", covering="exoskeleton", mass_kg=0.01, habitats=(),
                      climate=(), active_time=(), group="arthropod", features=features,
                      provenance=(("visible_features", "model-estimated"),))

    pat, feat, src = plate_pattern(animal(("grey body of overlapping armored bands",)))
    assert pat["id"] == "bands" and pat["banded"] and "bands" in feat
    pat, feat, src = plate_pattern(animal(()))
    assert pat["id"] == "carapace" and feat == "" and src.startswith("model-estimated (transfer_rules.json class default")


# ------------------------------------------------------------------ part 1 (e): RC-R10-17, GBIF reptile classes


def test_rc_r10_17_is_loaded():
    c = cards()["RC-R10-17"]
    assert c.status == "VERIFIED" and c.strength == "soft" and "skeleton" in c.rule
    assert "ideas.repec.org" in c.source


async def test_a_turtle_host_keeps_its_shell(eng):
    s = await _session(eng, "tortoise", "domestic goat", "realistic", host="tortoise")
    cov = _cov(s.plan)
    assert set(cov.extent) <= {"head", "neck", "legs", "tail"} and cov.host_shell
    assert "RC-R10-17" in cov.extent_reason and "RC-R10-17" in s.plan.card_trace
    p = compile_prompt(s.plan, eng.tax)
    assert "shell keeps its own form and bony plates" in p and "replaces the tortoise's scaly skin" in p
    assert "replaces the tortoise's hard shell plates" not in p
    bad = s.apply("set_extent", {"feature": "covering", "extent": ["back", "legs"], "reason": "warm fur on the back"})
    assert not bad.ok and bad.errors[0].code == "shell_is_skeleton"


async def test_gbif_testudines_reads_as_a_reptile(eng):
    t = (await eng.resolve("tortoise")).animal
    assert t.tax_class == "Testudines" and t.group == "vertebrate" and class_entry(t) is not None


# ------------------------------------------------------------------ owner decisions D1 to D3


def test_d1_meta_decides_and_spark_open_is_information():
    assert config()["critic_decision"] == {"mode": "primary", "primary": "meta_spark"}


async def test_d2_a_structural_tie_has_no_rule(eng):
    lion, eagle = eng.tax.animals["lion"], eng.tax.animals["golden_eagle"]
    assert host_tie(route(lion, eagle, eng.tax)) == ["lion", "golden_eagle"]
    with pytest.raises(ChimeraError) as e:
        await eng.fuse(sire_name="lion", dam_name="eagle")
    assert e.value.details["needs_choice"] == "host" and len(e.value.details["options"]) == 2
    doc = await eng.fuse(sire_name="lion", dam_name="eagle", host="dam")
    assert doc["genome"]["host"] == "golden_eagle"


def test_d3_the_axolotl_gold_label_follows_the_owner_decision():
    for name in ("gold_set.json", "gold_set_s3b.json"):
        d = json.loads((REPO / "docs/evolution/benchmark" / name).read_text(encoding="utf-8"))
        item = next(i for i in d["items"] if i["id"] == "e4/b_axolotl_x_pangolin")
        assert item["label"] == "good" and "owner decision S3c" in item["note"]


# ------------------------------------------------------------------ part 2: the agent loop


def scripted(steps: list[Any]) -> A.PolicyBrain:
    """A brain from a list of (tool, args) or callables(run) -> (tool, args). Exhausted: no more tool calls."""
    it = iter(steps)

    def policy(run: A.AgentRun) -> tuple[str, dict[str, Any]] | None:
        nxt = next(it, None)
        return nxt(run) if callable(nxt) else nxt

    return A.PolicyBrain(policy)


def last_image(run: A.AgentRun) -> str:
    return run.state.order[-1]


def fake_inspect(fails: list[dict[str, Any]]):
    async def _inspect(image: bytes, g: Any, r: Any, verdict: dict[str, Any]) -> dict[str, Any]:
        rows = [{"status": "fail", "fix": f"fix {f['key']}", "text": f["key"], "answers": {}, **f} for f in fails]
        return {"failures": rows, "items": rows, "structural_failures": len(rows), "descriptions": {
            "meta_spark": {"heads": 1, "walking_legs": 4, "tails": 1}}, "expected_counts": {}, "third_animals": {}}
    return _inspect


async def test_the_default_agent_builds_a_creature_with_a_reason_on_every_step(eng):
    doc, run = await eng.agent_fuse("rhinoceros beetle", "brown bear", "speculative")
    tools = [s["tool"] for s in run.trace]
    assert tools[:6] == ["resolve_animal", "resolve_animal", "propose_candidates", "choose_candidate", "audit_plan",
                         "render"]
    assert tools[-1] == "finalize" and all(s["reason"] for s in run.trace)
    assert doc["genome"]["host"] == "brown_bear" and doc["card"]["agent"]["renders"] == 1
    assert doc["card"]["remaining_failures"] == [] and doc["providers"]
    md = run.trace_md()
    assert "## 3. propose_candidates" in md and "- reason:" in md and "- cards:" in md


async def test_a_tie_gives_both_hosts_and_blocks_render_until_chosen(eng):
    run = A.AgentRun(eng, "lion", "eagle", brain=scripted([]))
    await run.call("resolve_animal", {"name": "lion", "reason": "sire"})
    await run.call("resolve_animal", {"name": "eagle", "reason": "dam"})
    out = await run.call("propose_candidates", {"reason": "see options"})
    assert out["host_tie"] == ["lion", "golden eagle"]
    assert {c["host"] for c in out["candidates"]} == {"lion", "golden eagle"}
    assert all("structural tie" in c["notes"]["host"] for c in out["candidates"])
    run.session = run._new_session()  # a plan whose tie is not chosen
    audit = await run.call("audit_plan", {"reason": "check"})
    assert not audit["renderable"] and any(b["card"] == "RC-R10-01" for b in audit["blocking"])
    refused = await run.call("render", {"method": "single_pass", "reason": "try"})
    assert refused["error"] == "not_audited"
    assert (await run.call("plan_op", {"op": "set_host", "args": {"animal": "eagle"}, "reason": "the bird frame "
                                       "carries flight"}))["ok"]
    assert (await run.call("audit_plan", {"reason": "again"}))["renderable"]


async def test_a_plan_change_needs_a_new_audit_before_render(eng):
    run = A.AgentRun(eng, "crab", "gray wolf", brain=scripted([]))
    for name in ("crab", "gray wolf"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    assert (await run.call("audit_plan", {"reason": "check"}))["renderable"]
    assert (await run.call("plan_op", {"op": "set_habitat", "args": {"name": "rocky coast"}, "reason": "coast"}))["ok"]
    assert (await run.call("render", {"method": "single_pass", "reason": "go"}))["error"] == "not_audited"
    await run.call("audit_plan", {"reason": "re-audit"})
    assert (await run.call("render", {"method": "single_pass", "reason": "go"}))["ok"]


async def test_every_call_needs_a_reason_and_finalize_needs_an_inspected_image(eng):
    run = A.AgentRun(eng, "crab", "gray wolf", brain=scripted([]))
    assert (await run.call("resolve_animal", {"name": "crab"}))["error"] == "missing_reason"
    assert (await run.call("fly", {"reason": "x"}))["error"] == "unknown_tool"
    for name in ("crab", "gray wolf"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    await run.call("audit_plan", {"reason": "check"})
    img = (await run.call("render", {"method": "single_pass", "reason": "go"}))["image_id"]
    assert (await run.call("finalize", {"image_id": img, "reason": "done"}))["error"] == "not_inspected"


async def test_edit_fixes_covering_failures_only_and_inspect_checks_drift(eng, monkeypatch):
    monkeypatch.setattr(eng, "_inspect", fake_inspect([{"key": "follows_body", "group": "integration"},
                                                      {"key": "heads", "group": "structure"}]))
    run = A.AgentRun(eng, "rhinoceros beetle", "brown bear", brain=scripted([]))
    for name in ("rhinoceros beetle", "brown bear"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    await run.call("audit_plan", {"reason": "check"})
    img = (await run.call("render", {"method": "single_pass", "reason": "go"}))["image_id"]
    out = await run.call("inspect", {"image_id": img, "reason": "check"})
    kinds = {f["key"]: f["kind"] for f in out["failures"]}
    assert kinds == {"follows_body": "covering", "heads": "structural"}
    bad = await run.call("edit", {"image_id": img, "failure_keys": ["heads", "follows_body"], "reason": "fix both"})
    assert bad["error"] == "structural_failure" and bad["valid"] == ["follows_body"]
    ok = await run.call("edit", {"image_id": img, "failure_keys": ["follows_body"], "reason": "grow it in"})
    assert ok["ok"] and ok["instruction"] == "fix follows_body"
    after = await run.call("inspect", {"image_id": ok["image_id"], "reason": "check the edit"})
    assert after["drift"] == {"drifted": False, "changed": [], "by_critic": {"meta_spark": []}}


async def test_the_render_cap_and_code_finalize_with_remaining_failures(eng, monkeypatch):
    monkeypatch.setattr(eng, "_inspect", fake_inspect([{"key": "third_animal", "group": "structure"}]))

    def policy(run: A.AgentRun):
        s = run.state
        if len(s.resolved) < 2:
            return "resolve_animal", {"name": ["crab", "gray wolf"][len(s.resolved)], "reason": "parent"}
        if s.candidates is None:
            return "propose_candidates", {"reason": "options"}
        if s.chosen is None:
            return "choose_candidate", {"candidate_id": "C1", "reason": "top"}
        if s.audited is None:
            return "audit_plan", {"reason": "check"}
        if s.order and s.images[s.order[-1]].inspect is None:
            return "inspect", {"image_id": s.order[-1], "reason": "check"}
        return "render", {"method": "single_pass", "reason": "try again"}

    doc, run = await eng.agent_fuse("crab", "gray wolf", brain=A.PolicyBrain(policy))
    assert run.state.renders == A.settings()["max_renders"] == 4
    refused = [s for s in run.trace if s["tool"] == "render" and not s["ok"]]
    assert refused and refused[0]["result"]["error"] == "render_cap"
    assert run.state.calls == A.settings()["max_tool_calls"] and "tool-call cap" in run.state.stop
    assert doc["card"]["remaining_failures"] == [{"key": "third_animal", "kind": "structural", "text": "third_animal"}]
    assert run.trace[-1]["tool"] == "finalize" and run.trace[-1]["reason"].startswith("code:")


async def test_growth_edit_renders_the_host_first_and_grows_the_covering(eng):
    run = A.AgentRun(eng, "rhinoceros beetle", "brown bear", brain=scripted([]))
    for name in ("rhinoceros beetle", "brown bear"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    await run.call("audit_plan", {"reason": "check"})
    out = await run.call("render", {"method": "growth_edit", "reason": "grow the covering in"})
    host, grown = run.state.images[out["host_image_id"]], run.state.images[out["image_id"]]
    assert (host.kind, grown.kind, grown.parent) == ("growth_host", "growth", host.id)
    assert "Now grow the covering" in grown.prompt and run.state.renders == 1 and run.state.edits == 1
    insp = await run.call("inspect", {"image_id": grown.id, "reason": "check"})
    assert insp["drift"] is not None


async def test_ask_user_only_in_interactive_runs(eng):
    run = A.AgentRun(eng, "lion", "eagle", brain=scripted([]))
    out = await run.call("ask_user", {"question": "Which host?", "options": ["lion", "eagle"], "reason": "tie"})
    assert out["answer"] is None and "not an interactive run" in out["note"]

    async def ask(q: str, opts: list[str]) -> str:
        return opts[1]

    run2 = A.AgentRun(eng, "lion", "eagle", brain=scripted([]), ask=ask)
    assert (await run2.call("ask_user", {"question": "Which host?", "options": ["lion", "eagle"],
                                         "reason": "tie"}))["answer"] == "eagle"
    assert "call ask_user" in run2.system_prompt() and "not interactive" in run.system_prompt()


async def test_spark_open_brain_sends_tools_with_an_output_cap_and_parses_calls():
    sent: dict[str, Any] = {}

    class FakeBaseten:
        model_id = "meta-models/muse-spark-open-1026"

        async def chat(self, purpose: str, body: dict[str, Any]) -> dict[str, Any]:
            sent.update(purpose=purpose, body=body)
            return {"choices": [{"finish_reason": "tool_calls", "message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "resolve_animal",
                                                              "arguments": '{"name": "crab", "reason": "sire"}'}},
                {"id": "c2", "type": "function", "function": {"name": "audit_plan", "arguments": "{oops"}}]}}]}

    brain = A.SparkOpenBrain(FakeBaseten(), 8000)
    turn = await brain.next([{"role": "user", "content": "go"}], A.TOOLS)
    assert sent["purpose"] == "evo_agent" and sent["body"]["max_tokens"] == 8000
    assert sent["body"]["tools"] == A.TOOLS and sent["body"]["tool_choice"] == "auto"
    assert turn.calls[0] == {"id": "c1", "name": "resolve_animal", "arguments": {"name": "crab", "reason": "sire"}}
    assert "_unparsed" in turn.calls[1]["arguments"]


def test_every_tool_requires_a_reason_and_the_cap_is_configured():
    for t in A.TOOLS:
        assert "reason" in t["function"]["parameters"]["required"]
    cfg = A.settings()
    assert (cfg["max_renders"], cfg["max_tool_calls"], cfg["reference_portraits"]) == (4, 30, False)
    assert config()["routing"]["agent"]["max_tokens"] == cfg["max_tokens"]


async def test_a_brain_that_stops_calling_tools_is_finalized_by_code(eng):
    steps = [("resolve_animal", {"name": "crab", "reason": "sire"}),
             ("resolve_animal", {"name": "gray wolf", "reason": "dam"}),
             ("propose_candidates", {"reason": "options"}),
             ("choose_candidate", {"candidate_id": "C1", "reason": "top"}),
             ("audit_plan", {"reason": "check"}),
             ("render", {"method": "single_pass", "reason": "go"})]
    doc, run = await eng.agent_fuse("crab", "gray wolf", brain=scripted(steps))
    assert run.state.stop == "the agent stopped calling tools"
    assert doc["genome"]["host"] == "gray_wolf" and any(s["tool"] == "inspect" for s in run.trace)
    assert doc["card"]["agent"]["stop"].startswith("finalized by code")


async def test_a_plan_op_that_changes_nothing_says_so_and_keeps_the_audit(eng):
    run = A.AgentRun(eng, "rhinoceros beetle", "brown bear", brain=scripted([]))
    for name in ("rhinoceros beetle", "brown bear"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    await run.call("audit_plan", {"reason": "check"})
    out = await run.call("plan_op", {"op": "connect_features", "args": {"a": "head horn", "b": "covering"},
                                     "reason": "connect the horn"})
    assert out["ok"] and out["changed"] is False and "unchanged" in out["note"]
    assert (await run.call("render", {"method": "single_pass", "reason": "still audited"}))["ok"]


# ------------------------------------------------------------------ S3c finish: memory, the two-failure rule


def _has_image_data(obj: Any) -> bool:
    if isinstance(obj, (bytes, bytearray)):
        return True
    text = json.dumps(obj, default=lambda o: f"<{type(o).__name__}>")
    return "data:image/" in text or "UklGR" in text or "iVBORw0K" in text  # data URLs, base64 webp or png


async def test_the_agent_history_never_holds_image_data(eng, tmp_path):
    seen: list[list[dict[str, Any]]] = []

    class Watching(A.PolicyBrain):
        async def next(self, messages, tools):
            seen.append(json.loads(json.dumps(messages)))
            return await super().next(messages, tools)

    def policy(run: A.AgentRun):
        s = run.state
        if s.renders == 0 or (s.renders < 2 and s.images[s.order[-1]].inspect is not None):
            return A.default_policy(run) if s.renders == 0 else ("render", {"method": "growth_edit", "reason": "grow"})
        return A.default_policy(run)

    doc, run = await eng.agent_fuse("rhinoceros beetle", "brown bear", brain=Watching(policy),
                                    image_dir=tmp_path / "imgs")
    assert len(run.state.order) >= 3 and seen
    for im in run.state.images.values():
        assert not hasattr(im, "data") and im.path.parent == tmp_path / "imgs" and im.path.stat().st_size == im.size
        assert not any(isinstance(v, (bytes, bytearray)) for v in vars(im).values())
    assert not any(_has_image_data(m) for m in seen) and not _has_image_data(run.messages)
    assert not _has_image_data(run.trace) and not _has_image_data(doc)


async def test_two_covering_failures_in_a_row_stop_edits_until_the_plan_changes(eng, monkeypatch):
    monkeypatch.setattr(eng, "_inspect", fake_inspect([{"key": "on_top", "group": "integration"}]))
    run = A.AgentRun(eng, "rhinoceros beetle", "brown bear", brain=scripted([]))
    assert "Two-failure rule" in run.system_prompt() and "set_extent" in run.system_prompt()
    for name in ("rhinoceros beetle", "brown bear"):
        await run.call("resolve_animal", {"name": name, "reason": "parent"})
    await run.call("propose_candidates", {"reason": "options"})
    await run.call("choose_candidate", {"candidate_id": "C1", "reason": "top"})
    await run.call("audit_plan", {"reason": "check"})
    img = (await run.call("render", {"method": "single_pass", "reason": "go"}))["image_id"]
    first = await run.call("inspect", {"image_id": img, "reason": "check"})
    assert "rule" not in first
    e1 = (await run.call("edit", {"image_id": img, "failure_keys": ["on_top"], "reason": "grow it in"}))["image_id"]
    second = await run.call("inspect", {"image_id": e1, "reason": "check the edit"})
    assert "two-failure rule" in second["rule"] and "[two-failure rule" in run.trace[-1]["summary"]
    refused = await run.call("edit", {"image_id": e1, "failure_keys": ["on_top"], "reason": "once more"})
    assert refused["error"] == "two_failure_rule" and "set_extent" in refused["hint"]
    # an operation that changes nothing keeps the lock
    zones = run.session.plan.transfers[[t.kind for t in run.session.plan.transfers].index("covering")].extent
    same = await run.call("plan_op", {"op": "connect_features", "args": {"a": "head horn", "b": "covering"},
                                      "reason": "no change"})
    assert same["ok"] and same["changed"] is False
    assert (await run.call("edit", {"image_id": e1, "failure_keys": ["on_top"], "reason": "x"}))["error"] == \
        "two_failure_rule"
    smaller = [z for z in zones if z in ("back", "flanks", "neck", "shoulders", "hips")] or zones[:2]
    out = await run.call("plan_op", {"op": "set_extent", "args": {"feature": "covering", "extent": smaller,
                                                                   "reason": "plates on the back only, where they "
                                                                             "protect the spine; legs stay fur"},
                                     "reason": "two-failure rule: reduce the covering"})
    assert out["ok"] and out["changed"], out
    assert (await run.call("audit_plan", {"reason": "re-audit"}))["renderable"]
    img2 = (await run.call("render", {"method": "single_pass", "reason": "render the smaller covering"}))["image_id"]
    assert "rule" not in await run.call("inspect", {"image_id": img2, "reason": "check"})
    assert (await run.call("edit", {"image_id": img2, "failure_keys": ["on_top"], "reason": "one edit"}))["ok"]
