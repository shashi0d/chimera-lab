"""S2 part 3: the plan as small typed operations (the step-3 agent's plan tools; ROADMAP 4 and 5b).

The agent never writes a whole plan (S1: Spark Open runs away on long JSON). It edits a `PlanSession` through six
operations, each validated on its own:

    set_host(animal)                     the frame parent (chimera and mythic routes)
    set_region(region, donor, operator)  head, tail, forelimbs, or a surface region (PATCH / OVERLAY / PICK)
    set_habitat(name)                    a profiled habitat
    set_mode(mode)                       realistic | speculative | mythic
    add_license(rule, compensation)      a bendable rule (R9 3.2) the plan really bends, within the mode's budget
    drop_part(part, reason)              remove a donor part

S3b adds four transfer operations (RC-R10-15, RC-R10-16; transfer.py validates them):

    set_transfer_class(feature, cls)     material | homologous | non_homologous
    set_extent(feature, extent, reason)  a covering's body zones, with a functional reason
    connect_features(a, b)               two features of one donor system grow from each other
    set_identity_cues(feature, cues)     the positive form description that makes a part the donor's

S3c adds (owner decision D4):

    set_identity_part(donor, part, reason)  the donor's one identity part, among its own diagnostic parts

S5 adds (D1):

    set_covering_material_only(reason)   the host keeps its own covering; the donor gives only its color, gloss,
                                         texture and pattern on it (discrete identity parts are kept)

A session stores the accepted operations as intents and rebuilds the plan from the code skeleton on every call
(seed_plan, the intents, then finish), so code always fills card_trace, labels, checks, audit, licenses,
render_details and the silhouette. An operation that fails validation, or whose result breaks a hard card, is
not applied: the call returns structured errors (code, message, field, hint, valid values) the agent can act on.
The legacy full-plan path (engine.fuse with a model-written plan) is unchanged.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.errors import ChimeraError
from app.evolution.audit import DROPPED, _drop, donor_parts
from app.evolution.data import Animal, config, norm
from app.evolution.fiction import bendable, budget, never_licensable, respiratory_claim_error
from app.evolution.genome import DESIGN_MODES, SURFACE_TAGS, Genome, LimbSlot, Trait
from app.evolution.judge import generated_checklist
from app.evolution.parts import best_part, dorsal_wings, flies_with_wings, specs
from app.evolution.prompt import has_franchise
from app.evolution.route import Route, host_tie, is_real_hybrid
from app.evolution.transfer import TransferError
from app.models.schemas import ErrorCode

SURFACE_REGIONS = ("neck", "forequarters", "back", "flanks", "belly", "hindquarters", "legs")
REGION_OPERATORS = {"head": ("PICK",), "tail": ("PICK",), "forelimbs": ("PICK",),
                    **{r: ("PATCH", "OVERLAY", "PICK") for r in SURFACE_REGIONS}}
OPS = ("set_host", "set_region", "set_habitat", "set_mode", "add_license", "drop_part", "set_transfer_class",
       "set_extent", "connect_features", "set_identity_cues", "set_identity_part", "set_covering_material_only")
TRANSFER_OPS = (*OPS[6:10], "set_covering_material_only")
MAX_COMPENSATION = 240


@dataclass
class OpError:
    code: str
    message: str
    field: str | None = None
    hint: str = ""
    valid: list[str] | None = None


@dataclass
class OpResult:
    ok: bool
    op: str
    errors: list[OpError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        return {"ok": self.ok, "op": self.op, "errors": [asdict(e) for e in self.errors], "warnings": self.warnings,
                "summary": self.summary}


class OpRejected(Exception):
    def __init__(self, *errors: OpError) -> None:
        super().__init__("; ".join(e.message for e in errors))
        self.errors = list(errors)


class PlanSession:
    """A plan under construction by typed operations. `plan` is always a finished, hard-card-clean plan."""

    def __init__(self, engine: Any, sire: Animal, dam: Animal, mode: str = "speculative", seed: int = 0) -> None:
        if mode not in DESIGN_MODES:
            raise ChimeraError(ErrorCode.VALIDATION_FAILED, f"Unknown mode {mode!r}.",
                               details={"modes": list(DESIGN_MODES)})
        self.engine, self.sire, self.dam, self.seed = engine, sire, dam, seed
        self.mode = mode
        self.host_pick: str | None = None
        self.habitat: str | None = None
        self.regions: list[dict[str, str]] = []  # set_region intents, in order
        self.licenses: list[tuple[str, str]] = []  # add_license intents (bendable id, compensation)
        self.drops: list[dict[str, str]] = []  # drop_part intents
        self.transfer_edits: list[dict[str, Any]] = []  # S3b transfer intents, re-applied on every build
        self.identity_picks: dict[str, tuple[str, str]] = {}  # S3c (D4): donor id -> (part, reason)
        self.log: list[dict[str, Any]] = []
        self.plan, self.route = self._build()
        self.tie: list[str] = host_tie(self.route)  # S3c (D2): a structural tie; the host must be chosen

    # ------------------------------------------------------------------ public

    def apply(self, op: str, args: dict[str, Any]) -> OpResult:
        """Run one operation. On any error the session is unchanged."""
        if op not in OPS:
            return self._result(op, args, [OpError("unknown_op", f"no operation {op!r}", hint="use one of the listed "
                                                   "operations", valid=list(OPS))])
        saved = self._state()
        try:
            warnings = getattr(self, f"_{op}")(**args) or []
            plan, r = self._build()
            if v := self.engine._check(plan, r):
                raise OpRejected(*[OpError("hard_card", f"{x.card}: {x.detail}", hint="the result breaks a hard rule "
                                           "card; change the operation or drop the part involved") for x in v])
        except OpRejected as e:
            self._restore(saved)
            return self._result(op, args, e.errors)
        except TransferError as e:
            self._restore(saved)
            return self._result(op, args, [OpError(e.code, e.message, e.field, e.hint, e.valid)])
        except TypeError as e:  # wrong or missing arguments
            self._restore(saved)
            return self._result(op, args, [OpError("bad_arguments", str(e)[:200], hint=f"see the {op} signature")])
        except (ValueError, AssertionError) as e:
            self._restore(saved)
            return self._result(op, args, [OpError("invalid_plan", str(e)[:300], hint="the plan could not be built "
                                                   "with this operation; try another value")])
        self.plan, self.route = plan, r
        return self._result(op, args, [], warnings)

    def summary(self) -> dict[str, Any]:
        g, tax = self.plan, self.engine.tax
        name = lambda i: tax.animals[i].common_name if i else None  # noqa: E731
        surf = g.traits["coat_texture"]
        return {
            "plan_id": g.id, "route": g.mode, "design_mode": g.design_mode, "host": name(g.host),
            "host_tie": ([name(i) for i in self.tie] if self.tie and self.host_pick is None else None),
            "identity_parts": [{"donor": name(p.donor), "part": p.part, "from_trait": p.feature, "source": p.source,
                                "set_by": p.set_by} for p in g.identity_parts],
            "habitat": g.habitat.name, "silhouette": g.silhouette, "labels": g.labels,
            "licenses": [{"rule": x.id, "card": x.card, "compensation": x.compensation} for x in g.licenses],
            "license_budget": budget(g.design_mode),
            "parts": [p for _w, p in donor_parts(g)] + [f"wings ({k})" for k, s in
                                                         (("forelimbs", g.limb_plan.forelimbs),
                                                          ("extra pair", g.limb_plan.extra_wings))
                                                         if s and s.kind == "wings" and s.donor and s.donor != g.host],
            "patches": {"donor": name(surf.donor) if isinstance(surf.donor, str) else None,
                        "regions": list(surf.region or [])} if surf.op == "PATCH" else None,
            "dropped": [f[len(DROPPED):] for f in g.traits["body"].flags if f.startswith(DROPPED)],
            "audit": {i.function: i.result for i in g.audit},
            "checklist_preview": generated_checklist(g, tax),
            "transfers": [{"feature": t.feature, "class": t.cls, "anchor": t.anchor, "extent": t.extent,
                           "extent_reason": t.extent_reason, "connects": t.connects, "identity_cues": t.identity_cues,
                           "form": t.form, "set_by": t.set_by} for t in g.transfers],
        }

    # ------------------------------------------------------------------ operations

    def _set_host(self, animal: str) -> list[str]:
        if self.route.mode == "hybrid":
            raise OpRejected(OpError("not_allowed", "a hybrid has no single host frame", field="animal",
                                     hint="set_host works on chimera and mythic routes"))
        slot = self._parent_slot(animal, "animal")
        self.host_pick = slot
        dropped = [r for r in self.regions if self._parent(r["donor"]) == self._slot_animal(slot).id
                   and r["operator"] in ("PATCH", "OVERLAY")]
        self.regions = [r for r in self.regions if r not in dropped]
        return [f"set_region {r} no longer applies (the donor is now the host) and was removed" for r in dropped]

    def _set_region(self, region: str, donor: str, operator: str) -> list[str]:
        region, operator = region.strip().lower(), operator.strip().upper()
        if region not in REGION_OPERATORS:
            raise OpRejected(OpError("unknown_region", f"no region {region!r}", field="region",
                                     valid=list(REGION_OPERATORS)))
        if operator not in REGION_OPERATORS[region]:
            raise OpRejected(OpError("bad_operator", f"{operator} is not allowed on {region}", field="operator",
                                     valid=list(REGION_OPERATORS[region])))
        did = self._parent(donor, "donor")
        host = self.plan.host or self.sire.id
        if is_real_hybrid(self.route):
            raise OpRejected(OpError("not_allowed", "a documented hybrid's traits are fixed by its known-pair data",
                                     field="region", hint="change the mode or habitat instead"))
        if self.route.mode == "hybrid" and region not in ("head", "tail"):
            raise OpRejected(OpError("not_allowed", f"a hybrid blends its parents; {region} takes no donor patch",
                                     field="region", valid=["head", "tail"]))
        if region in SURFACE_REGIONS:
            if operator in ("PATCH", "OVERLAY") and did == host:
                raise OpRejected(OpError("donor_is_host", f"the host cannot {operator} its own body", field="donor",
                                         hint="name the other parent, or use PICK with the host to clear a region"))
            if operator == "PICK" and did != host:
                raise OpRejected(OpError("pick_needs_host", "PICK on a surface region gives it back to the host",
                                         field="donor", hint=f"use donor {self.engine.tax.animals[host].common_name!r}"
                                         " or PATCH to put the other parent there"))
            if operator == "OVERLAY" and not config()["coat_patterns"].get(did):
                raise OpRejected(OpError("no_pattern", f"the {self.engine.tax.animals[did].common_name} has no coat "
                                         "pattern to overlay", field="operator", valid=["PATCH"]))
            if operator == "PATCH":
                cur = set(self._patch_regions())
                if region not in cur and len(cur) >= config()["thresholds"]["max_patches"]:
                    raise OpRejected(OpError("too_many_patches", f"at most {config()['thresholds']['max_patches']} "
                                             "patch regions (RC-R5-03)", field="region", valid=sorted(cur),
                                             hint="give one region back with PICK first"))
        if region == "tail" and did != host:
            animal = self.engine.tax.animals[did]
            if best_part(animal, ("tail",)) is None:
                raise OpRejected(OpError("no_such_part", f"the {animal.common_name} has no tail part in its class "
                                         "list", field="donor", valid=[s.part for s in specs(animal)]))
        if region == "forelimbs" and did != host and not flies_with_wings(self.engine.tax.animals[did]):
            raise OpRejected(OpError("no_such_part", "only a wing-bearing donor can change the forelimbs",
                                     field="donor", hint="forelimbs from the host are the default"))
        self.regions = [r for r in self.regions if r["region"] != region] + [
            {"region": region, "donor": did, "operator": operator}]
        return []

    def _set_habitat(self, name: str) -> list[str]:
        valid = list(config()["habitat_profiles"])
        if norm(name) not in [norm(h) for h in valid]:
            raise OpRejected(OpError("unknown_habitat", f"no habitat profile {name!r}", field="name", valid=valid))
        self.habitat = next(h for h in valid if norm(h) == norm(name))
        return []

    def _set_mode(self, mode: str) -> list[str]:
        if mode not in DESIGN_MODES:
            raise OpRejected(OpError("unknown_mode", f"no mode {mode!r}", field="mode", valid=list(DESIGN_MODES)))
        self.mode = mode
        warns = []
        if len(self.licenses) > budget(mode):
            warns.append(f"{mode} allows {budget(mode)} license(s): the extra requests were removed")
            self.licenses = self.licenses[:budget(mode)]
        return warns

    def _add_license(self, rule: str, compensation: str) -> list[str]:
        spec = bendable()
        by_card = {b["card"]: k for k, b in spec.items()}
        rid = rule if rule in spec else by_card.get(rule)
        if rule in never_licensable():
            raise OpRejected(OpError("never_licensable", f"{rule} is an honesty or believability-floor rule",
                                     field="rule", hint="these can never be bent, in any mode"))
        if rid is None:
            raise OpRejected(OpError("not_bendable", f"{rule!r} is not a bendable rule (R9 3.2)", field="rule",
                                     valid=list(spec)))
        needs = self._needs()
        if rid not in needs:
            raise OpRejected(OpError("not_needed", f"the plan does not bend {rid}", field="rule",
                                     valid=sorted(needs) or None, hint="license only a rule the plan really bends"))
        comp = (compensation or "").strip()
        if not comp or len(comp) > MAX_COMPENSATION or has_franchise(comp):
            raise OpRejected(OpError("bad_compensation", "a license needs a short, visible compensation "
                                     f"(1 to {MAX_COMPENSATION} characters, no franchise names)", field="compensation",
                                     hint=f"for example: {spec[rid]['compensation']}"))
        if why := respiratory_claim_error(comp, self.plan, self.engine.tax):  # S3c: from the donor's own traits
            raise OpRejected(OpError("not_a_donor_trait", why, field="compensation",
                                     hint="name only features the donor's resolved traits include"))
        held = [x for x, _c in self.licenses if x != rid]
        if len(held) + 1 > budget(self.mode):
            raise OpRejected(OpError("over_budget", f"{self.mode} mode allows {budget(self.mode)} license(s)",
                                     field="rule", valid=held, hint="drop a part, or set_mode mythic"))
        self.licenses = [(x, c) for x, c in self.licenses if x != rid] + [(rid, comp)]
        return []

    def _drop_part(self, part: str, reason: str) -> list[str]:
        if not (reason or "").strip():
            raise OpRejected(OpError("missing_reason", "say why the part is dropped", field="reason",
                                     hint="one short sentence; it is logged with the plan"))
        current = self.summary()["parts"]
        hit = next((p for p in current if norm(part) in norm(p)), None)
        if hit is None:
            raise OpRejected(OpError("no_such_part", f"the plan has no part matching {part!r}", field="part",
                                     valid=current))
        self.drops = [d for d in self.drops if d["part"] != hit] + [{"part": hit, "reason": reason.strip()}]
        return []

    # ------------------------------------------------------------------ build

    def _transfer(self, op: str, **args: Any) -> list[str]:
        self.transfer_edits = [*self.transfer_edits, {"op": op, "args": args}]
        return []

    def _set_transfer_class(self, feature: str, cls: str) -> list[str]:
        return self._transfer("set_transfer_class", feature=feature, cls=cls)

    def _set_extent(self, feature: str, extent: list[str], reason: str) -> list[str]:
        return self._transfer("set_extent", feature=feature, extent=list(extent or []), reason=reason)

    def _connect_features(self, a: str, b: str) -> list[str]:
        return self._transfer("connect_features", a=a, b=b)

    def _set_identity_cues(self, feature: str, cues: str) -> list[str]:
        return self._transfer("set_identity_cues", feature=feature, cues=cues)

    def _set_covering_material_only(self, reason: str) -> list[str]:
        """S5 (D1): the host keeps its own covering; the donor contributes only its color, gloss, texture and pattern."""
        return self._transfer("set_covering_material_only", reason=reason)

    def _set_identity_part(self, donor: str, part: str, reason: str) -> list[str]:
        """S3c (D4): pick the donor's identity part among its own diagnostic parts, with a reason."""
        from app.evolution.identity import IdentityError, validate_pick

        did = self._parent(donor, "donor")
        if did == (self.plan.host or self.sire.id):
            raise OpRejected(OpError("donor_is_host", "the host has no identity part; name the other parent",
                                     field="donor"))
        if not (reason or "").strip():
            raise OpRejected(OpError("missing_reason", "say why this part shows the donor best", field="reason"))
        try:
            c = validate_pick(self.engine.tax.animals[did], part)
        except IdentityError as e:
            raise OpRejected(OpError(e.code, e.message, field="part", valid=e.valid)) from e
        self.identity_picks = {**self.identity_picks, did: (c.part, reason.strip())}
        return []

    def _build(self) -> tuple[Genome, Route]:
        eng = self.engine
        g, r = eng.seed_plan(self.sire, self.dam, host_pick=self.host_pick, habitat=self.habitat, seed=self.seed,
                             design_mode=self.mode)
        for intent in self.regions:
            self._apply_region(g, intent)
        for d in self.drops:
            self._apply_drop(g, d["part"])
        g = eng.finish(g, r, license_requests=self.licenses, transfer_edits=self.transfer_edits,
                       identity_picks=self.identity_picks)
        for d in self.drops:  # a part finish() re-created (dorsal wings) is dropped again, then re-finished
            if any(norm(d["part"]) in norm(p) for _w, p in donor_parts(g)) or (
                    "wing" in d["part"] and dorsal_wings(g, eng.tax)):
                self._apply_drop(g, d["part"])
                g = eng.finish(g, r, license_requests=self.licenses, transfer_edits=self.transfer_edits,
                               identity_picks=self.identity_picks)
        return g, r

    def _apply_region(self, g: Genome, it: dict[str, str]) -> None:
        tax, region, did, op = self.engine.tax, it["region"], it["donor"], it["operator"]
        host = g.host or self.sire.id
        t = g.traits
        if region == "head":
            for tag in ("head", "face", "ears", "skull"):
                t[tag] = Trait(op="PICK", donor=did, note="set by the agent (set_region head)")
        elif region == "tail":
            part = None if did == host else best_part(tax.animals[did], ("tail",))
            t["tail"] = Trait(op="PICK", donor=did, part=part.part if part else None,
                              note="set by the agent (set_region tail)")  # S3c: identity never overrides it
            g.limb_plan.appendages = [a for a in g.limb_plan.appendages if not a.endswith("(tail)")]
            if part:
                g.limb_plan.appendages.append(f"{part.part} (tail)")
        elif region == "forelimbs":
            if did == host:
                g.limb_plan.requested_wings = None
                if g.limb_plan.forelimbs.kind == "wings":
                    g.limb_plan.forelimbs = LimbSlot(kind="legs", donor=host)
            else:
                g.limb_plan.requested_wings = did
        elif op == "PATCH":
            for tag in SURFACE_TAGS:
                tr = t[tag]
                regs = list(tr.region or []) if tr.op == "PATCH" and tr.donor == did else []
                if region not in regs:
                    regs.append(region)
                t[tag] = Trait(op="PATCH", donor=did, strength=1.0, region=regs)
        elif op == "OVERLAY":
            tr = t["coat_pattern"]
            regs = list(tr.region or []) if tr.op == "OVERLAY" and tr.donor == did else []
            t["coat_pattern"] = Trait(op="OVERLAY", donor=did, strength=tr.strength or 0.4,
                                      region=[*regs, region] if region not in regs else regs)
        else:  # PICK with the host: the region goes back to the host
            for tag in SURFACE_TAGS:
                tr = t[tag]
                if tr.op in ("PATCH", "OVERLAY") and region in (tr.region or []):
                    rest = [x for x in tr.region or [] if x != region]
                    t[tag] = tr.model_copy(update={"region": rest}) if rest else Trait(op="PICK", donor=host)

    def _apply_drop(self, g: Genome, part: str) -> None:
        lp, host = g.limb_plan, g.host or self.sire.id
        if part.startswith("wings ("):
            if lp.extra_wings:
                lp.extra_wings = None
            if lp.forelimbs.kind == "wings" and lp.forelimbs.donor != host:
                lp.forelimbs = LimbSlot(kind="legs", donor=host)
            lp.requested_wings = None
            _drop(g, "wings", frozenset())
            return
        for tag, tr in g.traits.items():
            if tr.part and part.startswith(tr.part) or (tr.part and tr.part in part):
                g.traits[tag] = Trait(op="PICK", donor=host, note=f"host {tag}: donor part dropped by the agent")
                lp.appendages = [a for a in lp.appendages if a != f"{tr.part} ({tag})"]
        if part in lp.appendages:
            lp.appendages.remove(part)
        if "wings" in part:
            lp.requested_wings = None
        _drop(g, part, frozenset())

    # ------------------------------------------------------------------ helpers

    def _needs(self) -> set[str]:
        """Bendable rules the current plan bends (granted or not)."""
        from app.evolution.audit import run_audit

        g = self.plan.model_copy(deep=True)
        _cards, needs = run_audit(g, self.engine.tax, self.route)
        return {n.id for n in needs} | {x.id for x in self.plan.licenses}

    def _parent(self, name: str, fieldname: str = "donor") -> str:
        a = self.engine.tax.resolve(str(name))
        if a is None or a.id not in (self.sire.id, self.dam.id):
            raise OpRejected(OpError("not_a_parent", f"{name!r} is not a parent of this plan", field=fieldname,
                                     valid=[self.sire.common_name, self.dam.common_name]))
        return a.id

    def _parent_slot(self, name: str, fieldname: str) -> str:
        return "sire" if self._parent(name, fieldname) == self.sire.id else "dam"

    def _slot_animal(self, slot: str) -> Animal:
        return self.sire if slot == "sire" else self.dam

    def _patch_regions(self) -> list[str]:
        tr = self.plan.traits["coat_texture"]
        return list(tr.region or []) if tr.op == "PATCH" else []

    def _state(self) -> tuple[Any, ...]:
        return (self.mode, self.host_pick, self.habitat, list(self.regions), list(self.licenses), list(self.drops),
                list(self.transfer_edits), dict(self.identity_picks))

    def _restore(self, s: tuple[Any, ...]) -> None:
        (self.mode, self.host_pick, self.habitat, self.regions, self.licenses, self.drops,
         self.transfer_edits, self.identity_picks) = s

    def _result(self, op: str, args: dict[str, Any], errors: list[OpError], warnings: list[str] | None = None) -> OpResult:
        res = OpResult(ok=not errors, op=op, errors=errors, warnings=warnings or [], summary=self.summary())
        self.log.append({"op": op, "args": args, "ok": res.ok, "errors": [e.code for e in errors]})
        return res

