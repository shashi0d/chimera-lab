"""Backend executor registry, keyed by node type (mirrors frontend nodes/registry.ts).

Adding a runnable node = one new Executor here (or in its own module imported here).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.errors import ChimeraError
from app.models.schemas import ErrorCode, Graph, GraphNode
from app.pipeline.context import InputImage, RunContext
from app.pipeline.steps import compile as compile_step
from app.pipeline.steps import field_card, generate, hybrid_check, identify, load_inputs, match, rules_check, store

StepFn = Callable[[RunContext], Awaitable[str | None]]


@dataclass(frozen=True)
class StepDef:
    key: str
    label: str
    fn: StepFn


class Executor(Protocol):
    def resolve_inputs(self, graph: Graph, node: GraphNode) -> list[InputImage]: ...

    def configure(self, graph: Graph, node: GraphNode) -> dict[str, object]:
        """Validated node config, copied into the run's state before step 1."""
        ...

    def steps(self) -> list[StepDef]: ...


def upstream(graph: Graph, node_id: str, port: str) -> GraphNode | None:
    for e in graph.edges:
        if e.target == node_id and e.target_port == port:
            return next((n for n in graph.nodes if n.id == e.source), None)
    return None


PARTS = ("head", "body", "limbs", "covering", "tail")


class FusionExecutor:
    PORTS = ("a", "b")

    def configure(self, graph: Graph, node: GraphNode) -> dict[str, object]:
        donors = node.config.get("donors") or {}
        if not isinstance(donors, dict):
            raise ChimeraError(ErrorCode.GRAPH_INVALID, "The Fusion node's anatomy settings are not valid.")
        pins: dict[str, str] = {}
        for part, value in donors.items():
            if part not in PARTS or value not in ("auto", "A", "B"):
                raise ChimeraError(ErrorCode.GRAPH_INVALID, "The Fusion node's anatomy settings are not valid.",
                                   details={"part": str(part)})
            if value != "auto":
                pins[part] = value
        return {"donor_pins": pins}

    def resolve_inputs(self, graph: Graph, node: GraphNode) -> list[InputImage]:
        inputs: list[InputImage] = []
        for port in self.PORTS:
            src = upstream(graph, node.id, port)
            if src is None or src.type != "image-input":
                raise ChimeraError(ErrorCode.GRAPH_INVALID, "Connect two images to the Fusion node.",
                                   details={"missingPort": port})
            asset_id = src.data.get("assetId")
            if not asset_id:
                raise ChimeraError(ErrorCode.GRAPH_INVALID, "An input image has not finished uploading.",
                                   details={"nodeId": src.id})
            inputs.append(InputImage(slot=port.upper(), node_id=src.id, asset_id=str(asset_id)))
        if inputs[0].asset_id == inputs[1].asset_id:
            raise ChimeraError(ErrorCode.DUPLICATE_INPUTS, "Both inputs are the same image.")
        return inputs

    def steps(self) -> list[StepDef]:
        return [
            StepDef("load_inputs", "Load images", load_inputs.run),
            StepDef("identify", "Identify animals", identify.run),
            StepDef("match", "Match field data", match.run),
            StepDef("hybrid_check", "Check real hybrids", hybrid_check.run),
            StepDef("rules_check", "Check anatomy rules", rules_check.run),
            StepDef("compile", "Plan the creature", compile_step.run),
            StepDef("generate", "Generate image", generate.run),
            StepDef("store", "Save result", store.run),
        ]


class FieldCardExecutor:
    """F2: writes a field-guide card for the upstream Result's selected version."""

    def resolve_inputs(self, graph: Graph, node: GraphNode) -> list[InputImage]:
        self.configure(graph, node)
        return []

    def configure(self, graph: Graph, node: GraphNode) -> dict[str, object]:
        src = upstream(graph, node.id, "in")
        if src is None or src.type != "result":
            raise ChimeraError(ErrorCode.GRAPH_INVALID, "Connect a Result to write its card.")
        versions = src.data.get("versions") or []
        if not isinstance(versions, list) or not versions:
            raise ChimeraError(ErrorCode.GRAPH_INVALID, "Fuse first; the card describes a finished creature.")
        selected = src.data.get("selected", len(versions) - 1)
        idx = selected if isinstance(selected, int) and 0 <= selected < len(versions) else len(versions) - 1
        creature_id = (versions[idx] or {}).get("creatureId") if isinstance(versions[idx], dict) else None
        if not creature_id:
            raise ChimeraError(ErrorCode.GRAPH_INVALID, "This Result has no saved creature yet.")
        return {"creature_id": str(creature_id)}

    def steps(self) -> list[StepDef]:
        return [
            StepDef("load_creature", "Load creature", field_card.load_creature),
            StepDef("write_card", "Write field notes", field_card.write_card),
            StepDef("store_card", "Save card", field_card.store_card),
        ]


EXECUTORS: dict[str, Executor] = {"fusion": FusionExecutor(), "field-card": FieldCardExecutor()}
