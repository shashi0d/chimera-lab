# Round 1

## Review

I used the app end to end in mock mode via the pv-3 screenshots and the e2e flows:
- lion + tiger (real hybrid)
- octopus + macaw (warnings)
- fox + iguana (re-run to v2)

What feels thin:

1. **The user has no say in the creature.** Fuse is a slot machine: the model decides which parent gives the head, body, limbs, covering and tail, and re-running gives "another one" with no way to steer. The data already carries `partDonors` (5.1), and the tasksheet reserves it for "the future Fusion settings panel".
2. **"Fuse again" is not meaningfully different.** Versions exist, but nothing explains how v2 differs from v1.
3. **No check that the image matches the plan.** The spec says "head from A", but nobody looks at whether the image actually does that.
4. **The output dead-ends.** There is no artefact to take away (card, export).

## Candidates

1. **Anatomy controls.** Choose the donor parent for each body part (or leave it to the model); the creature and the explanation follow. *Helps:* anyone who wants a specific creature, not a random one.
2. **Verify step.** After generation, Muse Spark inspects the image against the plan (parts, limb count, no text or people) and gives a verdict, with one automatic repair attempt. *Helps:* trust and accuracy.
3. **Field-guide card.** A Result produces a printable specimen card (plate, invented binomial, habitat and diet inferred from the parents, provenance) as a PNG. *Helps:* sharing and the demo.
4. **Version compare.** Two versions side by side, with the plan differences highlighted. *Helps:* understanding re-runs.
5. **Prompt editing.** Edit the generated prompt before generating. *Helps:* power users.

## Scores (1 to 5)

| Candidate | User value | Demo impact | Meta model depth | Fits registry, no core change | Mock-testable | Low risk to gates | Total |
|---|---|---|---|---|---|---|---|
| 1 Anatomy controls | 5 | 5 | 3 | 5 | 5 | 4 | **27** |
| 2 Verify step | 4 | 4 | 5 | 5 | 5 | 3 | 26 |
| 3 Field-guide card | 4 | 5 | 4 | 4 | 5 | 4 | 26 |
| 4 Version compare | 3 | 3 | 1 | 4 | 5 | 4 | 20 |
| 5 Prompt editing | 3 | 2 | 2 | 4 | 5 | 3 | 19 |

## Pick: 1, Anatomy controls

It turns Fuse from a slot machine into a design tool, which is the core of "more control over the chimera". It exercises the parts of the architecture the tasksheet promised but never used:
- node config
- a node config **version bump with migration** (1 → 2)
- user overrides flowing through the planning model

It also makes "Fuse again" meaningful: change a part, re-run, and the plate changes. Verify (2) loses narrowly. It adds a paid call per run, and it is a stronger feature once the user's intent (donors) is explicit, because then there is a plan to verify against. Field card (3) is the natural candidate for F2. Compare (4) and prompt editing (5) lose on value and model depth.

## Mini-spec: Anatomy controls

**User flow**

1. The Fusion node shows an **Anatomy** strip with five parts: Head, Body, Limbs, Covering, Tail. Each part is a small cycle button whose value is `Auto → A → B → Auto`. "Auto" (dashed outline) means the model decides; "A" (Lapis) and "B" (Moss) pin the part to that parent. The color and shape match the port and slot colors.
2. The user pins, for example, Head = B (octopus) and Covering = A (macaw), then presses Fuse.
3. The pipeline's `compile` step passes the pins to the planning model as hard constraints. If all five parts are pinned, the planning call is skipped entirely, which saves a vision call. The final donors always honour the pins, even if the model disagrees.
4. The Result's "How this was made" panel marks each donor as **you** or **model**.
5. Changing a pin after a result exists marks the result **Outdated** ("Inputs changed… Fuse again"), the same as replacing an image.

**Node and contract changes**

- Fusion config `version: 2`, adding `donors: Record<"head"|"body"|"limbs"|"covering"|"tail", "auto"|"A"|"B">`. `migrate()` upgrades v1 nodes to all `auto`. **This is the first real per-node migration.**
- Backend: `FusionExecutor` reads `node.config.donors`. Invalid values give `GRAPH_INVALID`. Pins are stored on the run context.
- `compile`: `planning_context.donor_pins`; pins override the plan; all pinned means no plan call.
- `CreatureSpec.donorSource: Record<part, "user"|"model">` (new field; gen types).
- Mock vision honours pins. **The mock image generator composes from the donors**: the parent that gives the head is drawn over the parent that gives the body, so pinning visibly changes the plate.

**States added**

| Kind | State | Behaviour |
|---|---|---|
| Input | pin toggled | config updates (one undo step); results downstream become stale |
| Input | all parts from one parent | advisory hint (warn, not block): "Every part comes from A, so this will look like A." |
| Loading | n/a | unchanged |
| Output | donors in panel | each donor tagged "you" / "model" |
| Error | bad saved config (e.g. `"C"`) | migrate/sanitise to `auto` on load; backend rejects with `GRAPH_INVALID` if sent |
| Broken | old v1 graph | migrated on load (all auto) |
| Offline | toggles | work offline (local config); Fuse stays disabled |
| Read-only | toggles | disabled |

**Acceptance**

- *Given* a Fusion node with Head pinned to B, *when* I fuse, *then* the spec's `partDonors.head` is `B` and `donorSource.head` is `user`.
- *Given* all five parts pinned, *when* I fuse, *then* only 2 vision calls are made (no planning call).
- *Given* a result, *when* I change a pin, *then* the Fusion and Result nodes show Outdated.
- *Given* a saved graph with a v1 Fusion node, *when* it loads, *then* the node is v2 with all parts `auto`.
- *Given* a pin set to every part from A, *when* I look at the node, *then* a non-blocking hint explains it.
- *Given* keyboard only, *when* I tab to a part and press Enter, *then* it cycles and announces "Head from B".

## Tasks

See TASKSHEET F1-01 to F1-06.

## Outcome

**Shipped: Anatomy controls.**

- **Backend:**
  - `FusionExecutor.configure()` validates `config.donors` (`GRAPH_INVALID` on bad values).
  - `compile` passes pins to the planner, forces them onto the plan, and skips the planning call when all five are pinned (test: the run succeeds with a vision budget of 2).
  - `CreatureSpec.donorSource` records who chose each part.
  - The mock planner honours pins, and the mock generator reads the head assignment from the prompt, so pins visibly change the plate.
- **Frontend:**
  - Fusion config **v2** with `migrate()` (v1 → all Auto; bad values sanitised). This is the first per-node migration in the app.
  - The `AnatomyStrip` cycle buttons: dashed Auto, Lapis A, Moss B; keyboard-operable and announced.
  - An advisory hint when every part comes from one parent.
  - A pin change marks results Outdated.
  - The panel tags each donor "you" / "model".
  - New store API `updateNodeConfig` (one undo step per edit).

**Tests:**

- backend +7 (`test_anatomy_controls.py`)
- frontend +5 component (`anatomy.test.tsx`)
- e2e +1 (pin → fuse → panel credits you → change → Outdated)
- full suites green

**Visual QA (round `f1`, 36 shots, 1440 and 1024 in both themes):**

- New states 80 to 83 plus affected states 06, 20, 22, 23 and 60.
- No blocker or major defects. Lowest score per criterion is 4.
- One capture artefact: the parked mouse at (2,600) hovers an image node and shows its toolbar in `81-*`. Not a product defect.
- Baselines re-approved on purpose: the Fusion node gained the anatomy strip (D-028).

**Cut:** a per-part "lock" on the Result node (re-run with the same donors as version N). Next round should consider it as part of a richer version workflow.

**Next round should consider:**

1. The output still dead-ends: there is no artefact to take away. A field-guide card fits naturally now, since the card can say "head from the macaw (your choice)".
2. A Verify step now has an explicit plan to check against (the pins).
