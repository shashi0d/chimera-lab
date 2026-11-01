"""S1: capability probe for the new architecture. One part per invocation:

    .venv/Scripts/python.exe scripts/s1_probe.py spark     # part 2: Spark Open on Baseten (JSON, image, tools, refusals)
    .venv/Scripts/python.exe scripts/s1_probe.py parity    # part 3: 10 recorded Meta Spark requests replayed on Baseten
    .venv/Scripts/python.exe scripts/s1_probe.py image     # part 4: Muse Image references and edit turn (Meta)
    .venv/Scripts/python.exe scripts/s1_probe.py sam       # part 5: SAM 3.1 part prompts (Meta)

Keys come from .env (META_API_KEY, BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26) and are never printed or saved;
recordings are key-free and elide base64. Caps are runaway guards only (shared counter docs/live/budget.json).
Outputs: docs/evolution/live/s1/<part>/ (results.json, raw/ recordings, images and masks).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evolution" / "live" / "s1"
E4 = ROOT / "docs" / "evolution" / "live" / "e4"
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)  # Settings reads .env from the working directory
os.environ.update({
    "CHIMERA_LIVE_BUDGET_FILE": str(ROOT / "docs" / "live" / "budget.json"),
    "CHIMERA_LIVE_LOG": str(ROOT / "docs" / "LIVE_LOG.md"),
    "CHIMERA_LIVE_MAX_IMAGES": "30",
    "CHIMERA_LIVE_MAX_SPARK": "120",
    "CHIMERA_LIVE_MAX_SAM": "30",
    "CHIMERA_LIVE_MAX_SPARK_BASETEN": "300",
})

from app.adapters.baseten.client import BasetenEvoSpark
from app.adapters.meta.client import _data_url, _message_json
from app.adapters.usage import CallRecord, budget_used, current_calls, current_step
from app.config import Settings
from app.errors import ChimeraError
from app.evolution import live
from app.evolution.engine import EvoEngine
from app.evolution.genome import validate_plan
from app.evolution.judge import judge, mask_stats
from app.evolution.prompt import accept_polish
from app.evolution.route import route
from app.services import build_services
from PIL import Image

LOCKED = ("parents", "mode", "known_pair", "host", "labels")
PLAN_TASK = "Write the first plan for this pair."


# ------------------------------------------------------------------ shared helpers


def w(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, bytes):
        path.write_bytes(obj)
    else:
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj, indent=1, ensure_ascii=False, default=str),
                        encoding="utf-8")


def schema_errors(value: Any, schema: dict[str, Any], at: str = "$") -> list[str]:
    """The JSON Schema subset our strict schemas use: type, enum, properties, required, additionalProperties,
    items and anyOf."""
    if "anyOf" in schema:
        return [] if any(not schema_errors(value, s, at) for s in schema["anyOf"]) else [f"{at}: matches no anyOf"]
    errs: list[str] = []
    types = schema.get("type")
    types = [types] if isinstance(types, str) else types or []
    ok = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
          "number": isinstance(value, (int, float)) and not isinstance(value, bool),
          "integer": isinstance(value, int) and not isinstance(value, bool), "boolean": isinstance(value, bool),
          "null": value is None}
    if types and not any(ok[t] for t in types):
        return [f"{at}: expected {types}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{at}: {value!r} not in enum")
    if isinstance(value, dict) and "properties" in schema:
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{at}.{k}: missing")
        if schema.get("additionalProperties") is False:
            errs += [f"{at}.{k}: not allowed" for k in value if k not in schema["properties"]]
        for k, v in value.items():
            if k in schema["properties"]:
                errs += schema_errors(v, schema["properties"][k], f"{at}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            errs += schema_errors(v, schema["items"], f"{at}[{i}]")
    return errs


def json_report(payload: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    """Strict-JSON facts about one chat completion, without trusting the parser's leniency."""
    choice = (payload.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content)
    content = content or ""
    out: dict[str, Any] = {"finish_reason": choice.get("finish_reason"), "content_chars": len(content),
                           "starts_with_brace": content.lstrip().startswith("{"),
                           "code_fence": "```" in content, "think_tags": "<think" in content,
                           "reasoning_field": next((k for k in ("reasoning_content", "reasoning") if msg.get(k)), None),
                           "refusal_field": bool(msg.get("refusal"))}
    try:
        data = json.loads(content)
        out["json_valid"] = True
        out["schema_errors"] = schema_errors(data, schema)[:8] if schema else []
        out["schema_valid"] = not out["schema_errors"]
    except json.JSONDecodeError as e:
        out.update(json_valid=False, schema_valid=False, json_error=str(e)[:120], content_head=content[:300])
    return out


REFUSAL_WORDS = re.compile(r"\b(i can(?:no|')t|i'm unable|i am unable|i won't|cannot help|not able to|sorry|"
                           r"policy|inappropriate|unethical|harmful)\b", re.IGNORECASE)


def refusal_of(payload: dict[str, Any] | None, error: str | None) -> str | None:
    if error and "MODEL_REFUSED" in error:
        return f"error {error}"
    if not payload:
        return None
    choice = (payload.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    if choice.get("finish_reason") == "content_filter":
        return "finish_reason content_filter"
    if msg.get("refusal"):
        return f"refusal field: {str(msg['refusal'])[:120]}"
    content = msg.get("content") or ""
    if isinstance(content, str) and not content.lstrip().startswith("{") and REFUSAL_WORDS.search(content):
        return f"deflection text: {content[:160]}"
    return None


class Run:
    """Collects the usage records of every attempt so each probe reports its own latency and outcome."""

    def __init__(self, part: str) -> None:
        self.part, self.dir = part, OUT / part
        os.environ["CHIMERA_RECORD_DIR"] = str(self.dir / "raw")
        self.calls: list[CallRecord] = []
        self.n = 0
        current_calls.set(self.calls)
        self.settings = Settings(chimera_mode="real", local_data_dir=str(ROOT / ".localdata" / "s1"))
        if not self.settings.meta_api_key:
            sys.exit("META_API_KEY is not set")
        self.before = budget_used()

    def mark(self) -> int:
        return len(self.calls)

    def since(self, start: int) -> list[dict[str, Any]]:
        return [{k: v for k, v in asdict(c).items() if k in ("kind", "purpose", "model", "latency_ms",
                                                              "input_tokens", "output_tokens", "outcome")}
                for c in self.calls[start:]]

    def finish(self, results: dict[str, Any]) -> None:
        after = budget_used()
        results["budget"] = {"before": self.before, "after": after,
                             "made": {k: after[k] - self.before.get(k, 0) for k in after}}
        results["attempts"] = [asdict(c) for c in self.calls]
        w(self.dir / "results.json", results)
        print("budget", self.before, "->", after)


async def bt_call(run: Run, spark: BasetenEvoSpark, purpose: str, body: dict[str, Any],
                  retry: bool = True) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    current_step.set(f"s1:{run.part}:{purpose}")
    start = run.mark()
    try:
        payload = await spark.chat(purpose, body, retry=retry)
        run.n += 1  # recordings elide long text: keep the full answer, so a runaway output can be diagnosed
        msg = (payload.get("choices") or [{}])[0].get("message") or {}
        w(run.dir / "content" / f"{run.n:02d}_{purpose}.txt", str(msg.get("content") or msg.get("tool_calls") or ""))
        return payload, None, run.since(start)
    except ChimeraError as e:
        detail = e.details.get("upstream_body") if e.details else None
        return None, f"{e.code.value}: {e.message} {json.dumps(detail)[:400] if detail else ''}", run.since(start)


def engine(run: Run) -> EvoEngine:
    return EvoEngine(build_services(run.settings))


def animal(eng: EvoEngine, name: str):
    a = eng.tax.resolve(name)
    if a is None:
        hits = eng.resolver.store.lookup(name)
        a = eng.tax.resolve(hits[0]["id"]) if hits else None
    if a is None:
        raise SystemExit(f"cannot resolve {name!r} offline")
    return a


def plan_body(eng: EvoEngine, model: str, sire: str, dam: str, mode: str):
    a, b = animal(eng, sire), animal(eng, dam)
    skel, r = eng.seed_plan(a, b, design_mode=mode)
    prompt = eng.plan_prompt(skel, PLAN_TASK)
    return live.build_plan_request(model, prompt), skel, r, prompt


def plan_verdict(eng: EvoEngine, payload: dict[str, Any], skel, r) -> dict[str, Any]:
    """The engine's own acceptance test for a model plan, plus which locked fields the model changed."""
    try:
        data = _message_json(payload)
    except ChimeraError as e:
        return {"accepted": False, "reason": f"unreadable: {e.message}"}
    sk = skel.model_dump()
    changed = [k for k in LOCKED if k in data and data[k] != sk[k]]
    try:
        plan = validate_plan({**live.parse_plan_response(payload, sk), "id": "pending"})
        v = eng._check(plan, r, final=False)
        if v:
            return {"accepted": False, "locked_changed": changed,
                    "reason": "; ".join(f"{x.card}: {x.detail}" for x in v)[:300]}
        eng.finish(plan, r)
    except (ValueError, TypeError, AssertionError) as e:
        return {"accepted": False, "locked_changed": changed, "reason": f"schema/validation: {str(e)[:300]}"}
    return {"accepted": True, "locked_changed": changed}


def recorded(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ part 2: Spark Open probes

TOOLS = [
    {"type": "function", "function": {
        "name": "resolve_animal", "description": "Look up one animal by its common name. Returns its id.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["name"],
                       "properties": {"name": {"type": "string", "description": "common name of one animal"}}}}},
    {"type": "function", "function": {
        "name": "run_audit", "description": "Audit whether a creature fused from two resolved animals can live. "
        "Needs both animal ids from resolve_animal. Returns an audit_id.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["sire_id", "dam_id", "mode"],
                       "properties": {"sire_id": {"type": "string"}, "dam_id": {"type": "string"},
                                      "mode": {"type": "string", "enum": ["realistic", "speculative", "mythic"]}}}}},
    {"type": "function", "function": {
        "name": "render", "description": "Render the audited creature. Needs the audit_id from run_audit. "
        "Returns an image_id.",
        "parameters": {"type": "object", "additionalProperties": False, "required": ["audit_id"],
                       "properties": {"audit_id": {"type": "string"}}}}},
]
TOOL_TASK = ("Make a realistic creature from an axolotl and a pangolin, with the axolotl as sire and the "
             "pangolin as dam. Resolve both animals, run the audit on the resolved pair, then render it. "
             "When the render is done, reply with the image id.")
FAKE_IDS = {"axolotl": "ambystoma_mexicanum", "pangolin": "manis_pentadactyla"}


def fake_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "resolve_animal":
        key = next((k for k in FAKE_IDS if k in str(args.get("name", "")).lower()), None)
        return {"id": FAKE_IDS[key], "status": "resolved"} if key else {"status": "not_found"}
    if name == "run_audit":
        ok = args.get("sire_id") == FAKE_IDS["axolotl"] and args.get("dam_id") == FAKE_IDS["pangolin"]
        return {"audit_id": "audit_7f3a" if ok else "audit_bad_ids", "breathing": "repaired", "feeding": "pass"}
    if name == "render":
        return {"image_id": "img_42c9" if args.get("audit_id") == "audit_7f3a" else "img_wrong_audit"}
    return {"error": "unknown tool"}


async def tool_probe(run: Run, spark: BasetenEvoSpark) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You operate a creature engine through tools. Call tools to do the work; "
                                      "use the ids the tools return."},
        {"role": "user", "content": TOOL_TASK}]
    turns, extra = [], {"parallel_tool_calls": True}
    for turn in range(1, 7):
        body = {"model": spark.model_id, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
                "temperature": 0, **extra}
        payload, err, attempts = await bt_call(run, spark, "probe_tools", body)
        if err and extra and turn == 1:  # parallel_tool_calls not accepted: say so, then try without it
            turns.append({"turn": turn, "error": err, "attempts": attempts, "note": "retrying without parallel_tool_calls"})
            extra = {}
            payload, err, attempts = await bt_call(run, spark, "probe_tools", {k: v for k, v in body.items()
                                                                               if k != "parallel_tool_calls"})
        if err or payload is None:
            turns.append({"turn": turn, "error": err, "attempts": attempts})
            break
        msg = payload["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        rec: dict[str, Any] = {"turn": turn, "finish_reason": payload["choices"][0].get("finish_reason"),
                               "attempts": attempts, "tool_calls": [], "text": (msg.get("content") or "")[:400]}
        messages.append({"role": "assistant", "content": msg.get("content"),
                         **({"tool_calls": calls} if calls else {})})
        for c in calls:
            fn = c["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
                bad_args = None
            except json.JSONDecodeError as e:
                args, bad_args = {}, str(e)
            result = fake_tool(fn["name"], args)
            rec["tool_calls"].append({"name": fn["name"], "arguments": args, "bad_arguments": bad_args,
                                      "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)})
        turns.append(rec)
        if not calls:
            break
    seq = [c["name"] for t in turns for c in t.get("tool_calls", [])]
    resolved = {c["arguments"].get("name", "").lower() for t in turns for c in t.get("tool_calls", [])
                if c["name"] == "resolve_animal"}
    audits = [c for t in turns for c in t.get("tool_calls", []) if c["name"] == "run_audit"]
    renders = [c for t in turns for c in t.get("tool_calls", []) if c["name"] == "render"]
    final_text = next((t["text"] for t in reversed(turns) if t.get("text")), "")
    checks = {
        "both_resolved": any("axolotl" in x for x in resolved) and any("pangolin" in x for x in resolved),
        "order_resolve_audit_render": bool(audits and renders) and seq.index("run_audit") > max(
            i for i, n in enumerate(seq) if n == "resolve_animal") and seq.index("render") > seq.index("run_audit"),
        "audit_used_returned_ids": bool(audits) and audits[0]["result"]["audit_id"] == "audit_7f3a",
        "audit_mode_realistic": bool(audits) and audits[0]["arguments"].get("mode") == "realistic",
        "render_used_audit_id": bool(renders) and renders[0]["result"]["image_id"] == "img_42c9",
        "parallel_calls_used": any(len(t.get("tool_calls", [])) > 1 for t in turns),
        "valid_json_arguments": all(not c["bad_arguments"] for t in turns for c in t.get("tool_calls", [])),
        "final_reply_has_image_id": "img_42c9" in final_text,
        "extra_calls": len(seq) - 4,
    }
    return {"sequence": seq, "turns": turns, "checks": checks,
            "parallel_tool_calls_param": "accepted" if extra else "rejected or not sent"}


REFUSAL_SET = [("tiger", "lion", "speculative"), ("lion", "goldfish", "mythic"),
               ("octopus", "eagle", "mythic"), ("moon_jellyfish", "lion", "speculative"),
               ("golden retriever", "woolly mammoth", "realistic")]


async def part_spark() -> None:
    run = Run("spark")
    spark = BasetenEvoSpark(run.settings)
    eng = engine(run)
    res: dict[str, Any] = {"model": spark.model_id, "endpoint": run.settings.baseten_base_url}

    # a) strict JSON: identify, traits (enums), audit
    print("a) strict JSON")
    ident_body = live.build_identify_request(spark.model_id, "axolotl", None)
    payload, err, att = await bt_call(run, spark, "probe_json_identify", ident_body, retry=False)
    if err and ("404" in err or "not_found" in err.lower() or "not found" in err.lower()):
        res["model_not_found"] = err
        print("MODEL NOT FOUND:", err[:300])
        run.finish(res)
        return
    a_rows = [{"call": "identify axolotl", "error": err, "attempts": att,
               **(json_report(payload, live.IDENTIFY_SCHEMA) if payload else {}),
               "parsed": live.parse_identify_response(payload) if payload else None}]
    traits_body = live.build_traits_request(spark.model_id, {"common_name": "axolotl",
                                                            "scientific_name": "Ambystoma mexicanum"})
    payload, err, att = await bt_call(run, spark, "probe_json_traits", traits_body)
    a_rows.append({"call": "learn traits axolotl (enum-heavy schema)", "error": err, "attempts": att,
                   **(json_report(payload, live.TRAITS_SCHEMA) if payload else {})})
    g_b = validate_plan(json.loads((E4 / "b_axolotl_x_pangolin_rerender" / "plan.json").read_text(encoding="utf-8")))
    from app.evolution.audit import plan_text
    audit_body = live.build_audit_request(spark.model_id, plan_text(g_b, eng.tax), ["feeding", "heat"])
    payload, err, att = await bt_call(run, spark, "probe_json_audit", audit_body)
    a_rows.append({"call": "audit feeding+heat (axolotl x pangolin)", "error": err, "attempts": att,
                   **(json_report(payload, live.AUDIT_SCHEMA) if payload else {}),
                   "parsed": live.parse_audit_response(payload, ["feeding", "heat"]) if payload else None})
    res["a_strict_json"] = a_rows

    # b) image input: identify from a photo, open critic, both on the E4 lion x eagle render
    print("b) image input")
    img = (E4 / "c_lion_x_eagle" / "image.webp").read_bytes()
    b_rows = []
    for purpose, body, schema, parse in [
        ("probe_image_identify", live.build_identify_request(spark.model_id, None, img), live.IDENTIFY_SCHEMA,
         live.parse_identify_response),
        ("probe_image_critic", live.build_critic_request(spark.model_id, img), live.CRITIC_SCHEMA,
         live.parse_critic_response)]:
        payload, err, att = await bt_call(run, spark, purpose, body)
        b_rows.append({"call": purpose, "error": err, "attempts": att,
                       **(json_report(payload, schema) if payload else {}),
                       "parsed": parse(payload) if payload and not err else None})
    res["b_image_input"] = b_rows

    # c) tool calling
    print("c) tool calling")
    res["c_tools"] = await tool_probe(run, spark)

    # d) refusal check on five real planning prompts
    print("d) refusals")
    d_rows = []
    for sire, dam, mode in REFUSAL_SET:
        body, skel, r, prompt = plan_body(eng, spark.model_id, sire, dam, mode)
        payload, err, att = await bt_call(run, spark, "probe_refusal_plan", body)
        d_rows.append({"pair": f"{sire} x {dam}", "mode": mode, "route": r.mode, "prompt_chars": len(prompt),
                       "error": err, "attempts": att, "refusal": refusal_of(payload, err),
                       **(json_report(payload, live.PLAN_SCHEMA) if payload else {}),
                       **({"plan": plan_verdict(eng, payload, skel, r)} if payload else {})})
        print(" ", sire, "x", dam, mode, "->", d_rows[-1]["refusal"] or "no refusal",
              d_rows[-1].get("plan", {}).get("accepted"))
    res["d_refusals"] = {"rows": d_rows, "refusals": sum(1 for x in d_rows if x["refusal"])}
    run.finish(res)


# ------------------------------------------------------------------ part 3: parity with recorded Meta calls

PLAN_RECS = [("b axolotl x pangolin realistic", "axolotl", "pangolin", "realistic",
              E4 / "raw_rerender" / "evo_plan-01.json", E4 / "b_axolotl_x_pangolin_rerender"),
             ("c lion x eagle mythic", "lion", "eagle", "mythic", E4 / "raw" / "evo_plan-02.json",
              E4 / "c_lion_x_eagle"),
             ("d rhinoceros beetle x brown bear speculative", "rhinoceros beetle", "brown bear", "speculative",
              E4 / "raw" / "evo_plan-03.json", E4 / "d_rhinoceros_beetle_x_brown_bear")]
POLISH_RECS = [("b axolotl x pangolin (E4 run 1)", E4 / "raw" / "evo_polish-01.json", E4 / "b_axolotl_x_pangolin"),
               ("c lion x eagle", E4 / "raw" / "evo_polish-02.json", E4 / "c_lion_x_eagle")]
IDENT_RECS = [("woolly mammoth", E4 / "raw" / "evo_identify-02.json"),
              ("pangolin (ambiguous)", E4 / "raw" / "evo_identify-03.json")]
CHECK_RECS = [("b axolotl x pangolin (E4 run 1)", E4 / "raw" / "evo_checklist-01.json", E4 / "b_axolotl_x_pangolin"),
              ("c lion x eagle", E4 / "raw" / "evo_checklist-03.json", E4 / "c_lion_x_eagle"),
              ("d rhinoceros beetle x brown bear", E4 / "raw" / "evo_checklist-05.json",
               E4 / "d_rhinoceros_beetle_x_brown_bear")]
ELIDED_LEN = re.compile(r"<elided> \((\d+) chars\)")


def with_model(req: dict[str, Any], model: str) -> dict[str, Any]:
    return {**json.loads(json.dumps(req)), "model": model}


async def part_parity() -> None:
    run = Run("parity")
    spark = BasetenEvoSpark(run.settings)
    eng = engine(run)
    res: dict[str, Any] = {"model": spark.model_id, "plans": [], "polish": [], "resolver": [], "checklist": []}

    for label, sire, dam, mode, rec_path, folder in PLAN_RECS:
        rec = recorded(rec_path)
        body, skel, r, prompt = plan_body(eng, spark.model_id, sire, dam, mode)
        m = ELIDED_LEN.search(str(rec["request"]["messages"][1]["content"]))
        meta_note = json.loads((folder / "judge.json").read_text(encoding="utf-8")).get("model_plan")
        if meta_note in (None, "not kept in the cached document"):
            meta_note = json.loads((E4 / "offline_reconstruction.json").read_text(encoding="utf-8")).get(
                folder.name, {}).get("model_plan")
        body["temperature"] = rec["request"].get("temperature", body["temperature"])
        payload, err, att = await bt_call(run, spark, "parity_plan", body)
        row = {"case": label, "rebuilt_prompt_chars": len(prompt),
               "recorded_prompt_chars": int(m.group(1)) if m else None, "meta_plan": meta_note,
               "error": err, "attempts": att, "refusal": refusal_of(payload, err)}
        row["request_identical_length"] = row["rebuilt_prompt_chars"] == row["recorded_prompt_chars"]
        if payload:
            row.update(json=json_report(payload, live.PLAN_SCHEMA), baseten_plan=plan_verdict(eng, payload, skel, r))
            w(run.dir / "plans" / f"{folder.name}.json", _message_json(payload))
        res["plans"].append(row)
        print("plan", label, "->", row.get("baseten_plan"))

    for label, rec_path, folder in POLISH_RECS:
        rec = recorded(rec_path)
        g = validate_plan(json.loads((folder / "plan.json").read_text(encoding="utf-8")))
        original = rec["request"]["messages"][1]["content"]
        meta_text = live.parse_polish_response(rec["response"])
        payload, err, att = await bt_call(run, spark, "parity_polish", with_model(rec["request"], spark.model_id))
        row: dict[str, Any] = {"case": label, "error": err, "attempts": att,
                               "meta": {"accepted": accept_polish(original, meta_text, g, eng.tax)[1] is None,
                                        "reason": accept_polish(original, meta_text, g, eng.tax)[1],
                                        "chars": len(meta_text)}, "original_chars": len(original)}
        if payload:
            text = live.parse_polish_response(payload)
            reason = accept_polish(original, text, g, eng.tax)[1]
            row["baseten"] = {"accepted": reason is None, "reason": reason, "chars": len(text),
                              "json": json_report(payload, live.POLISH_SCHEMA)}
            w(run.dir / "polish" / f"{folder.name}.txt", text)
        res["polish"].append(row)
        print("polish", label, "->", row.get("baseten", {}).get("accepted"), row["meta"]["accepted"])

    for label, rec_path in IDENT_RECS:
        rec = recorded(rec_path)
        meta = live.parse_identify_response(rec["response"])
        payload, err, att = await bt_call(run, spark, "parity_identify", with_model(rec["request"], spark.model_id))
        row = {"case": label, "error": err, "attempts": att, "meta": meta}
        if payload:
            bt = live.parse_identify_response(payload)
            row.update(baseten=bt, json=json_report(payload, live.IDENTIFY_SCHEMA),
                       same_kind=bt["kind"] == meta["kind"],
                       same_scientific_name=bt["scientific_name"].lower() == meta["scientific_name"].lower())
        res["resolver"].append(row)
        print("identify", label, "->", row.get("same_kind"), row.get("same_scientific_name"))

    for label, rec_path, folder in CHECK_RECS:
        rec = recorded(rec_path)
        req = with_model(rec["request"], spark.model_id)
        img = (folder / "image.webp").read_bytes()
        req["messages"][1]["content"][1]["image_url"]["url"] = _data_url(img)
        text = req["messages"][1]["content"][0]["text"]
        items = [ln.split(". ", 1)[1] for ln in text.split("\n") if re.match(r"^\d+\. ", ln)]
        choices = req["response_format"]["json_schema"]["schema"]["properties"]["choice"]["enum"]
        meta = live.parse_checklist_response(rec["response"], items, choices)
        payload, err, att = await bt_call(run, spark, "parity_checklist", req)
        row = {"case": label, "items": items, "error": err, "attempts": att,
               "meta": {"answers": [a["answer"] for a in meta["answers"]], "choice": meta["choice"],
                        "creatures": meta["creatures"], "animals": meta["animals"]}}
        if payload:
            bt = live.parse_checklist_response(payload, items, choices)
            row["baseten"] = {"answers": [a["answer"] for a in bt["answers"]], "choice": bt["choice"],
                              "creatures": bt["creatures"], "animals": bt["animals"], "notes": bt["notes"],
                              "json": json_report(payload, req["response_format"]["json_schema"]["schema"])}
            row["agree"] = [m == b for m, b in zip(row["meta"]["answers"], row["baseten"]["answers"], strict=True)]
            row["items_echoed_in_order"] = [str(a.get("item")) for a in (_message_json(payload).get("answers") or [])
                                            if isinstance(a, dict)] == items
        res["checklist"].append(row)
        print("checklist", label, "->", row.get("agree"))
    agree = [x for r in res["checklist"] for x in r.get("agree", [])]
    res["checklist_agreement"] = f"{sum(agree)}/{len(agree)}"
    run.finish(res)


# ------------------------------------------------------------------ part 4: Muse Image references and edit

PORTRAIT = ("A plain natural history illustration of one {name} ({sci}), the whole animal, side three-quarter view, "
            "plain light background. One animal only.")


async def judge_image(eng: EvoEngine, img: bytes, plan_dir: Path) -> dict[str, Any]:
    g = validate_plan(json.loads((plan_dir / "plan.json").read_text(encoding="utf-8")))
    r = route(eng.tax.animals[g.parents.sire], eng.tax.animals[g.parents.dam], eng.tax, g.design_mode == "mythic")
    v = await judge(img, g, r, eng.tax, eng.spark, eng.segmenter, eng.meter)
    return {k: v.get(k) for k in ("scores", "checklist", "critic", "critic_thumbnail", "forced_choice",
                                  "open_critic", "third_animal", "mask")}


def similarity(a: bytes, b: bytes) -> dict[str, float]:
    """Same-creature evidence for the edit turn: mean absolute pixel difference and changed-area share."""
    with Image.open(io.BytesIO(a)) as x, Image.open(io.BytesIO(b)) as y:
        x, y = x.convert("L").resize((256, 256)), y.convert("L").resize((256, 256))
        diff = [abs(p - q) for p, q in zip(x.tobytes(), y.tobytes(), strict=True)]
    return {"mean_abs_diff_0_255": round(sum(diff) / len(diff), 1),
            "changed_share_over_32": round(sum(1 for d in diff if d > 32) / len(diff), 3)}


async def part_image() -> None:
    run = Run("image")
    eng = engine(run)
    res: dict[str, Any] = {"renders": []}
    seg = eng.segmenter

    async def gen(label: str, prompt: str, refs: list[bytes], prev: str | None = None):
        current_step.set(f"s1:image:{label}")
        start = run.mark()
        t = time.perf_counter()
        try:
            img = await eng.renderer.generate(prompt, refs, "1:1", prev)
        except ChimeraError as e:
            res["renders"].append({"render": label, "error": f"{e.code.value}: {e.message}",
                                   "details": e.details, "attempts": run.since(start)})
            return None
        w(run.dir / f"{label}.webp", img.data)
        res["renders"].append({"render": label, "prompt": prompt, "references": len(refs),
                               "previous_response_id": prev, "response_id": img.response_id,
                               "seconds": round(time.perf_counter() - t, 1), "attempts": run.since(start)})
        return img

    # a) parent portraits, then the E4 compiled prompt with both portraits as references
    portraits = {}
    for key, name, sci in [("axolotl", "axolotl", "Ambystoma mexicanum"),
                           ("pangolin", "Chinese pangolin", "Manis pentadactyla")]:
        img = await gen(f"portrait_{key}", PORTRAIT.format(name=name, sci=sci), [])
        if img:
            portraits[key] = img.data
            current_step.set(f"s1:image:portrait_{key}:judge")
            items = [f"a {name}", "one animal only", "plain light background"]
            items.insert(1, "external gills on the sides of the head" if key == "axolotl" else "overlapping scales")
            start = run.mark()
            check = await eng.spark.checklist(img.data, items, [name.lower(), "other"])
            mask = await seg.segment(img.data, "animal")
            w(run.dir / f"portrait_{key}_mask.png", mask)
            res["renders"][-1]["judge"] = {"checklist": check, "mask": mask_stats(mask), "attempts": run.since(start)}
    compiled = (E4 / "b_axolotl_x_pangolin_rerender" / "prompt_compiled.txt").read_text(encoding="utf-8")
    if len(portraits) == 2:
        img = await gen("ref_axolotl_x_pangolin", compiled, [portraits["axolotl"], portraits["pangolin"]])
        if img:
            current_step.set("s1:image:ref:judge")
            start = run.mark()
            v = await judge_image(eng, img.data, E4 / "b_axolotl_x_pangolin_rerender")
            res["renders"][-1]["judge"] = {**v, "attempts": run.since(start)}
            res["renders"][-1]["text_only_baseline"] = json.loads(
                (E4 / "b_axolotl_x_pangolin_rerender" / "judge.json").read_text(encoding="utf-8"))["scores"]
    else:
        res["renders"].append({"render": "ref_axolotl_x_pangolin", "skipped": "a portrait failed"})

    # b) edit turn on the E4 beetle x bear render
    prev = recorded(E4 / "raw" / "text_to_image-03.json")["response"]["id"]
    d_dir = E4 / "d_rhinoceros_beetle_x_brown_bear"
    img = await gen("edit_beetle_x_bear", "Remove the beetle bodies on the shoulders; keep everything else.", [], prev)
    if img:
        current_step.set("s1:image:edit:judge")
        start = run.mark()
        v = await judge_image(eng, img.data, d_dir)
        res["renders"][-1]["judge"] = {**v, "attempts": run.since(start)}
        res["renders"][-1]["original_scores"] = json.loads((d_dir / "judge.json").read_text(encoding="utf-8"))["scores"]
        res["renders"][-1]["similarity_to_original"] = similarity((d_dir / "image.webp").read_bytes(), img.data)
    run.finish(res)


# ------------------------------------------------------------------ part 5: SAM part prompts

SAM_CASES = [("c_lion_x_eagle", "wings", "present"), ("c_lion_x_eagle", "eagle head", "present"),
             ("c_lion_x_eagle", "lion legs", "present"),
             ("b_axolotl_x_pangolin_rerender", "external gills", "absent"),
             ("d_rhinoceros_beetle_x_brown_bear", "beetle", "unknown")]


def overlay(image: bytes, mask: bytes) -> bytes:
    with Image.open(io.BytesIO(image)) as im, Image.open(io.BytesIO(mask)) as m:
        base = im.convert("RGB")
        tint = Image.new("RGB", base.size, (255, 0, 160))
        out = Image.composite(Image.blend(base, tint, 0.55), base, m.convert("L").resize(base.size))
        buf = io.BytesIO()
        out.save(buf, "PNG")
        return buf.getvalue()


def boxes(payload: dict[str, Any]) -> list[list[int]]:
    import meta_sam_parser as msp

    parser = msp.image_segmentation_format().create_parser()
    parser.push(live.sam_text(payload), emit=False)
    out = []
    for rec in parser.finish(msp.CompletedOutcome()).result.records:
        if isinstance(rec, msp.SegmentationMaskRecord):
            b = rec.bounds
            out.append([round(b.left), round(b.top), round(b.right), round(b.bottom)])
    return out


async def part_sam() -> None:
    run = Run("sam")
    eng = engine(run)
    rows = []
    for folder, label, expect in SAM_CASES:
        img = (E4 / folder / "image.webp").read_bytes()
        current_step.set(f"s1:sam:{folder}:{label}")
        start = run.mark()
        try:
            payload = await eng.segmenter.segment_raw(img, label)
        except ChimeraError as e:
            rows.append({"image": folder, "prompt": label, "expected": expect, "error": f"{e.code.value}: {e.message}",
                         "attempts": run.since(start)})
            continue
        with Image.open(io.BytesIO(img)) as im:
            size = im.size
        mask = live.parse_sam_response(payload, *size)
        slug = f"{folder}__{label.replace(' ', '_')}"
        w(run.dir / f"{slug}_mask.png", mask)
        w(run.dir / f"{slug}_overlay.png", overlay(img, mask))
        stats = mask_stats(mask)
        rows.append({"image": folder, "prompt": label, "expected": expect, "objects": len(boxes(payload)),
                     "boxes": boxes(payload), "fill": stats.get("fill"), "mask": stats,
                     "text_chars": len(live.sam_text(payload)), "attempts": run.since(start)})
        print(folder, label, "->", rows[-1]["objects"], "objects, fill", stats.get("fill"))
    run.finish({"cases": rows})


PARTS = {"spark": part_spark, "parity": part_parity, "image": part_image, "sam": part_sam}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PARTS:
        sys.exit(f"usage: s1_probe.py {{{'|'.join(PARTS)}}}")
    asyncio.run(PARTS[sys.argv[1]]())
