# Round 2

## Review (including the F1 outcome)

I reran the app in mock mode through the `f1` screenshots and e2e flows. F1 made Fuse steerable: pins change the plate, and the panel says who chose what. Its close-out flagged two things:

1. **The output still dead-ends.** After a good fusion there is nothing to take away or show. For a hackathon judge, a shareable artefact is the moment the demo lands.
2. **There is no check that the image matches the plan.** F1 made the plan explicit (pins), so a verifier now has something concrete to check.

Also noticed:

- The Result node is a sink: it has no output port, so nothing can build on a creature. The registry and edge rules already support `creature` flowing on; nothing uses it.
- Run updates are wired per node type in `App.tsx` (`registerFusionRunHandler`). A second runnable node would have to touch the app shell, which contradicts the "only `nodes/<type>/`, registry, executor" promise.

## Candidates

1. **Field-guide card node.** A Result feeds a new Field Card node, which writes a specimen card with Muse Spark: invented binomial, habitat, diet, size from the parents' real measurement ranges, behaviour, provenance. It renders on the canvas and downloads as a PNG. *Helps:* sharing and the demo; proves the node architecture.
2. **Verify step.** After generation, Muse Spark checks the image against the plan (pinned parts, limb count, no text or people), with one automatic repair attempt. *Helps:* accuracy and trust.
3. **Version workflow.** Compare v1 and v2 side by side, and re-run with a version's donors. *Helps:* iteration.
4. **Batch fusion.** One image against several partners at once. *Helps:* exploration (but multiplies spend).

## Scores (1 to 5)

| Candidate | User value | Demo impact | Meta model depth | Fits registry, no core change | Mock-testable | Low risk to gates | Total |
|---|---|---|---|---|---|---|---|
| 1 Field-guide card | 4 | 5 | 4 | 5 | 5 | 4 | **27** |
| 2 Verify step | 4 | 4 | 5 | 5 | 5 | 3 | 26 |
| 3 Version workflow | 3 | 3 | 1 | 4 | 5 | 4 | 20 |
| 4 Batch fusion | 3 | 4 | 3 | 3 | 5 | 2 | 20 |

## Pick: 1, Field-guide card

It gives the demo a takeaway, uses the curated data in a way users can see (real measurement ranges, habitats, the real-hybrid note), and is the first **new node type** added after v1. That makes it a live test of `docs/ADDING_A_NODE.md`. Verify loses narrowly, on gate risk: it adds a paid generation (the repair) to every fusion and changes the step list that all baselines show. It is the top candidate for a next round. Version workflow and batch lose on value and spend.

**Core change I'm making on purpose:** run-update handling moves from `App.tsx` into the registry (`NodeDefinition.onRunUpdate`). Without it, a new runnable node needs an app-shell edit. With it, the "no changes outside the node folder" rule really holds (D-030).

## Mini-spec: Field Card node

**User flow**

1. The Result node gets an output port (`creature`, diamond) and a hover-toolbar action, **Make field card**, which adds a Field Card node to its right, already connected. A Field Card can also be wired by hand from any Result.
2. The Field Card shows "Write card". The backend loads the creature (spec plus image) for the Result's **selected version** and asks Muse Spark for a structured card. Size comes from the parents' measurement ranges, quoted as ranges and never averaged.
3. The node renders the card: plate, name, *invented binomial* (tagged "invented"), habitat, diet, size, behaviour, and a provenance strip ("Generated fusion. Not a real animal." plus "Real hybrid: Liger" when relevant).
4. **Download PNG** draws the card client-side (canvas, self-hosted fonts) and saves `<name>-field-card.png`. It works offline.
5. If the Result's selected version changes, the card says it was made from version N and offers "Rewrite for version M".

**New node and contract changes**

- `nodes/field-card/`: definition, view, validation, PNG renderer. `nodes/result/`: output port plus toolbar action.
- `NodeDefinition.onRunUpdate` (generic). Fusion's handler moves into its definition. `App.tsx` dispatches through the registry.
- Backend:
  - `FieldCardExecutor` with steps `load_creature → write_card → store_card`
  - `VisionAdapter.write_field_card(context) → FieldCard`, with mock and Meta implementations
  - `RunResult.card`
  - per-run vision cap applies (1 call)
- `FieldCard` model: `commonName`, `binomial`, `habitat`, `diet`, `size`, `behaviour`, `provenance`.

**States added**

| Kind | State | Behaviour |
|---|---|---|
| Input | no Result connected | Write card disabled, hint "Connect a Result to write its card." |
| Input | Result has no version yet | disabled, hint "Fuse first; the card describes a finished creature." |
| Loading | writing | step list (3 steps), skeleton card |
| Output | card | rendered card plus Download PNG |
| Output | out of date | "Made from v1, now showing v2" plus Rewrite |
| Error | model errors / timeout / rate limit | same error map and retry UX as Fusion |
| Error | creature not found (old graph) | `NOT_FOUND`: "Fuse again, then write the card." |
| Offline | | Write disabled; Download still works |
| Broken | unknown in old builds | placeholder (existing behaviour) |

**Acceptance**

- *Given* a finished Result, *when* I choose "Make field card", *then* a connected Field Card appears with "Write card" enabled.
- *Given* lion + tiger, *when* the card is written, *then* it shows the invented binomial (marked invented), the parents' mass ranges verbatim, and "Real hybrid: Liger".
- *Given* a written card, *when* I click Download PNG, *then* a PNG of at least 1200px is produced, including offline.
- *Given* the Result is switched to another version, *then* the card shows it is out of date and offers Rewrite.
- *Given* `X-Mock-Fault: timeout`, *when* writing, *then* the card shows the timeout message with Retry.
- **Architecture check:** the node is added with changes only in `nodes/field-card/`, `nodes/result/` (its own port and action), `nodes/registry.ts` and one backend executor module. The one-time `onRunUpdate` refactor is called out above.

## Tasks

See TASKSHEET F2-01 to F2-07.

## Outcome

**Shipped: Field-guide card node.**

- **Backend:**
  - `FieldCardExecutor` resolves the upstream Result's selected version (`GRAPH_INVALID` if not connected or not fused).
  - Steps: `load_creature` (`NOT_FOUND` for a missing creature), `write_card` (Muse Spark structured output, counted against the vision cap, retry policy), `store_card` (card saved on the creature record).
  - Size quotes the parents' recorded ranges verbatim. **Provenance is always server-written** ("Generated fusion. Not a real animal." plus the real-hybrid line), never model text (fixed point 4).
  - `Executor.configure()` now takes the graph.
- **Frontend:**
  - `nodes/field-card/`: definition, view, validation, upstream helper, run handler, canvas PNG renderer (1600×1000, theme tokens + self-hosted fonts, works offline).
  - Result node: `creature` output port plus a "Make field card" toolbar action.
  - Out-of-date detection against the Result's selected version, with "Rewrite for vN".
- **One-time core refactor (D-030):** run updates dispatch through `NodeDefinition.onRunUpdate` via `registerRunHandlers()`. Fusion's handler moved into its definition. Adding the Field card needed **no app-shell change**.
- **Architecture check:** apart from that planned refactor and the shared `canvas/RunParts.tsx` extraction (used by both runnable nodes), the node touched only `nodes/field-card/`, `nodes/result/`, `nodes/registry.ts` (one line), `copy.ts`/`theme.css` (strings and styles live there by rule), and one backend executor plus step module.

**Tests:**

- backend +7 (`test_field_card.py`)
- frontend +6 component (`fieldCard.test.tsx`)
- e2e +1 (make, write, download PNG checked as a real 1600px PNG, out of date after v2, rewrite)
- totals: pytest 89, vitest 146, e2e 39

**Visual QA (round `f2`, 36 shots, 1440 and 1024 in both themes):**

- States 90 to 94, including the exported PNG itself, plus affected states 20, 23, 60 and 81.
- No blocker or major defects. Lowest score per criterion is 4.
- Baselines unchanged within tolerance (the new Result output port is within 1%).

**Cut:** server-side PNG rendering (client canvas is enough and works offline); sharing links (accounts are a non-goal).

**Next round should consider:**

1. **Verify step** (runner-up twice). The plan is now explicit, so verification has a target.
2. A version workflow: re-run with a version's donors, and compare v1/v2.
3. Real photos for the demo, once P7 keys exist.
