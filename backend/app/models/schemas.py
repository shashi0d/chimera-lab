"""Pydantic models: the single source of truth for API types.

`scripts/gen_types.sh` turns these into `frontend/src/types/api.ts`.
Python attributes are snake_case; JSON on the wire is camelCase.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, json_schema_serialization_defaults_required=True
    )

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")


# ---------------------------------------------------------------- errors


class ErrorCode(str, Enum):
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    IMAGE_CORRUPT = "IMAGE_CORRUPT"
    IMAGE_TOO_SMALL = "IMAGE_TOO_SMALL"
    NOT_AN_ANIMAL = "NOT_AN_ANIMAL"
    HUMAN_DETECTED = "HUMAN_DETECTED"
    DUPLICATE_INPUTS = "DUPLICATE_INPUTS"
    GRAPH_INVALID = "GRAPH_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    MODEL_REFUSED = "MODEL_REFUSED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    RUN_NOT_FOUND = "RUN_NOT_FOUND"
    RUN_INTERRUPTED = "RUN_INTERRUPTED"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL = "INTERNAL"


class ApiError(ApiModel):
    code: ErrorCode
    message: str
    retryable: bool = False
    retry_after_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error_id: str | None = None


class ErrorEnvelope(ApiModel):
    error: ApiError


# ---------------------------------------------------------------- health


class Health(ApiModel):
    status: Literal["ok"] = "ok"
    mode: Literal["mock", "real"]
    version: str
    data_source: Literal["full", "sample"]


# ---------------------------------------------------------------- assets


class Asset(ApiModel):
    asset_id: str
    width: int
    height: int
    sha256: str
    content_type: str
    url: str
    created_at: str


# ---------------------------------------------------------------- graph


class Position(ApiModel):
    x: float
    y: float


class GraphNode(ApiModel):
    id: str
    type: str
    version: int = 1
    position: Position
    config: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(ApiModel):
    id: str
    source: str
    source_port: str
    target: str
    target_port: str


class Graph(ApiModel):
    schema_version: int = 1
    graph_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------- vision + spec


class AnimalReading(ApiModel):
    is_animal: bool
    contains_human: bool = False
    common_name: str | None = None
    scientific_name: str | None = None
    confidence: float = 0.0
    visible_parts: list[str] = Field(default_factory=list)
    body_plan: str | None = None
    notes: str = ""


class AnimalMatch(ApiModel):
    animal_id: str
    tier: Literal[1, 2]
    common_name: str
    scientific_name: str | None = None
    matched_on: Literal["common_name", "scientific_name", "genus"]
    facts: dict[str, str] = Field(default_factory=dict)


class ParentInfo(ApiModel):
    slot: Literal["A", "B"]
    asset_id: str
    reading: AnimalReading
    match: AnimalMatch | None = None


class RealHybrid(ApiModel):
    hybrid_id: str
    name: str
    facts: dict[str, str] = Field(default_factory=dict)


class RuleWarning(ApiModel):
    rule_id: str
    message: str
    severity: Literal["info", "warning"] = "warning"


PartSlot = Literal["A", "B"]


class PartDonors(ApiModel):
    head: PartSlot = "A"
    body: PartSlot = "B"
    limbs: PartSlot = "B"
    covering: PartSlot = "A"
    tail: PartSlot = "A"


class FusionPlan(ApiModel):
    """Structured output from the planning model (Muse Spark)."""

    body_plan: str
    part_donors: PartDonors
    rationale: str = ""
    name_suggestion: str | None = None


class CreatureSpec(ApiModel):
    parents: list[ParentInfo]
    real_hybrid: RealHybrid | None = None
    body_plan: str
    part_donors: PartDonors
    rationale: str = ""
    name: str | None = None
    warnings: list[RuleWarning] = Field(default_factory=list)
    prompt: str
    model: dict[str, str]
    # F1 anatomy controls: who chose each part ("user" pin or "model" plan).
    donor_source: dict[str, Literal["user", "model"]] = Field(default_factory=dict)


# ---------------------------------------------------------------- runs


RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]
StepStatus = Literal["pending", "running", "succeeded", "failed", "skipped"]


class Step(ApiModel):
    key: str
    label: str
    status: StepStatus = "pending"
    started_at: str | None = None
    ended_at: str | None = None
    detail: str | None = None


class FieldCard(ApiModel):
    """F2: field-guide card text. `provenance` is always written by the server, never the model."""

    common_name: str
    binomial: str
    habitat: str
    diet: str
    size: str
    behaviour: str
    provenance: str = ""


class RunResult(ApiModel):
    asset_id: str
    creature_id: str
    image_url: str
    spec: CreatureSpec
    card: FieldCard | None = None


class Run(ApiModel):
    id: str
    graph_id: str
    node_id: str
    session_id: str | None = None
    status: RunStatus = "queued"
    steps: list[Step] = Field(default_factory=list)
    result: RunResult | None = None
    error: ApiError | None = None
    failed_input: Literal["A", "B"] | None = None
    created_at: str
    updated_at: str
    version: int = 0


class StartRunRequest(ApiModel):
    graph: Graph
    node_id: str


class Creature(ApiModel):
    creature_id: str
    run_id: str
    asset_id: str
    parent_asset_ids: list[str]
    spec: CreatureSpec
    created_at: str


# Exported in this order by scripts/gen_types.py
EXPORTED_MODELS: list[type[BaseModel]] = [
    ApiError,
    ErrorEnvelope,
    Health,
    Asset,
    Graph,
    AnimalReading,
    CreatureSpec,
    Run,
    StartRunRequest,
    FieldCard,
]
