# Adding a node type

> **Live example:** the Field card node (`frontend/src/nodes/field-card/`, `backend/app/pipeline/steps/field_card.py`, `FieldCardExecutor`) was added in round F2 following this guide. Read it next to the Style walkthrough below.

A worked example adds a **Style** node that takes a creature and re-renders it in a chosen illustration style. It is not shipped; it is here to show the shape of the change. Adding a node touches only:

1. `frontend/src/nodes/style/` (new folder)
2. one line in `frontend/src/nodes/registry.ts`
3. one backend executor (a new step module plus one entry in `backend/app/pipeline/registry.py`)

Nothing in the canvas, stores, transport, API or styles needs to change. The tool rail button, validation, run button behaviour, step list, error states and side panel all come from the registry.

## 1. Frontend: `nodes/style/`

`nodes/style/types.ts`

```ts
import type { RunnableData } from "../../runs/store";

export interface StyleConfig extends Record<string, unknown> {
  style: "field-guide" | "woodcut" | "watercolour";
}
export type StyleData = RunnableData; // activeRunId / runIds like Fusion
```

`nodes/style/definition.ts`

```ts
import { upstreamNode } from "../../graph/queries";
import { defineNode } from "../types";
import { StyleView } from "./NodeView";
import type { StyleConfig, StyleData } from "./types";

export const styleNode = defineNode<StyleConfig, StyleData>({
  type: "style",
  version: 1,
  label: "Style",
  category: "process",
  icon: "leaf",
  addable: true, // tool rail gets an "Add style node" button automatically
  inputs: [{ id: "in", label: "Creature", accepts: ["creature"] }],
  outputs: [{ id: "out", emits: "creature" }],
  defaultConfig: { style: "field-guide" },
  defaultData: () => ({ activeRunId: null, runIds: [] }),
  validate: (node, ctx) =>
    upstreamNode(ctx.graph, node.id, "in")
      ? []
      : [{ code: "MISSING_INPUTS", message: "Connect a Result to restyle it.", severity: "block" }],
  View: StyleView,
  runnable: true,
  // Optional: write run results back into the graph (see nodes/field-card/actions.ts).
  onRunUpdate: (nodeId, run) => { /* e.g. store run.result in node data */ },
});
```

`nodes/style/NodeView.tsx` composes the shared card and the shared run widgets in `canvas/RunParts.tsx` (`StepList`, `ErrorBlock`, `useCountdown`). Ports, the kicker + title header, the `LiveIndicator` status, optional edge-to-edge `media` and the glass contextual `toolbar` come from `NodeCard` (U1, `docs/DESIGN_U1.md`). Starting and watching runs come from `useRuns`, exactly as in `nodes/fusion/NodeView.tsx`:

```tsx
export function StyleView({ node, selected, issues }: NodeViewProps<StyleConfig, StyleData>) {
  const start = useRuns((s) => s.start);
  const blocked = issues.some((i) => i.severity === "block");
  return (
    <NodeCard nodeId={node.id} kind="style" kicker="Style" title="Restyle"
      inputs={styleNode.inputs} outputs={styleNode.outputs} selected={selected}
      footer={<Button variant="primary" disabled={blocked} onClick={() => void start(node.id)}>Restyle</Button>}>
      {/* a <select> bound to node.config.style via useGraph().updateNodeData */}
    </NodeCard>
  );
}
```

CSS: add a `/* 5x. Style */` block in `theme.css`, section 5 (Nodes) (for example `.node--style { width: var(--node-w-fusion); }`), using tokens only.

Strings go in `copy.ts`.

## 2. Register it

```ts
// frontend/src/nodes/registry.ts
import { styleNode } from "./style/definition";
const definitions: AnyNodeDefinition[] = [imageInputNode, fusionNode, resultNode, styleNode];
```

Edge rules work at once: `creature → creature` is allowed, and cycles are refused generically. Saved graphs from before the Style node existed are unaffected. Graphs that contain one, opened in an older build, show the "Unsupported node" placeholder.

If the config shape changes later, bump `version` and add `migrate(oldConfig, oldData, fromVersion)`. `graph/migrate.ts` calls it on load.

## 3. Backend executor

`backend/app/pipeline/steps/restyle.py`:

```python
async def run(ctx: RunContext) -> str:
    source = ctx.inputs[0]  # the upstream result image, loaded by load_inputs-style logic
    out = await call_with_retry(
        lambda: ctx.services.image_gen.generate(f"Redraw this creature as a {style} plate.", [source.data], "1:1"),
        timeout=ctx.services.settings.generate_timeout_seconds,
        base_delay=ctx.services.settings.retry_base_seconds,
        max_attempts=ctx.services.settings.retry_max_attempts,
        before_attempt=lambda _n: ctx.use_generation(),   # the spend guard applies automatically
        can_retry=ctx.can_generate,
    )
    ...
```

`backend/app/pipeline/registry.py`:

```python
class StyleExecutor:
    def resolve_inputs(self, graph, node): ...  # follow the "in" edge to a result node's latest asset
    def configure(self, graph, node): ...       # validated config -> run state (e.g. {"style": ...})
    def steps(self):
        return [StepDef("load_inputs", "Load creature", load_creature.run),
                StepDef("restyle", "Restyle", restyle.run),
                StepDef("store", "Save result", store.run)]

EXECUTORS = {"fusion": FusionExecutor(), "style": StyleExecutor()}
```

`POST /runs` already accepts any registered runnable node. `GET /runs/:id` reports the new step list, and the frontend step list renders it with no change.

## 4. Tests to add

- `frontend/tests/unit/style.test.ts`: `validate` blocks without an input, and the edge rule accepts `result.out → style.in`.
- `frontend/tests/component/styleNode.test.tsx`: the button is disabled with a hint, and `start()` is called once.
- `backend/tests/integration/test_style_runs.py`: a full run in mock mode, plus `X-Mock-Fault: refusal`, which should give `MODEL_REFUSED`.
- Add the node's states to `frontend/tests/visual/capture.ts` and review them against `docs/UI_STANDARD.md`.
