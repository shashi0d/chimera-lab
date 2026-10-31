"""The genome (creature plan), validated by code (ALGORITHM.md section 3).

Every creature is one JSON document. Variation acts on it; the image is always
re-rendered from it (RC-R8-01). Unknown fields are rejected, so no plan can
carry a field such as "dominant_parent" (RC-R1-01).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TRAIT_TAGS: tuple[str, ...] = (
    "size", "body", "head", "face", "ears", "mane", "tail", "limbs", "feet",
    "coat_pattern", "coat_color", "coat_texture", "skull", "behavior",
)
MEASUREMENT_TAGS = ("size", "body", "limbs", "tail", "ears", "skull")
SURFACE_TAGS = ("coat_pattern", "coat_color", "coat_texture")
HEAD_GROUP = ("head", "face", "ears", "skull")
REGIONS: tuple[str, ...] = (
    "head", "face", "ears", "neck", "forequarters", "back", "flanks", "belly",
    "hindquarters", "legs", "forelimbs", "hindlimbs", "feet", "tail", "wings",
)
BEYOND = "beyond both parents"
Op = Literal["BLEND", "PICK", "OVERLAY", "PATCH"]
Mode = Literal["hybrid", "chimera", "mythic"]
DesignMode = Literal["realistic", "speculative", "mythic"]  # E4: the fiction budget (R9 3.1)
DESIGN_MODES: tuple[str, ...] = ("realistic", "speculative", "mythic")
FUNCTIONS: tuple[str, ...] = ("breathing", "feeding", "support", "movement", "heat", "senses")  # R9 2
LimbKind = Literal["legs", "wings", "fins", "tentacles", "arms", "none"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Trait(_Strict):
    op: Op
    donor: str | list[str] | None
    value: float | None = None  # BLEND position: 0 = donor[0], 1 = donor[1]
    strength: float | None = None  # 0..1 visibility
    region: list[str] | None = None
    part: str | None = None  # a donated signature part, e.g. "tentacles"
    note: str | None = None
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> Trait:
        beyond = BEYOND in self.flags
        if self.op == "BLEND":
            if not (isinstance(self.donor, list) and len(self.donor) == 2 and self.donor[0] != self.donor[1]):
                raise ValueError("BLEND needs two different donors")
            if self.value is None:
                raise ValueError("BLEND needs a value")
            lo, hi = (-0.5, 1.5) if beyond else (0.0, 1.0)
            if not lo <= self.value <= hi:
                raise ValueError(f"BLEND value {self.value} out of range (flag '{BEYOND}' to exceed parents)")
        else:
            if isinstance(self.donor, list):
                raise ValueError(f"{self.op} takes one donor")
            if self.op in ("OVERLAY", "PATCH"):
                if not self.donor:
                    raise ValueError(f"{self.op} needs a donor")
                if not self.region:
                    raise ValueError(f"{self.op} needs a region")
        if self.strength is not None and not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be 0..1")
        for r in self.region or []:
            if r not in REGIONS:
                raise ValueError(f"unknown region {r!r}")
        return self

    def donors(self) -> list[str]:
        if self.donor is None:
            return []
        return list(self.donor) if isinstance(self.donor, list) else [self.donor]


class Parents(_Strict):
    sire: str
    dam: str


class Lineage(_Strict):
    parent_ids: list[str] = Field(default_factory=list)
    generation: int = 0


class Habitat(_Strict):
    name: str
    source: Literal["shared", "bridging", "user"]
    adjustments: list[str] = Field(default_factory=list)
    visible_trait: str | None = None


class Size(_Strict):
    mass_kg: float | None
    flags: list[str] = Field(default_factory=list)


class LimbSlot(_Strict):
    kind: LimbKind
    donor: str | None = None


class LimbPlan(_Strict):
    forelimbs: LimbSlot
    hindlimbs: LimbSlot
    extra_wings: LimbSlot | None = None  # a separate wing pair: six limbs (RC-R3-02)
    appendages: list[str] = Field(default_factory=list)  # tentacle tail, trunk...
    wing_use: Literal["powered", "borderline", "gliding_or_display", "none"] = "none"
    requested_wings: str | None = None  # a wing donor waiting for the limb-budget check

    def limb_count(self) -> int:
        n = sum(2 for s in (self.forelimbs, self.hindlimbs) if s.kind != "none")
        return n + (2 if self.extra_wings else 0)

    def has_wings(self) -> bool:
        return "wings" in (self.forelimbs.kind, self.hindlimbs.kind) or self.extra_wings is not None


class Check(_Strict):
    step: str
    result: Literal["pass", "repaired", "labeled", "blocked", "adjusted"]
    detail: str
    cards: list[str] = Field(default_factory=list)


class AuditItem(_Strict):
    """One function of the R9 audit (4.5b). `pending` waits for the one model judgment before the render."""
    function: Literal["breathing", "feeding", "support", "movement", "heat", "senses"]
    result: Literal["pass", "repaired", "labeled", "licensed", "pending"]
    detail: str
    cards: list[str] = Field(default_factory=list)
    source: Literal["code", "model-judged"] = "code"


class License(_Strict):
    """A declared fiction license (4.5c): bends one named bendable card, always with a compensation."""
    id: str
    card: str
    rule: str
    compensation: str
    reason: str


class Genome(_Strict):
    id: str
    parents: Parents
    lineage: Lineage = Field(default_factory=Lineage)
    mode: Mode
    known_pair: str | None = None
    host: str | None
    identity_balance: float = Field(ge=0.0, le=1.0)
    habitat: Habitat
    size: Size
    silhouette: str
    limb_plan: LimbPlan
    traits: dict[str, Trait]
    labels: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)
    card_trace: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    seed: int = 0
    design_mode: DesignMode = "speculative"
    audit: list[AuditItem] = Field(default_factory=list)
    licenses: list[License] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> Genome:
        parents = {self.parents.sire, self.parents.dam}
        if self.parents.sire == self.parents.dam:
            raise ValueError("sire and dam must differ")
        missing = [t for t in TRAIT_TAGS if t not in self.traits]
        extra = [t for t in self.traits if t not in TRAIT_TAGS]
        if missing or extra:
            raise ValueError(f"traits must cover the shared vocabulary exactly (missing {missing}, extra {extra})")
        for tag, tr in self.traits.items():
            bad = [d for d in tr.donors() if d not in parents]
            if bad:
                raise ValueError(f"trait {tag}: donor {bad} is not a parent")
        if self.host is not None and self.host not in parents:
            raise ValueError("host must be a parent")
        if self.host is None and self.mode != "hybrid":
            raise ValueError("chimera and mythic plans need a host")
        for slot in (self.limb_plan.forelimbs, self.limb_plan.hindlimbs, self.limb_plan.extra_wings):
            if slot and slot.donor and slot.donor not in parents:
                raise ValueError("limb donor must be a parent")
        if not self.silhouette.strip():
            raise ValueError("silhouette sentence is required (RC-R7-06)")
        return self

    def other(self, animal_id: str) -> str:
        return self.parents.dam if animal_id == self.parents.sire else self.parents.sire


def validate_plan(doc: dict[str, Any] | Genome) -> Genome:
    """Code validation used on every endpoint that accepts or produces a plan (section 5)."""
    return doc if isinstance(doc, Genome) else Genome.model_validate(doc)


def trait(op: str, donor: Any, **kw: Any) -> Trait:
    return Trait(op=op, donor=donor, **kw)  # type: ignore[arg-type]
