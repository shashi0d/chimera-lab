"""S3c part 2: the agent core (ROADMAP step 3, section 4).

Muse Spark Open on Baseten runs a tool loop over the engine. The agent decides; code is its tools and guardrails:

    resolve_animal(name)                 database, learned cache, GBIF, cited traits
    propose_candidates()                 ranked plan arrangements with R10 selection notes (niche, autonomy,
                                         survival, identity); advice only, it decides nothing
    choose_candidate(candidate_id)       adopt one candidate (its typed operations are replayed)
    plan_op(op, args)                    one typed plan operation (ops.PlanSession); the agent never writes a plan
    audit_plan()                         hard cards block render; soft cards and the R9 audit come back as advice
    render(method)                       Muse Image: single pass, or growth by edit for a covering (S3b)
    inspect(image_id)                    the plan-blind critics (Meta decides, Spark Open logged, D-084) plus SAM
    edit(image_id, failure_keys)         one Muse Image edit turn for covering or surface failures, plan-worded
    ask_user(question, options)          interactive runs only
    finalize(image_id)                   the card, with any remaining failures stated

Every call carries a `reason`. Guardrails in code: a plan must be audited (and have no blocking item) before it is
rendered; a structural host tie must be chosen (D-085); an edit fixes only covering or surface failures (structural
ones need a plan change and a new render); an edit is checked for host drift from the critics' own counts. Runaway
caps (evo_config `agent`): 4 renders and 30 tool calls per creature. At a cap, or when the agent stops without
finalizing, code finalizes the best inspected image and states its remaining failures on the card.

Every step is logged (tool, arguments, result summary, reason, cards cited) to `trace` (trace.json, trace.md).
Reference portraits stay off (ROADMAP 5b). In mock mode a policy brain drives the same loop.
"""

from __future__ import annotations

import json
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.errors import ChimeraError
from app.evolution.adapters import swatch
from app.evolution.audit import DROPPED
from app.evolution.card import output_card
from app.evolution.checks import soft_penalties
from app.evolution.data import Animal, config, norm
from app.evolution.growth import DRIFT_KEYS, has_covering, host_first, planned_counts
from app.evolution.growth import instruction as growth_instruction
from app.evolution.identity import candidates as identity_candidates
from app.evolution.identity import needs_identity
from app.evolution.inspect import edit_instruction
from app.evolution.judge import judge
from app.evolution.ops import OPS, PlanSession
from app.evolution.prompt import accept_polish, compile_prompt
from app.evolution.route import host_tie
from app.models.schemas import ErrorCode

COVERING_GROUPS = ("integration", "coverage", "placement", "pattern", "surface")  # an edit may fix these
RESULT_CHARS = 3500  # a tool result shown to the agent is cut here (the full result is in the trace)


def settings() -> dict[str, Any]:
    return {"max_renders": 4, "max_tool_calls": 30, "max_edits": 6, "max_tokens": 8000, "max_nudges": 3,
            "reference_portraits": False, **(config().get("agent") or {})}


def failure_kind(row: dict[str, Any]) -> str:
    """covering: a covering or surface item (an edit may fix it); structural: counts, frame, extra or missing parts,
    part identity and connection, a third animal (a plan change and a new render)."""
    return "covering" if row.get("group") in COVERING_GROUPS else "structural"


# ------------------------------------------------------------------ tool schemas


def _fn(name: str, desc: str, props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    props = {**props, "reason": {"type": "string", "description": "Why you make this call (one or two sentences; "
                                                                    "cite rule cards such as RC-R10-15 when they apply)."}}
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props, "required": [*required, "reason"], "additionalProperties": False}}}


OP_HELP = ("Typed plan operations (args): set_host(animal); set_region(region, donor, operator) with regions head, "
           "tail, forelimbs (PICK) or neck, forequarters, back, flanks, belly, hindquarters, legs (PATCH, OVERLAY, "
           "PICK); set_habitat(name); set_mode(mode); add_license(rule, compensation); drop_part(part, reason); "
           "set_transfer_class(feature, cls); set_extent(feature, extent, reason); connect_features(a, b); "
           "set_identity_cues(feature, cues); set_identity_part(donor, part, reason). A failed operation changes "
           "nothing and returns errors with valid values.")

TOOLS = [
    _fn("resolve_animal", "Resolve one parent name to an animal with sourced traits.",
        {"name": {"type": "string"}}, ["name"]),
    _fn("propose_candidates", "Ranked plan arrangements for the two resolved parents, each with R10 selection notes "
        "(niche, autonomy, survival, identity) and its reasons. Advice only.", {}, []),
    _fn("choose_candidate", "Adopt one candidate plan by id.", {"candidate_id": {"type": "string"}}, ["candidate_id"]),
    _fn("plan_op", "Change the current plan with one typed operation. " + OP_HELP,
        {"op": {"type": "string", "enum": list(OPS)}, "args": {"type": "object"}}, ["op", "args"]),
    _fn("audit_plan", "Audit the current plan: blocking items (hard cards, an unchosen host tie) and advice (soft "
        "cards, the function audit, the fiction budget). Required before render.", {}, []),
    _fn("render", "Render the audited plan. method single_pass (default) or growth_edit (host first, then one edit "
        "grows the covering; only for a plan with a donor covering).",
        {"method": {"type": "string", "enum": ["single_pass", "growth_edit"]}}, ["method"]),
    _fn("inspect", "Inspect an image with the plan-blind critics. Returns pass or the failures, each with a key and "
        "kind (covering or structural).", {"image_id": {"type": "string"}}, ["image_id"]),
    _fn("edit", "One image edit turn fixing covering or surface failures of an image (keys from inspect). Structural "
        "failures need a plan change and a new render instead.",
        {"image_id": {"type": "string"}, "failure_keys": {"type": "array", "items": {"type": "string"}}},
        ["image_id", "failure_keys"]),
    _fn("ask_user", "Ask the user to choose (interactive runs only).",
        {"question": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}},
        ["question", "options"]),
    _fn("finalize", "Finish with this image. Any failures it still has are stated on the card.",
        {"image_id": {"type": "string"}}, ["image_id"]),
]
TOOL_NAMES = [t["function"]["name"] for t in TOOLS]

SYSTEM = """You are the design agent of Chimera Lab, a natural-history creature engine. You build one creature from \
two parent animals by calling tools; code tools do the work and check every step.

Rules:
1. You never write a plan. Pick a candidate from propose_candidates with choose_candidate, and change it only with \
plan_op (typed operations). Code fills every derived field.
2. Every call has a reason: what you decided and why, citing the rule cards the tools return when they apply.
3. Order: resolve_animal for each parent, propose_candidates, choose_candidate, audit_plan, render, inspect.
4. audit_plan: blocking items stop render until fixed; advice is yours to weigh.
5. After inspect: if it passes, call finalize with that image. If it fails, choose and say why:
   - covering or surface failures (kind "covering"): edit that image with those failure keys;
   - structural failures (kind "structural": counts, extra or missing parts, the frame, part identity or \
connection, a third animal): change the plan with plan_op or choose another candidate, audit, and render again;
   - or accept the failures and finalize, saying why.
   An edit or a new render can make things worse: compare with images_so_far from inspect, and finalize the best image, not just the latest.
6. A host tie: choose the host yourself from the candidates' notes, with a reason{ask}.
7. Limits: at most {renders} renders and {calls} tool calls. Near a limit, finalize your best inspected image; \
its remaining failures go on the card.
Keep reasons short. Call one tool at a time."""


# ------------------------------------------------------------------ brains


@dataclass
class Turn:
    """One brain answer: tool calls [{id, name, arguments}] and any text it wrote."""
    calls: list[dict[str, Any]]
    text: str = ""
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None


class SparkOpenBrain:
    """Muse Spark Open on Baseten (OpenAI-compatible tool calling), with an output cap on every call."""

    def __init__(self, baseten: Any, max_tokens: int) -> None:
        self.baseten, self.max_tokens = baseten, max_tokens
        self.model_id = getattr(baseten, "model_id", "spark-open")

    async def next(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Turn:
        body = {"messages": messages, "tools": tools, "tool_choice": "auto", "max_tokens": self.max_tokens}
        payload = await self.baseten.chat("evo_agent", body)
        choice = (payload.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        calls = []
        for c in msg.get("tool_calls") or []:
            fn = c.get("function") or {}
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except ValueError:
                args = {"_unparsed": str(raw)[:400]}
            calls.append({"id": c.get("id") or f"call_{len(calls)}", "name": fn.get("name", ""), "arguments": args})
        return Turn(calls, str(msg.get("content") or ""), choice.get("finish_reason"), payload.get("usage"))


class PolicyBrain:
    """Mock mode and tests: a policy function picks the next call from the run's state (same loop, same tools)."""

    model_id = "policy"

    def __init__(self, policy: Callable[[AgentRun], tuple[str, dict[str, Any]] | None]) -> None:
        self.policy, self.n = policy, 0
        self.run: AgentRun | None = None

    def bind(self, run: AgentRun) -> None:
        self.run = run

    async def next(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Turn:
        assert self.run is not None, "bind the brain to its run"
        step = self.policy(self.run)  # the policy reads the run's state; the messages stay for the trace
        if step is None:
            return Turn([], "done")
        self.n += 1
        name, args = step
        return Turn([{"id": f"call_{self.n}", "name": name, "arguments": args}])


def default_policy(run: AgentRun) -> tuple[str, dict[str, Any]] | None:
    """A sensible scripted agent: resolve, propose, choose the top candidate, audit, render, inspect; edit covering
    failures once; change nothing structural (finalize with the failures stated)."""
    s = run.state
    for slot, name in (("sire", run.sire_name), ("dam", run.dam_name)):
        if slot not in s.resolved:
            return "resolve_animal", {"name": name, "reason": f"resolve the {slot}"}
    if s.candidates is None:
        return "propose_candidates", {"reason": "see the arrangements"}
    if s.chosen is None:
        return "choose_candidate", {"candidate_id": s.candidates[0]["id"], "reason": "top ranked"}
    if not run.audit_current():
        return "audit_plan", {"reason": "audit before render"}
    if not s.images:
        method = "growth_edit" if run.growth_default and has_covering(run.session.plan) else "single_pass"
        return "render", {"method": method, "reason": "render the audited plan"}
    last = s.images[s.order[-1]]
    if last.inspect is None:
        return "inspect", {"image_id": last.id, "reason": "check the render"}
    if last.inspect["verdict"] == "pass" or s.finalized:
        return ("finalize", {"image_id": last.id, "reason": "inspect passed"}) if not s.finalized else None
    cov = [f["key"] for f in last.inspect["failures"] if f["kind"] == "covering"]
    if cov and last.parent is None and s.edits < 1:
        return "edit", {"image_id": last.id, "failure_keys": cov, "reason": "covering failures: one edit"}
    return "finalize", {"image_id": run.best_image_id() or last.id, "reason": "remaining failures stated"}


# ------------------------------------------------------------------ run state


@dataclass
class Image:
    """An image of the run. Its bytes live on disk only (`path`); a tool loads them for one call and drops them, so
    neither the run nor the agent's history holds image data (S3c memory fix)."""
    id: str
    path: Path
    content_type: str
    response_id: str | None
    prompt: str
    kind: str  # render | growth_host | growth | edit
    plan_id: str
    plan: Any  # the plan it was rendered from (the agent may change the plan afterwards)
    parent: str | None = None
    key: str = ""
    inspect: dict[str, Any] | None = None
    raw_inspect: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    size: int = 0

    def load(self) -> bytes:
        return self.path.read_bytes()


@dataclass
class State:
    resolved: dict[str, Animal] = field(default_factory=dict)
    candidates: list[dict[str, Any]] | None = None
    chosen: str | None = None
    host_reason: str | None = None
    audited: str | None = None
    audit: dict[str, Any] | None = None
    images: dict[str, Image] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    renders: int = 0
    edits: int = 0
    calls: int = 0
    finalized: dict[str, Any] | None = None
    stop: str | None = None
    covering_streak: int = 0  # inspects in a row with covering failures (reset by a plan change or a clean inspect)
    edit_lock: str | None = None  # the plan content on which the two-failure rule stopped covering edits


class AgentError(Exception):
    """A tool refused the call (wrong order, bad arguments, a guardrail). The agent sees the message and a hint."""

    def __init__(self, code: str, message: str, hint: str = "", valid: list[str] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.hint, self.valid = code, message, hint, valid


class AgentRun:
    def __init__(self, engine: Any, sire_name: str, dam_name: str, mode: str = "speculative", seed: int = 0,
                 brain: Any = None, ask: Callable[[str, list[str]], Awaitable[str]] | None = None,
                 growth_default: bool = False, image_dir: Path | None = None,
                 on_step: Callable[[AgentRun, dict[str, Any]], None] | None = None) -> None:
        self.engine, self.sire_name, self.dam_name, self.mode, self.seed = engine, sire_name, dam_name, mode, seed
        self.cfg = settings()
        self.brain = brain or PolicyBrain(default_policy)
        if hasattr(self.brain, "bind"):
            self.brain.bind(self)
        self.ask = ask  # None: not interactive
        self.growth_default = growth_default
        self.state = State()
        self.session: PlanSession | None = None
        self.trace: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.started = time.time()
        self.image_dir = Path(image_dir) if image_dir else Path(tempfile.mkdtemp(prefix="agent_imgs_"))
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.on_step = on_step  # called after every tool step (the live script saves the run to disk there)

    # ------------------------------------------------------------------ loop

    def system_prompt(self) -> str:
        ask = " or call ask_user" if self.ask else " (this run is not interactive: ask_user returns no answer)"
        return SYSTEM.replace("{ask}", ask).replace("{renders}", str(self.cfg["max_renders"])).replace(
            "{calls}", str(self.cfg["max_tool_calls"]))

    def task_prompt(self) -> str:
        return (f"Build one creature from the parents '{self.sire_name}' (sire) and '{self.dam_name}' (dam) in "
                f"{self.mode} mode. Start with resolve_animal for each parent.")

    async def run(self) -> dict[str, Any]:
        self.messages = [{"role": "system", "content": self.system_prompt()},
                         {"role": "user", "content": self.task_prompt()}]
        nudges = 0
        while self.state.finalized is None:
            if self.state.calls >= self.cfg["max_tool_calls"]:
                self.state.stop = f"tool-call cap reached ({self.cfg['max_tool_calls']})"
                break
            try:
                turn = await self.brain.next(self.messages, TOOLS)
            except ChimeraError as e:
                if e.code == ErrorCode.BUDGET_EXCEEDED:
                    raise
                self._log_brain_error(f"{e.code.value}: {e.message[:200]}")
                self.state.stop = f"agent call failed ({e.code.value})"
                break
            if not turn.calls:
                nudges += 1
                self._log_text(turn)
                if nudges > self.cfg["max_nudges"]:
                    self.state.stop = "the agent stopped calling tools"
                    break
                self.messages.append({"role": "assistant", "content": turn.text or ""})
                self.messages.append({"role": "user", "content": "Call a tool. Finish with finalize."})
                continue
            self.messages.append({"role": "assistant", "content": turn.text or None, "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(
                    c["arguments"])}} for c in turn.calls]})
            for c in turn.calls:
                if self.state.finalized is not None or self.state.calls >= self.cfg["max_tool_calls"]:
                    self.messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(
                        {"ok": False, "error": "not run: the run has ended or reached its tool-call cap"})})
                    continue
                result = await self.call(c["name"], c["arguments"], turn.text)
                self.messages.append({"role": "tool", "tool_call_id": c["id"],
                                      "content": json.dumps(result, ensure_ascii=False)[:RESULT_CHARS]})
        if self.state.finalized is None:
            await self._code_finalize()
        return self.state.finalized or {}

    async def call(self, name: str, args: dict[str, Any], said: str = "") -> dict[str, Any]:
        """Run one tool and log it. Tool errors come back to the agent as structured results."""
        self.state.calls += 1
        args = dict(args or {})
        reason = str(args.pop("reason", "") or "").strip()
        t0 = time.time()
        step: dict[str, Any] = {"n": self.state.calls, "tool": name, "arguments": args, "reason": reason,
                                "agent_text": said[:600] if said else ""}
        try:
            if name not in TOOL_NAMES:
                raise AgentError("unknown_tool", f"no tool {name!r}", valid=TOOL_NAMES)
            if not reason:
                raise AgentError("missing_reason", "every call needs a reason", hint="add a short reason")
            result = await getattr(self, f"t_{name}")(**args)
            out = {"ok": True, **result}
        except AgentError as e:
            out = {"ok": False, "error": e.code, "message": e.message, "hint": e.hint, **({"valid": e.valid} if e.valid
                                                                                           else {})}
        except TypeError as e:
            out = {"ok": False, "error": "bad_arguments", "message": str(e)[:200]}
        except ChimeraError as e:
            if e.code == ErrorCode.BUDGET_EXCEEDED:
                raise
            out = {"ok": False, "error": e.code.value, "message": e.message[:300]}
        step.update(ok=out["ok"], result=out, cards=_cards_in(out), seconds=round(time.time() - t0, 1),
                    summary=_summary(name, out))
        self.trace.append(step)
        if self.on_step is not None:
            self.on_step(self, step)
        return out

    def _log_text(self, turn: Turn) -> None:
        self.trace.append({"n": None, "tool": None, "agent_text": (turn.text or "")[:1200], "ok": True,
                           "summary": "no tool call", "finish_reason": turn.finish_reason, "cards": []})

    def _log_brain_error(self, msg: str) -> None:
        self.trace.append({"n": None, "tool": None, "ok": False, "summary": f"agent call failed: {msg}", "cards": []})

    # ------------------------------------------------------------------ tools

    async def t_resolve_animal(self, name: str) -> dict[str, Any]:
        res = await self.engine.resolve(name)
        slot = next((s for s, n in (("sire", self.sire_name), ("dam", self.dam_name)) if norm(n) == norm(name)), None)
        out: dict[str, Any] = {"status": res.status, "note": res.note}
        if res.status != "resolved" or res.animal is None:
            out["alternatives"] = [{"common_name": a.get("common_name"), "scientific_name": a.get("scientific_name")}
                                   for a in (res.alternatives or [])][:5]
            return out
        a = res.animal
        if slot is not None:
            self.state.resolved[slot] = a
            self.engine.resolutions[slot] = res
        out.update(slot=slot, animal=_animal_brief(a))
        return out

    def _need_parents(self) -> tuple[Animal, Animal]:
        miss = [s for s in ("sire", "dam") if s not in self.state.resolved]
        if miss:
            raise AgentError("not_resolved", f"resolve the {' and '.join(miss)} first", hint="call resolve_animal")
        return self.state.resolved["sire"], self.state.resolved["dam"]

    def _new_session(self) -> PlanSession:
        sire, dam = self._need_parents()
        if sire.id == dam.id:
            raise AgentError("same_animal", "the two parents are the same animal")
        return PlanSession(self.engine, sire, dam, self.mode, self.seed)

    async def t_propose_candidates(self) -> dict[str, Any]:
        self._need_parents()
        base = self._new_session()
        tie = base.tie
        hosts = [base.plan.host] if base.plan.host else [None]
        other = [p for p in (base.sire.id, base.dam.id) if p not in hosts and base.route.mode != "hybrid"]
        hosts += other  # both host options always: a tie lists both as equals, otherwise the second is advised against
        cands: list[dict[str, Any]] = []
        for h in hosts:
            ops: list[dict[str, Any]] = []
            if h is not None and (tie or h != base.plan.host):
                ops.append({"op": "set_host", "args": {"animal": self.engine.tax.animals[h].common_name}})
            sess = self._replay(ops)
            if sess is None:
                continue
            cands.append(self._candidate(sess, ops, tie, primary=(h == base.plan.host)))
            donor = sess.plan.other(sess.plan.host) if sess.plan.host else None
            if donor and sess.plan.identity_parts:  # a second diagnostic part as an identity alternative
                d = self.engine.tax.animals[donor]
                cur = sess.plan.identity_parts[0].part
                alt = next((c for c in identity_candidates(d) if c.part != cur and c.feature), None)
                if alt is not None:
                    ops2 = [*ops, {"op": "set_identity_part", "args": {"donor": d.common_name, "part": alt.part,
                                                                         "reason": f"alternative: {alt.feature}"}}]
                    if (s2 := self._replay(ops2)) is not None:
                        cands.append(self._candidate(s2, ops2, tie, primary=False))
        for i, c in enumerate(sorted(cands, key=lambda c: -c["score"]), 1):
            c["id"] = f"C{i}"
        cands.sort(key=lambda c: c["id"])
        self.state.candidates = cands
        return {"host_tie": [self.engine.tax.animals[i].common_name for i in tie] or None,
                "candidates": cands, "note": "advice only: you choose; scores rank the R10 notes, nothing more",
                "cards": ["RC-R10-01", "RC-R6-08", "RC-R6-09", "RC-R10-15"]}

    def _replay(self, ops: list[dict[str, Any]]) -> PlanSession | None:
        s = self._new_session()
        for o in ops:
            if not s.apply(o["op"], o["args"]).ok:
                return None
        return s

    def _candidate(self, s: PlanSession, ops: list[dict[str, Any]], tie: list[str], primary: bool) -> dict[str, Any]:
        g, tax = s.plan, self.engine.tax
        host = tax.animals[g.host] if g.host else None
        donor = tax.animals[g.other(g.host)] if g.host else None
        notes, score = {}, 0.0
        hab = g.habitat.name
        fits = [a.common_name for a in (s.sire, s.dam) if hab in a.habitats]
        notes["niche"] = f"habitat {hab} ({'native to ' + ', '.join(fits) if fits else 'a bridging habitat'})"
        score += 1.0 if host and hab in host.habitats else 0.5
        bad = [f"{i.function}: {i.result}" for i in g.audit if i.result not in ("pass", "licensed", "pending")]
        notes["autonomy"] = (f"the {host.common_name if host else 'blend'} body carries every function" if not bad
                             else "functions not carried: " + "; ".join(bad))
        score += 1.0 - 0.25 * len(bad)
        notes["survival"] = (f"{len(g.licenses)} license(s) of {s.summary()['license_budget']}: "
                             + ("; ".join(x.rule for x in g.licenses) or "none")
                             + (f"; labels: {'; '.join(x for x in g.labels if x.startswith('speculative:'))}"
                                if any(x.startswith("speculative:") for x in g.labels) else ""))
        score -= 0.2 * len(g.licenses)
        cov = next((t for t in g.transfers if t.kind == "covering"), None)
        ids = g.identity_parts
        bits = []
        if ids:
            bits.append(f"identity part: {ids[0].part} ({ids[0].feature or 'class list'}; {ids[0].source})")
        if cov:
            bits.append(f"covering over {', '.join(cov.extent)}" + (f", {cov.plate_pattern}" if cov.plate_pattern else "")
                        + (f"; {cov.host_shell}" if cov.host_shell else ""))
        if donor and host and needs_identity(donor, host) and not ids and g.design_mode != "realistic":
            bits.append("no identity part from the donor's own traits")
            score -= 0.5
        notes["identity"] = "; ".join(bits) or "donor shown through blended traits"
        score += 0.5 * bool(ids) + 0.5 * bool(cov)
        if tie:
            notes["host"] = (f"structural tie: {host.common_name if host else '-'} is one of two equal options "
                             "(RC-R10-01: never by size, mass or name order)")
        elif not primary and host is not None:
            notes["host"] = f"the {host.common_name} has the less structured body schema (RC-R6-08, soft): advised against"
            score -= 1.0
        else:
            notes["host"] = f"the {host.common_name if host else 'blend'} has the more structured body schema (RC-R6-08)"
        summ = s.summary()
        return {"id": "", "ops": ops, "score": round(score, 2), "host": summ["host"], "silhouette": g.silhouette,
                "parts": summ["parts"], "dropped": summ["dropped"], "identity_parts": summ["identity_parts"],
                "covering": ({"extent": cov.extent, "plate_pattern": cov.plate_pattern,
                              "plate_source": cov.plate_source} if cov else None),
                "licenses": summ["licenses"], "labels": g.labels, "notes": notes}

    async def t_choose_candidate(self, candidate_id: str) -> dict[str, Any]:
        if self.state.candidates is None:
            raise AgentError("no_candidates", "call propose_candidates first")
        c = next((x for x in self.state.candidates if x["id"] == candidate_id), None)
        if c is None:
            raise AgentError("unknown_candidate", f"no candidate {candidate_id!r}",
                             valid=[x["id"] for x in self.state.candidates])
        s = self._replay(c["ops"])
        if s is None:
            raise AgentError("replay_failed", "the candidate's operations no longer apply")
        self.session, self.state.chosen, self.state.audited = s, candidate_id, None
        return {"chosen": candidate_id, "plan": self._plan_brief(), "next": "audit_plan"}

    def audit_current(self) -> bool:
        """The current plan passed audit_plan (by content: who last set a field does not matter)."""
        return self.session is not None and self.state.audited == _content_key(self.session.plan)

    def _need_session(self) -> PlanSession:
        if self.session is None:
            raise AgentError("no_plan", "choose a candidate first", hint="propose_candidates, then choose_candidate")
        return self.session

    async def t_plan_op(self, op: str, args: dict[str, Any]) -> dict[str, Any]:
        s = self._need_session()
        before = _content_key(s.plan)
        res = s.apply(op, dict(args or {}))
        changed = res.ok and _content_key(s.plan) != before
        if changed:
            self.state.audited = None
        out = res.public()
        out.pop("summary", None)
        note = {"next": "audit_plan"} if changed else (
            {"note": "the plan is unchanged (this was already so): rendering it again gives the same plan"}
            if res.ok else {})
        return {**out, "changed": changed, "plan": self._plan_brief(), **note}

    async def t_audit_plan(self) -> dict[str, Any]:
        s = self._need_session()
        g, r = s.plan, s.route
        blocking = [{"card": v.card, "detail": v.detail} for v in self.engine._check(g, r)]
        if host_tie(r) and s.host_pick is None:
            blocking.append({"card": "RC-R10-01", "detail": "structural host tie: choose the host (set_host, or a "
                             "candidate that sets it) with a reason (D-085)"})
        items, _pen = soft_penalties(g, r, self.engine.tax)
        advice = [{"card": i.get("card"), "detail": i.get("detail") or i.get("why") or "", "weight": i.get("weight")}
                  for i in items]
        advice += [{"card": ",".join(a.cards[:2]), "detail": f"{a.function}: {a.result} ({a.detail[:160]})"}
                   for a in g.audit if a.result not in ("pass", "licensed", "pending")]
        audit = {"blocking": blocking, "advice": advice,
                 "functions": {a.function: a.result for a in g.audit},
                 "fiction_budget": {"budget": s.summary()["license_budget"],
                                    "licenses": [{"rule": x.rule, "card": x.card, "compensation": x.compensation}
                                                 for x in g.licenses],
                                    "identity_parts": s.summary()["identity_parts"]},
                 "labels": g.labels}
        self.state.audit = audit
        self.state.audited = _content_key(g) if not blocking else None
        cards = sorted({b["card"] for b in blocking} | {a["card"] for a in advice if a.get("card")})
        return {**audit, "renderable": not blocking, "cards": cards}

    def _ready(self) -> PlanSession:
        s = self._need_session()
        if not self.audit_current():
            raise AgentError("not_audited", "the current plan has not passed audit_plan since its last change",
                             hint="call audit_plan; fix any blocking item first")
        if self.state.renders >= self.cfg["max_renders"]:
            raise AgentError("render_cap", f"the render cap ({self.cfg['max_renders']}) is reached",
                             hint="finalize your best inspected image")
        return s

    async def _render(self, prompt: str, refs: list[bytes], previous: str | None = None) -> Any:
        eng = self.engine
        kind = "edit" if previous else "render"
        img = await eng.meter.call("image", kind, eng.renderer.generate(prompt, refs, "1:1", previous))
        if eng.mock:
            eng.registry.note(img.data, prompt)
        return img

    def _add_image(self, img: Any, prompt: str, kind: str, plan: Any, parent: str | None = None,
                   **extra: Any) -> Image:
        """Write the image to disk and keep only its path; the caller drops the downloaded bytes."""
        iid = f"img{len(self.state.order) + 1}"
        ext = {"image/png": "png", "image/jpeg": "jpg"}.get(img.content_type, "webp")
        path = self.image_dir / f"{iid}.{ext}"
        path.write_bytes(img.data)
        im = Image(iid, path, img.content_type, img.response_id, prompt, kind, plan.id, plan, parent, extra=extra,
                   size=len(img.data))
        self.state.images[iid] = im
        self.state.order.append(iid)
        return im

    async def t_render(self, method: str = "single_pass") -> dict[str, Any]:
        s = self._ready()
        g, eng = s.plan, self.engine
        refs = [swatch(g.parents.sire), swatch(g.parents.dam)] if eng.mock else []  # no reference portraits (5b)
        await eng._judge_functions(g)
        if method == "growth_edit":
            if not has_covering(g):
                raise AgentError("no_covering", "growth by edit grows a donor covering; this plan has none",
                                 valid=["single_pass"])
            first = compile_prompt(host_first(g), eng.tax)
            img1 = await self._render(first, refs)
            self.state.renders += 1
            im1 = self._add_image(img1, first, "growth_host", g)
            del img1
            instr = growth_instruction(g, eng.tax)
            img2 = await self._render(instr, [], im1.response_id)
            self.state.edits += 1
            full = compile_prompt(g, eng.tax)
            im = self._add_image(img2, f"{first}\n\n[edit turn]\n{instr}", "growth", g, parent=im1.id,
                                 prompt_compiled=full)
            del img2
            return {"image_id": im.id, "method": method, "host_image_id": im1.id, "renders_used": self.state.renders,
                    "note": "growth edit done: inspect checks host drift against the host image",
                    "cards": ["RC-R10-12", "RC-R10-15"]}
        prompt = compile_prompt(g, eng.tax)
        polished = await eng.meter.call("spark", "polish", eng.spark.polish(prompt))
        final, why = accept_polish(prompt, polished, g, eng.tax)
        img = await self._render(final, refs)
        self.state.renders += 1
        im = self._add_image(img, final, "render", g, prompt_compiled=prompt,
                             polish="accepted" if not why else f"rejected: {why}")
        del img
        return {"image_id": im.id, "method": method, "renders_used": self.state.renders,
                "renders_left": self.cfg["max_renders"] - self.state.renders, "polish": im.extra["polish"]}

    def _image(self, image_id: str) -> Image:
        im = self.state.images.get(image_id)
        if im is None:
            raise AgentError("unknown_image", f"no image {image_id!r}", valid=list(self.state.images))
        return im

    async def t_inspect(self, image_id: str) -> dict[str, Any]:
        im = self._image(image_id)
        s = self._need_session()
        g = im.plan
        if im.inspect is not None:
            return {"image_id": image_id, "cached": True, **im.inspect}
        data = im.load()  # loaded for the critics' calls only
        try:
            insp = await self.engine._inspect(data, g, s.route, {})
        finally:
            del data
        rows = []
        for f in insp["failures"]:
            rows.append({"key": f["key"], "kind": failure_kind(f), "status": f["status"], "text": f["text"][:160],
                         "fix": (f.get("fix") or "")[:200]})
        drift = None
        parent = self.state.images.get(im.parent) if im.parent else None
        im.raw_inspect = insp  # the drift check reads this image's own descriptions
        if parent is not None:
            drift = await self._drift(parent, im, g)
            if drift["drifted"]:
                rows.append({"key": "host_drift", "kind": "structural", "status": "fail",
                             "text": f"the edit changed the host: {', '.join(drift['changed'])}",
                             "fix": "render the plan again (single pass) instead of keeping this edit"})
        verdict = "pass" if not rows else "fail"
        out = {"image_id": image_id, "verdict": verdict, "failures": rows,
               "counts": {k: v for k, v in insp.get("expected_counts", {}).items()},
               "third_animals": insp.get("third_animals"), "drift": drift,
               "decision": "Meta Spark decides; Spark Open answers kept as information (D-084)"}
        im.inspect, im.raw_inspect = out, insp
        return {**out, "images_so_far": self._scoreboard(), "best_so_far": self.best_image_id(),
                "cards": ["RC-R10-12", "RC-R10-15", "RC-R10-16"] if rows else []}

    def _scoreboard(self) -> dict[str, dict[str, int]]:
        """Every inspected image's failure counts, so the agent can compare an edit with what it started from."""
        return {i: {"structural": sum(f["kind"] == "structural" for f in im.inspect["failures"]),
                    "covering": sum(f["kind"] == "covering" for f in im.inspect["failures"])}
                for i, im in self.state.images.items() if im.inspect is not None}

    async def _drift(self, before: Image, after: Image, g: Any) -> dict[str, Any]:
        """Host drift across an edit, from the critics' plan-blind counts. The before image is inspected (or
        described) first if needed; no count is compared without both."""
        if before.raw_inspect is None:
            from app.evolution.critic import critics_for

            descs = {}
            for name, spark in critics_for(self.engine.spark).items():
                try:
                    descs[name] = await self.engine.meter.call("spark", f"drift_before:{name}", spark.describe(before.load()))
                except ChimeraError as e:
                    if e.code == ErrorCode.BUDGET_EXCEEDED:
                        raise
            before.extra["descriptions"] = descs
            b_desc = descs
        else:
            b_desc = before.raw_inspect.get("descriptions") or {}
        a_desc = (after.raw_inspect or {}).get("descriptions") or {}
        planned = planned_counts(g, self.engine.tax)
        changed: dict[str, list[str]] = {}
        for name in set(b_desc) & set(a_desc):
            b, a = b_desc[name] or {}, a_desc[name] or {}
            changed[name] = [k for k in DRIFT_KEYS if isinstance(b.get(k), int) and isinstance(a.get(k), int)
                             and b[k] != a[k] and a[k] != planned.get(k)]
        agreed = sorted(set.intersection(*(set(v) for v in changed.values()))) if changed else []
        return {"drifted": bool(agreed), "changed": agreed, "by_critic": changed}

    def _plan_for(self, im: Image) -> Any:
        return im.plan

    async def t_edit(self, image_id: str, failure_keys: list[str]) -> dict[str, Any]:
        im = self._image(image_id)
        if im.inspect is None:
            raise AgentError("not_inspected", "inspect the image first, then edit named failures")
        if self.state.edits >= self.cfg["max_edits"]:
            raise AgentError("edit_cap", f"the edit cap ({self.cfg['max_edits']}) is reached")
        fails = {f["key"]: f for f in (im.raw_inspect or {}).get("failures", [])}
        keys = [k for k in failure_keys if k in fails]
        if not keys:
            raise AgentError("unknown_failure", "none of these keys is a failure of this image",
                             valid=list(fails))
        structural = [k for k in keys if failure_kind(fails[k]) == "structural"]
        if structural:
            raise AgentError("structural_failure", f"{structural} are structural: an edit turn fixes coverings and "
                             "surfaces only", hint="change the plan with plan_op (or choose another candidate), "
                             "audit, and render again",
                             valid=[k for k in keys if k not in structural] or None)
        instr = edit_instruction([fails[k] for k in keys])
        img = await self._render(instr, [], im.response_id)
        self.state.edits += 1
        new = self._add_image(img, f"{im.prompt}\n\n[edit turn]\n{instr}", "edit", im.plan, parent=im.id,
                              instruction=instr, prompt_compiled=im.extra.get("prompt_compiled"))
        del img
        return {"image_id": new.id, "instruction": instr, "edits_used": self.state.edits,
                "next": "inspect the new image (host drift is checked there)"}

    async def t_ask_user(self, question: str, options: list[str]) -> dict[str, Any]:
        if self.ask is None:
            return {"answer": None, "note": "not an interactive run: decide yourself and state the reason"}
        ans = await self.ask(question, list(options))
        return {"answer": ans}

    async def t_finalize(self, image_id: str) -> dict[str, Any]:
        im = self._image(image_id)
        if im.inspect is None:
            raise AgentError("not_inspected", "inspect the image before finalizing it")
        best = self.best_image_id()
        doc = await self._finish(im, "finalized by the agent")
        if best and best != im.id:
            doc["card"]["agent"]["note"] = f"the agent finalized {im.id}; by failure counts {best} was better"
        return {"creature_id": doc["genome"]["id"], "remaining_failures": doc["card"]["remaining_failures"]}

    # ------------------------------------------------------------------ finish

    def best_image_id(self) -> str | None:
        done = [self.state.images[i] for i in self.state.order if self.state.images[i].inspect is not None]
        if not done:
            return None

        def rank(im: Image) -> tuple[int, int, int]:
            f = im.inspect["failures"]  # type: ignore[index]
            return (sum(x["kind"] == "structural" for x in f), len(f), -self.state.order.index(im.id))

        return min(done, key=rank).id

    async def _code_finalize(self) -> None:
        best = self.best_image_id()
        if best is None and self.state.order:  # rendered but never inspected: inspect the last one
            last = self.state.order[-1]
            await self.call("inspect", {"image_id": last, "reason": f"code: {self.state.stop}; inspect before finalizing"})
            best = self.best_image_id()
        if best is None:
            self.state.finalized = {"error": f"no image: {self.state.stop or 'the agent never rendered'}",
                                    "trace": self.trace}
            return
        self.trace.append({"n": None, "tool": "finalize", "arguments": {"image_id": best}, "ok": True,
                           "reason": f"code: {self.state.stop or 'the agent ended without finalize'}; the best "
                           "inspected image (fewest structural, then fewest failures)",
                           "summary": f"finalized {best} by code", "cards": []})
        await self._finish(self.state.images[best], f"finalized by code: {self.state.stop}")

    async def _finish(self, im: Image, how: str) -> dict[str, Any]:
        s, eng = self._need_session(), self.engine
        g = self._plan_for(im)
        data = im.load()
        try:
            verdict = await judge(data, g, s.route, eng.tax, eng.spark, eng.segmenter, eng.meter)
            g = g.model_copy(update={"scores": verdict["scores"]})
            key = f"evo/{g.id}.agent.{im.id}.webp"
            await eng.services.storage.put(key, data, im.content_type)
        finally:
            del data
        im.key = key
        card = output_card(g, s.route, eng.tax)
        remaining = [{"key": f["key"], "kind": f["kind"], "text": f["text"]} for f in im.inspect["failures"]]  # type: ignore[index]
        card["remaining_failures"] = remaining
        card["agent"] = {"brain": getattr(self.brain, "model_id", "?"), "renders": self.state.renders,
                         "edits": self.state.edits, "tool_calls": self.state.calls, "stop": how,
                         "candidate": self.state.chosen}
        doc = {"genome": g.model_dump(), "prompt": im.prompt,
               "prompt_compiled": im.extra.get("prompt_compiled") or compile_prompt(g, eng.tax),
               "image_key": key, "image_id": im.id, "image_kind": im.kind, "judge": verdict, "card": card,
               "route": s.route.public(), "inspect": im.raw_inspect, "agent_inspect": im.inspect,
               "response_id": im.response_id, "warnings": [f"remaining failure: {r['text']}" for r in remaining],
               "agent": {**card["agent"], "trace_steps": len(self.trace)}}
        eng.store.put("creatures", g.id, doc)
        self.state.finalized = doc
        return doc

    # ------------------------------------------------------------------ views

    def _plan_brief(self) -> dict[str, Any]:
        s = self._need_session()
        sm = s.summary()
        cov = next((t for t in s.plan.transfers if t.kind == "covering"), None)
        return {"plan_id": sm["plan_id"], "host": sm["host"], "host_tie": sm["host_tie"], "mode": sm["design_mode"],
                "habitat": sm["habitat"], "silhouette": sm["silhouette"], "parts": sm["parts"],
                "identity_parts": sm["identity_parts"], "dropped": sm["dropped"], "licenses": sm["licenses"],
                "covering": ({"extent": cov.extent, "plate_pattern": cov.plate_pattern} if cov else None),
                "transfers": [{"feature": t["feature"], "class": t["class"], "anchor": t["anchor"]}
                              for t in sm["transfers"] if t["feature"] != "covering"]}

    def trace_md(self) -> str:
        return trace_markdown(self)


# ------------------------------------------------------------------ helpers


def _animal_brief(a: Animal) -> dict[str, Any]:
    return {"id": a.id, "common_name": a.common_name, "scientific_name": a.scientific_name, "class": a.tax_class,
            "body_plan": a.body_plan, "covering": a.covering, "mass_kg": a.mass_kg, "habitats": list(a.habitats),
            "breathing": a.breathing, "features": list(a.features)[:5],
            "features_source": a.source_of("visible_features", "features"), "source": a.source}


def _content_key(g: Any) -> str:
    """The plan's content, ignoring who last set a field (a repeated operation marks set_by "agent" only)."""
    d = g.model_dump(exclude={"id", "scores", "checks"})
    for t in d.get("transfers", []):
        t["set_by"] = ""
    for p in d.get("identity_parts", []):
        p["set_by"], p["reason"] = "", ""
    return json.dumps(d, sort_keys=True)


def _cards_in(obj: Any) -> list[str]:
    import re

    found = re.findall(r"RC-R\d+-\d+", json.dumps(obj))
    return sorted(set(found))


def _summary(name: str, out: dict[str, Any]) -> str:
    if not out.get("ok"):
        return f"refused: {out.get('error')}: {out.get('message', '')[:160]}"
    if name == "resolve_animal":
        a = out.get("animal") or {}
        return f"{out.get('status')}: {a.get('common_name', '')} ({a.get('scientific_name', '')})"
    if name == "propose_candidates":
        cs = out.get("candidates") or []
        tie = out.get("host_tie")
        return (f"{len(cs)} candidates" + (f"; host tie {tie}" if tie else "") + ": "
                + "; ".join(f"{c['id']} host {c['host']}, identity "
                            f"{(c['identity_parts'] or [{}])[0].get('part', '-')}, score {c['score']}" for c in cs))
    if name == "choose_candidate":
        p = out.get("plan") or {}
        return f"{out.get('chosen')}: host {p.get('host')}, parts {p.get('parts')}"
    if name == "plan_op":
        return f"{out.get('op')} ok" + (f"; warnings {out.get('warnings')}" if out.get("warnings") else "")
    if name == "audit_plan":
        return (f"renderable={out.get('renderable')}; blocking {[b['card'] for b in out.get('blocking', [])]}; "
                f"{len(out.get('advice', []))} advice items")
    if name == "render":
        return f"{out.get('image_id')} ({out.get('method')}), renders used {out.get('renders_used')}"
    if name == "inspect":
        f = out.get("failures") or []
        return f"{out.get('image_id')}: {out.get('verdict')}" + (
            " - " + "; ".join(f"{x['key']} ({x['kind']}, {x['status']})" for x in f) if f else "")
    if name == "edit":
        return f"{out.get('image_id')} from an edit: {out.get('instruction', '')[:160]}"
    if name == "finalize":
        return f"{out.get('creature_id')}; remaining failures {len(out.get('remaining_failures') or [])}"
    if name == "ask_user":
        return f"answer: {out.get('answer')}"
    return "ok"


def trace_markdown(run: AgentRun) -> str:
    lines = [f"# Agent trace: {run.sire_name} x {run.dam_name} ({run.mode})", "",
             f"Brain: {getattr(run.brain, 'model_id', '?')}. Renders {run.state.renders}, edits {run.state.edits}, "
             f"tool calls {run.state.calls}. Stop: {run.state.stop or 'finalized by the agent'}.", ""]
    for st in run.trace:
        head = f"## {st['n']}. {st['tool']}" if st.get("n") else f"## {st.get('tool') or 'agent text'}"
        lines.append(head)
        if st.get("arguments"):
            lines.append(f"- arguments: `{json.dumps(st['arguments'], ensure_ascii=False)[:400]}`")
        if st.get("reason"):
            lines.append(f"- reason: {st['reason']}")
        if st.get("agent_text"):
            lines.append(f"- agent said: {st['agent_text'][:600]}")
        lines.append(f"- result: {st.get('summary', '')}")
        if st.get("cards"):
            lines.append(f"- cards: {', '.join(st['cards'])}")
        lines.append("")
    return "\n".join(lines)


def dropped_parts_of(g: Any) -> list[str]:
    return [f[len(DROPPED):] for f in g.traits["body"].flags if f.startswith(DROPPED)]
