# Decisions

One entry per meaningful change from the tasksheet defaults: what changed, why, the alternative, and what it affects. Newest entries go at the bottom.

---

**D-001 GitHub repo created by Shashi, not from the build environment.**
The session's GitHub access is limited to repositories that already exist and are attached to the session, so `gh repo create` was refused. The build went ahead in a local git repo and gets pushed once `shashi0d/chimera-lab` is reachable. *Alternative:* wait idle. *Affects:* nothing in the code.

**D-002 Python 3.13 locally; Modal image pinned to 3.11.**
The container ships Python 3.13. The code is 3.11-compatible (ruff targets py311), and `modal_app.py` builds a 3.11 image. *Alternative:* install 3.11 with uv. That adds setup time and tests no more than the 3.11 deploy image does.

**D-003 The spend guard counts every attempt, retries included, and retries stop when the budget runs out.**
A failed paid call may still be billed, so the guard charges every *attempt*. Instead of raising the caps, the retry loop asks the guard before each retry (`can_retry`). When the budget is spent it stops and surfaces the original upstream error, not `BUDGET_EXCEEDED`. Defaults stay `MAX_GENERATIONS_PER_RUN=2` and `MAX_VISION_CALLS_PER_RUN=4`: 2 identify + 1 plan leaves one spare vision retry, and generation gets one retry. *Alternative:* count only successful calls. That under-protects against an upstream that bills failures. *Affects:* `pipeline/retry.py`, `pipeline/context.py`.

**D-004 `VisionAdapter.plan_fusion` added to the protocol.**
The `compile` step needs Muse Spark structured output (Section 5.1). That is a vision/planning-model call, so it sits on the same adapter as `describe_animal` and is charged to the vision budget. *Alternative:* a separate `PlannerAdapter`, which would be another adapter to mock with no isolation gain. *Affects:* `adapters/base.py`, mock and Meta adapters.

**D-005 `GET /runs/{id}` returns the creature spec inside `result`.**
The "How this was made" panel needs the spec. Embedding it saves a round trip and a `/creatures` endpoint. *Alternative:* `GET /creatures/{id}`. *Affects:* `RunResult` model and TS types.

**D-006 Mock vision identifies by dominant hue, so fixtures read deterministically.**
Mock images go through client re-encoding and server normalisation, so content hashing is unstable. A saturation-weighted mean hue survives re-encoding. The shipped fixture "photos" are painted in the hues that map to their animals (lion.jpg reads as a lion). Faults (`not_animal` on B, `human` on A) override it. *Alternative:* a filename hint in the adapter interface, which leaks mock concerns into the real protocol.

**D-007 Mock image generation paints a deterministic composite "specimen plate".**
The tasksheet default was a fixed fixture image chosen by hashing the two asset ids. Instead, the mock blends A's region over B in a plate layout: still deterministic (same inputs give identical bytes, which a test checks) and still 2 to 4s × `MOCK_DELAY_SCALE`. Screenshots and the demo then show something that reads as a fusion of the two inputs. *Affects:* `adapters/mock/image_gen.py`.

**D-008 Fixture images are generated, not photographs.**
The build environment can't reach Wikimedia or other image hosts (egress policy). `scripts/make_fixture_images.py` paints stylised animals and the edge-case files: tiny, huge, corrupt, gif, pdf, svg, EXIF-rotated-with-GPS, and HEIC. Real photos should be used for the demo video in real mode (P7).

**D-009 Light ("Field paper") is the default theme; dark ("Night herbarium") is the override.**
The tasksheet structure assumed dark default. Natural-history plates are printed on paper, generated images read more truthfully on warm paper, and a dark-plus-neon canvas is the most common AI-tool default (DESIGN.md "Review"). `theme.css` therefore has `:root` = light tokens and `:root[data-theme="dark"]` = dark tokens. The user's choice persists in localStorage.

**D-010 React Flow's structural CSS is vendored into theme.css.**
The single-CSS-file rule rules out importing `@xyflow/react/dist/base.css`. Its rules (line 60 onward) are inlined in section 4b, its own color defaults are dropped, and its `--xy-*` variables are bound to our tokens. *Alternative:* allow a second CSS import for the library, which breaks the rule and leaves its hex colors outside tokens.

**D-011 Port shapes encode type as well as color.**
Image ports are circles (Lapis) and creature ports are diamonds (Moss), so state never relies on color alone (quality floor).

**D-012 Adding images to a canvas with no Fusion node auto-creates and connects one.**
The tasksheet flow has the user drag both connections by hand. For first-run clarity (and the 3-minute demo), dropping 2 images on an empty canvas produces two Image nodes and a Fusion node with A and B already wired, plus a toast ("Press Fuse"). Manual wiring still works everywhere, and each Fusion input slot has a `<select>`, which makes connecting fully keyboard-accessible. *Alternative:* empty Fusion node with a hint. That costs two drags before anything happens.

**D-013 Result node is created when a run *starts*, not when it succeeds.**
This lets the Result node show a skeleton while generating (7.3). Subsequent runs add versions to the same node.

**D-014 Undo/redo restores structure, positions and config, never live data.**
Snapshots hold the whole graph, but on undo/redo a node that still exists keeps its *current* `data` (upload progress, run ids, versions). Otherwise undoing a node move could rewind an upload or delete a result version. *Affects:* `graph/store.ts` (`restore`).

**D-015 Graph schema v0 → v1 migration path exists from day one.**
To prove `graph/migrate.ts` on real data, v0 is defined as the prototype format (`links[]` with `from/to`, node `pos`). Unknown node types load as placeholders; graphs newer than the app open read-only.

**D-016 Runs execute as in-process asyncio tasks; Modal keeps one warm container.**
v1 polls a run that lives in the API process. On Modal, `min_containers=1, max_containers=1` keeps polling on the same process. A heartbeat refreshes `updatedAt` every 10s, and a run whose heartbeat stops for `RUN_LEASE_SECONDS` (180) is marked `interrupted` when read. The local single-process store also interrupts orphans at startup. *Alternative:* `modal.Function.spawn` plus Supabase as the source of truth, which is the right next step when scaling (noted for P7).

**D-017 `X-Session-Id` header for the anonymous session.**
A random id lives in localStorage. Graphs are scoped to it, and the per-session rate limit on `POST /runs` keys on it. It is not auth: accounts come later.

**D-018 Playwright pinned to 1.63.0.**
That matches the browser preinstalled in the build image (`/opt/pw-browsers`). `@axe-core/playwright` brings its own `playwright-core` types, so `AxeBuilder` gets `page as never`.

**D-019 Autosave has a max wait and flushes on teardown.**
Found by e2e: continuous upload-progress updates kept resetting the 500ms debounce, and an app crash cleared the pending save, losing the canvas. Saves now happen at least every 2s during bursts, and on `pagehide` / unmount.

**D-020 New nodes are placed in free space.**
Found by e2e: adding an image to a non-empty canvas could land on an existing node and block its clicks. `findFreeSpot` searches right and down for a gap.

**D-021 Toasts are a region of status/alert items, not a list.**
axe flagged `<ol>` containing `role=status` children. The toast stack is now a `<section aria-label="Notifications">`, and each toast is an implicit live region.

**D-022 `--ink-3` darkened to #646C65 so "faint" text still passes AA.**
axe flagged the fine print at the old value (3.9:1). Faint text is used for catalog numbers and timings, which are still text, so the token now meets 4.5:1 on both paper colors.

**D-023 Screenshot matrix: full states at 1440 (both themes), core states at 1280 and 1024.**
See UI_STANDARD.md. Layout assertions still run the full flow at all three widths.

**D-024 New images are wired into a Fusion node with free inputs.**
Found in PV round pv-2 (PV2-02). After "Add fusion node", adding images left them unwired and placed to the right of the node. Images now go into the selected Fusion node with a free input, or the only one, and are placed to its left. With several candidates and none selected, nothing is auto-wired.

**D-025 After success, the Fusion node shows a summary instead of the step log.**
PV1-04: the step log outweighed the creature. On success the Fusion node shows thumbnail, name, step count and duration, and "Generated fusion", with steps behind a "Show steps" disclosure. While running, only the latest finished step shows its detail. This also delivers 7.4's "image in the Fusion node".

**D-026 Screenshots are quantized to 256-color PNGs.**
Each round is about 18MB raw, about 6MB quantized (`scripts/shrink_shots.py`). Visual baselines stay full-color.

**D-027 F1 pick: anatomy controls (part donor pins).**
It scored highest (27/30). It turns Fuse into a design tool and exercises node config, node version migration (fusion v1 → v2) and user constraints flowing through the planning model. Verify and the field card were deferred (ROUND-1.md).

**D-028 Graph store gains `updateNodeConfig`, and visual baselines are re-approved for F1.**
Config edits are user actions, so each is one undo step (unlike data updates). The baselines changed on purpose, because the Fusion node now shows the anatomy strip.

**D-029 The mock generator reads part assignment from the prompt.**
This keeps the `ImageGenAdapter` interface unchanged (prompt + references), as the real model sees the same input. The mock parses which reference the prompt gives the head to, so pins visibly change the mock plate.

**D-030 Run updates are dispatched through the registry (`NodeDefinition.onRunUpdate`).**
F2 found that the app shell wired the Fusion run handler directly, so any new runnable node would need an `App.tsx` change. `registerRunHandlers()` (in `nodes/registry.ts`) now routes each update to the node type's `onRunUpdate`. The shared run UI (step list, error block, retry countdown) moved to `canvas/RunParts.tsx` for reuse.

**D-031 F2 pick: field-guide card node; provenance is server-written.**
It scored highest (27/30) and is the first post-v1 node type, which tests `ADDING_A_NODE.md` for real. The card's provenance line is composed by the backend, never the model, so the "not a real animal" fixed point can't be lost to a prompt. Size quotes the parents' recorded ranges verbatim (Section 5.4: no midpoints).

**D-032 `Executor.configure(graph, node)`.**
The Field card's config comes from upstream (the Result's selected version), so `configure` takes the graph as well as the node.

**D-033 Real data file is committed (`data/chimera_data.json`, 2.8 MB).**
D1-07 and L1-08 need it in the repo, and Modal bakes it into the image. Removed from `.gitignore`. The invented sample stays for the earlier tests.

**D-034 Hybrid parents resolve to a *set* of animals, tagged with how they matched.**
The real file has three scientific names shared by two tier-1 animals each (*Canis lupus*: gray wolf and domestic dog; *Lama glama*: llama and guanaco; *Sus scrofa*: wild boar and domestic pig). "Canis familiaris" is in neither tier, so it resolves by genus. A parent therefore resolves to every tier-1 animal with that name (tier 2 if none, then genus), and each hybrid match records `matched_via`. Exact-species matches sort before genus-only ones, and the cross direction is kept from the role suffix. *Alternative:* a hand-written synonym table, which is more precise for dogs but hides data problems. Genus matches are visible instead (R-A3-P01 is about exactly this case).

**D-035 Rules run through an explicit rule_id → check table, in two phases.**
The real rules have no machine field, so `backend/app/data/rule_map.py` lists 44 of 130 by hand: 26 run on the two parents (rules_check step), 18 run on the planned fusion (end of compile). The other 86 are data-integrity or mythology-record rules about how the file must be written; they are counted as unmapped in every run, never silently skipped. Severity comes from the map, because the real rules don't carry one. Only rules with a specific detail (or warnings, max 3) go into the image prompt; the real rule texts are long.

**D-036 The planner's allowed body plans come from the data.**
R-A1-01 requires one body plan from the data's set (real: quadruped, biped, winged, finned, multi_legged, serpentine, radial). The previous hard-coded list ("avian", "aquatic", …) didn't match it.

**D-037 Mythology matching: common-name words first, then a broad-word taxon table.**
Mythology components are everyday words. A component matches a parent if it is the parent's common name or one of its words ("eagle" → bald eagle). Otherwise broad words map to a taxon test (`BROAD_TAXA`: bird → class Aves, snake → serpentine body plan, bull → genus Bos/Bison/Bubalus, …). Name matches rank above taxon matches. `verified` is true only when the row's verification text says "verified". No real row does: they are "line-checked by Muse" or "URL loads only", which the API passes through verbatim.

**D-038 The open-weight model id is noted, not used.**
Per the hackathon guide, the open-weight Muse Spark is `meta-models/muse-spark-open-1026` (not the id in the docs). Not used in L1; recorded here for a later "open-weight bonus" task.

**D-039 The planner always runs, even when every part is pinned.**
F1 skipped the planning call when all five parts were pinned, which saved one Spark call. L1-10 requires the plan step to name the creature, so the planner now always runs with the pins as hard constraints (pins still win if it disagrees). The mock planner returns descriptive names ("Lion-headed tiger") instead of portmanteaus. *Alternative:* a separate naming call, with the same cost and more code.

**D-040 Real Meta adapters use the OpenAI SDK with SDK retries off; the image model uses the Responses API.**
`openai.AsyncOpenAI(base_url, api_key, timeout, max_retries=0)`. The shared `call_with_retry` is the single retry layer, so every attempt is charged once by the spend guard and the live budget. Muse Image goes through `client.responses.create` with `input_image` parts; the old `/images/generations` guess is gone. Verified live (docs/LIVE_REPORT.md).

**D-041 Every real call is accounted per step and per run; a hard live budget caps the whole phase.**
`backend/app/adapters/usage.py`:
- each attempt is recorded: step, purpose, model, latency, input/output tokens, outcome, response id
- `Step.calls/tokens` and `Run.usage` carry the per-run totals
- `MAX_TOKENS_PER_RUN` / `DAILY_TOKEN_CAP` join the call caps
- an optional file-backed counter (`CHIMERA_LIVE_BUDGET_FILE`) refuses calls beyond 15 images / 60 Spark calls across processes

Cancelled attempts (per-step timeout) are recorded too. That was missing at first, so two attempts are absent from LIVE_LOG; the counter still caught them.

**D-042 Timeouts from measured latency; one Spark client covers the longest call.**
Identify 20 s, plan 60 s, generate 80 s: about 2× the slowest live calls (9.0 s, 24.1 s, 37.1 s). The Spark client is shared by describe, plan and card, so its HTTP timeout is `max(identify, plan)`. Before this fix, plan calls were cut off at the identify timeout, which caused the one live failure.

**D-043 Mocks replay recorded live shapes through the real parsers; the mock image is WebP.**
Live responses are saved key-free (base64 elided, refused if any credential appears) in `backend/tests/fixtures/recorded/`. Mocks fill those templates and call `parse_*_response`, so a parser change is exercised by every mock test. Muse Image returns WebP, so the mock plate is WebP too. Format is detected by magic bytes everywhere.

**D-044 Live fixtures are AI-generated, generated once.**
Six `muse-image-1.0` text-to-image photos (`backend/tests/fixtures/live/`, with a README saying they are not real photos). `scripts/live_fixtures.py` never overwrites an existing file. Identification accuracy on clean generated images likely overstates accuracy on real phone photos (LIVE_REPORT problem 9).
