"""Builds the creature spec (via the planning model) and the Muse Image prompt.

The prompt template is `compile_template.txt`, editable without code changes.
"""

from __future__ import annotations

from pathlib import Path

from app.errors import ChimeraError
from app.models.schemas import CreatureSpec, ErrorCode, FusionPlan, ParentInfo, PartDonors
from app.pipeline.context import RunContext
from app.pipeline.retry import call_with_retry

TEMPLATE_PATH = Path(__file__).with_name("compile_template.txt")
PART_WORDS = {"head": "head", "body": "torso", "limbs": "limbs", "covering": "skin covering", "tail": "tail"}


def _join(words: list[str]) -> str:
    if not words:
        return "overall colouring only"
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def build_prompt(spec_parts: dict[str, str], names: dict[str, str], body_plan: str, constraints: list[str]) -> str:
    a_parts = [PART_WORDS[p] for p, donor in spec_parts.items() if donor == "A"]
    b_parts = [PART_WORDS[p] for p, donor in spec_parts.items() if donor == "B"]
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(
        a_name=names["A"], b_name=names["B"], a_parts=_join(a_parts), b_parts=_join(b_parts),
        body_plan=body_plan, constraints=" ".join(constraints),
    ).strip()


def planning_context(ctx: RunContext) -> dict[str, object]:
    readings, matches = ctx.state["readings"], ctx.state["matches"]
    return {
        "readings": {k: v.dump() for k, v in readings.items()},
        "matches": {k: (v.dump() if v else None) for k, v in matches.items()},
        "real_hybrid": ctx.state["real_hybrid"].dump() if ctx.state.get("real_hybrid") else None,
        "rule_warnings": [w.dump() for w in ctx.state.get("warnings", [])],
        "allowed_body_plans": ["quadruped", "biped", "avian", "aquatic", "serpentine", "cephalopod", "insectoid"],
        # Parts the user pinned to a parent. The plan must keep these exactly.
        "donor_pins": ctx.state.get("donor_pins", {}),
    }


def pinned_plan(ctx: RunContext, pins: dict[str, str], names: dict[str, str]) -> FusionPlan:
    """Every part pinned by the user: no planning call needed (saves a vision call)."""
    readings, matches = ctx.state["readings"], ctx.state["matches"]
    body = pins["body"]
    match = matches.get(body)
    plan = (match.facts.get("body_plan") if match else None) or readings[body].body_plan or "quadruped"
    head, tail = names[pins["head"]].split()[-1], names[body].split()[-1]
    return FusionPlan(
        body_plan=plan,
        part_donors=PartDonors(**pins),
        rationale="Every part was chosen by you; the body plan follows the body donor.",
        name_suggestion=f"{head[:3].title()}{tail[-4:].lower()}",
    )


async def run(ctx: RunContext) -> str:
    s = ctx.services.settings
    readings, matches = ctx.state["readings"], ctx.state["matches"]
    names = {
        slot: (matches[slot].common_name if matches.get(slot) else readings[slot].common_name) or f"animal {slot}"
        for slot in ("A", "B")
    }
    pins: dict[str, str] = dict(ctx.state.get("donor_pins", {}))
    if len(pins) == len(PART_WORDS):
        plan = pinned_plan(ctx, pins, names)
    else:
        plan = await call_with_retry(
            lambda: ctx.services.vision.plan_fusion(planning_context(ctx)),
            timeout=s.identify_timeout_seconds,
            base_delay=s.retry_base_seconds,
            max_attempts=s.retry_max_attempts,
            before_attempt=lambda _n: ctx.use_vision(),
            can_retry=ctx.can_use_vision,
        )
        # Pins always win, even if the model disagreed.
        if pins:
            plan.part_donors = plan.part_donors.model_copy(update=pins)
    donor_source = {part: ("user" if part in pins else "model") for part in PART_WORDS}
    constraints = []
    if ctx.state.get("real_hybrid"):
        constraints.append(f"Stay close to the documented {ctx.state['real_hybrid'].name}, a real hybrid of these parents.")
    for w in ctx.state.get("warnings", []):
        if w.severity == "warning":
            constraints.append(w.message)
    try:
        prompt = build_prompt(plan.part_donors.model_dump(), {k: v.lower() for k, v in names.items()},
                              plan.body_plan, constraints)
        spec = CreatureSpec(
            parents=[
                ParentInfo(slot=i.slot, asset_id=i.asset_id, reading=readings[i.slot],  # type: ignore[arg-type]
                           match=matches.get(i.slot))
                for i in ctx.inputs
            ],
            real_hybrid=ctx.state.get("real_hybrid"),
            body_plan=plan.body_plan,
            part_donors=plan.part_donors,
            rationale=plan.rationale,
            name=plan.name_suggestion,
            warnings=ctx.state.get("warnings", []),
            prompt=prompt,
            model={"vision": ctx.services.vision.model_id, "image": ctx.services.image_gen.model_id},
            donor_source=donor_source,
        )
    except (KeyError, ValueError) as exc:
        raise ChimeraError(ErrorCode.INTERNAL, "Could not build the creature plan.") from exc
    ctx.state["spec"] = spec
    pinned = f", {len(pins)} part{'s' if len(pins) != 1 else ''} chosen by you" if pins else ""
    return f"{plan.body_plan.capitalize()} body, head from {plan.part_donors.head}{pinned}"
