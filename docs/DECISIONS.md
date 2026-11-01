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

## U1 UI redesign (ZD design system)

**D-045 Four `-aa` tokens are the only deviations from ZD values.**
ZD (`docs/design-system/zd-tokens.css`) is pasted into `theme.css` verbatim; a unit test checks the file is contained byte for byte. Where a ZD pairing misses 4.5:1, a Chimera token ending in `-aa` is used instead (`contrast.test.ts` asserts both that the ZD value fails and that the `-aa` value passes):

| Token | Light | Dark | Why |
|---|---|---|---|
| `--success-text-aa` | `#147a52` (5.34 on white, 4.78 on its tint) | `var(--success-text)` | ZD light success text is 4.35:1 on white |
| `--danger-text-aa` | `#bf3b45` (5.35 on white, 4.87 on its tint) | `var(--danger-text)` | ZD light danger text is 4.43:1 on `--tint-danger` |
| `--toast-bg-aa` / `--toast-text-aa` | `var(--ink-900)` / `var(--white)` | `var(--surface-modal)` / `var(--text-strong)` | ZD's dark `--ink-900` is near-white, so a white toast would be 1.1:1 |

Each value is darkened only as far as needed. Dark keeps ZD's own text values.

**D-046 ZD replaces "Field paper"; the primary hover keeps the indigo-600 fill.**
The 4.5:1 bar from P-rounds stays. Fuse and every primary button are solid `--indigo-600` (5.51:1 under white). The first draft darkened the hover to `--indigo-700`. The rewritten contrast test caught that ZD's *dark* `--indigo-700` is a light lilac (`#aaa5ff`, 2.2:1 under white), so the hover now lifts the button (`--shadow-cta`, 1px up) instead of changing the fill. `--gradient-mark` appears once, on the brand mark (unit-tested). `check-css.sh` accepts ZD's `[data-theme="dark"] {` block as a token block.

**D-047 Node actions live in a glass contextual toolbar; two actions stay on the card.**
The toolbar (`ui/ContextToolbar`, `role="toolbar"`) shows on hover, on selection and on `:focus-within`. It is hidden with opacity and a transform, never `display`/`visibility`, so it stays in the tab order and the accessibility tree; keyboard users reach it by tabbing into the node. Contents: Input (Replace, Remove); Fusion ("Connect image A/B" selects, Swap A and B, Reset to Auto); Result (Make field card). Two primary actions stay on the card because they are the reason the node exists: **Fuse** on the Fusion node, and **How this was made** on the Result card. The Field card's Download PNG also stays in its footer. A transparent bridge under the toolbar keeps hover alive while the pointer travels to it.

**D-048 The drawer is non-modal, so it has no scrim.**
ZD pairs drawers with `--scrim`. "How this was made" is a complementary panel that explains a node, and the canvas pans so that node stays visible beside it (`SidePanel`). A scrim would hide what it explains and imply modality. The shortcuts dialog, which is modal, uses `--scrim` with `--blur-scrim`.

**D-049 Input titles are the identified species, looked up in the frontend.**
`nodes/image-input/species.ts` searches run results (newest first), then Result node versions, for a parent whose `assetId` matches the input, and shows `match.commonName ?? reading.commonName`, capitalised. Before any run identifies it, the title is "Animal photo" (the Fusion portrait reads "Image A"). The filename appears only in the photo's alt text. No backend change.

**D-050 The anatomy body diagram is drawn from a region list.**
`nodes/fusion/bodyRegions.ts` holds one entry per part: outline path, optional larger hit path (limbs, tail), label point and badge point. Regions are SVG `<g role="button" tabindex="0">` with the F1 aria-labels ("Head from A"). Click, Enter or Space cycles Auto → A → B. A pinned region fills with its donor colour (`--cat-blue` A, `--cat-teal` B, mixed into the card) and shows the donor's circular portrait plus a letter tag, so the colour is never the only signal. The diagram is hidden while a run is active (pins can't change then), which keeps the node compact. L2 wings = one new entry here plus its id in `PARTS`.

**D-051 The drawer's lead and numbers are built from structured fields.**
`nodes/result/summary.ts` writes 2–3 sentences from `partDonors`, `realHybrids`, `mythology[0]` and warning counts; it never quotes model prose. The planner's `rationale` sits in a collapsed "Planner notes" section. Stat cards show match confidence per parent, rules run (`rulesSummary.run` of `total`), warnings, and tokens from the run's `usage.tokens`. When the run is not in memory (e.g. after a reload) tokens read "unknown", never 0. Mythology rows always read "Resembles X (culture)" with an "Unverified" pill and the row's own verification text, whatever `verified` says (D-037): the UI never calls a resemblance verified or confirmed.

**D-052 Screenshots and visual baselines use real generated images.**
`tests/visual/liveSeed.ts` puts recorded L1 results on the canvas. It adds the live input photos through the file picker (a real upload), uploads the live fusion WebP, and then loads a graph with a Result node built from `docs/live/fusions/<case>.json`. The recorded run goes in through the existing `loadGraph` and `setRun` test hooks, so test hooks are unchanged. States that need a real mock run (faults, field cards, versions) keep it, but any generated asset is served as the live fusion image for that pair, so no flat mock drawing appears. Caveat: mock vision identifies by colour, so in mock-run states the species labels are mock readings (e.g. the live lion photo is read as "Red fox"). The hero states (canvas, result, drawer, body diagram, baselines) all use the live specs.

**D-053 Fusion ports sit beside the parent portraits.**
Input ports are fixed at 98px and 130px from the Fusion card's top, and the output port at 114px, so connections meet the portraits whatever the card's height (running, failed, done).

**D-054 The Fusion node no longer shows the result thumbnail (supersedes part of PV1-04).**
PV1-04 put a thumbnail in the Fusion node so the creature led. In U1 the Result card is the hero (about 2× an input card), so the Fusion node shows only status, the step Timeline (behind "Show steps" when done) and Fuse. TASKSHEET 7.4's "image in the Fusion summary" is now met by the Result card beside it.

**D-055 Guanaco binomial corrected to Lama guanicoe; close-relative label says "speculative".**
`data/chimera_data.json` listed the guanaco as *Lama glama*, which is the llama, so the two animals shared a binomial and `Taxonomy.resolve("Lama glama")` could return either. Only the `scientific_name` field of the guanaco's `animals` entry changed (the two guanaco measurement rows have no binomial field). The cama override in `data/evo_known_pairs.json` matches by animal id, so dromedary x guanaco and dromedary x llama both still resolve to `cama` (tested in `tests/evolution/test_e2_review_fixes.py`). The documented-hybrid lookup now matches the cama record (*Lama glama* mother) only for the llama, which is what the source says. Separately, `LABEL_CLOSE` in `evolution/route.py` now reads "speculative hybrid of close relatives, no documented cross": a same-genus pair with no recorded cross is a guess, so the label must not suggest more than that.

**D-056 Real hybrids get no habitat step, and their prompt describes a known animal (E2c).**
A real hybrid is a known pair in `data/evo_known_pairs.json` or a cross documented in `chimera_data.json`: route mode `hybrid` with the label "real hybrid precedent" (`route.is_real_hybrid`). Close relatives with no documented cross ("speculative hybrid of close relatives") are not real hybrids. A documented hybrid is a known animal, not an adapted design, so `finish()` calls `habitat.clear_habitat` instead of `apply_habitat`: earlier habitat deltas are undone, `adjustments` is empty, `visible_trait` is `None`, and RC-R4-11 (one visible habitat trait) is neither traced nor penalised for these plans. The habitat name is kept as context only. The render prompt (`prompt.compile_real_hybrid`) opens with the hybrid's name and cross ("A mule (donkey sire x horse mare), a real hybrid animal."). It describes the frame in host terms first and in full, then names the other parent once in a single grouped clause ("with the donkey's long ears, short thick head, ..."). The wording comes from a `prompt` block on each known pair. Why: in E2b the per-detail "donkey ..." lines outweighed the horse frame, so the mule rendered as a donkey. The critic counts the hybrid's own name or an alias ("mule", "pizzly") as naming both parents on this route only.

**D-057 Open-world resolver: GBIF is the only taxonomy source for new animals, and only an EXACT species match is accepted (E4).**
`evolution/resolve.py` resolves a parent in this order: `chimera_data.json` animals, the learned cache (`data/learned_animals.json`; in mock mode `<local_data_dir>/evo/`), then the open-world path. On that path Muse Spark identifies the name or photo, and GBIF's species match (`strict=true`, `kingdom=Animalia`) must return `matchType` EXACT at species rank or below. An EXACT match at genus rank ("Pangolin") is not a species, so it returns `needs_choice`, as do FUZZY, NONE and HIGHERRANK. A binomial already in the `tier2_animals` table uses that stored GBIF row with no new call (source "chimera_data.json tier2 (gbif)"). Muse Spark fills the body and life traits, visible features, mouthparts and breathing organ, each marked `model-estimated`. Model claims of crosses are stored as "unverified claim" and never read by routing. A cached id is never overwritten: a second learning for the same id keeps the first entry. Ambiguous names ("pangolin") pick the most common species, say so, keep the alternatives, and store an alias so the note survives the cache. When GBIF is down, taxonomy is left unknown (empty class and genus), so the pair routes as a chimera with the speculative label; such an entry is not saved, so it can be learned properly later. A mythic name found in the `mythology` table is refused without any model call, with a mythic-mode suggestion built from its component animals. Database animals get breathing and mouthparts from project defaults by class (mammal teeth by diet) in `evo_config.json function_defaults`, with per-animal overrides as data (the axolotl's external gills), and their provenance says "project default". In mock mode a photo is read by the app's mock vision adapter, so photo tests keep their meaning.

**D-058 Routing for any pair, by taxonomy distance; precedent only from data; "mythic composite" (E4, RC-R9-01).**
`route()` now records the closest shared rank (`taxonomy_distance`: species, genus, family, order, class, beyond class, or unknown) in `Route.distance`. The decisions are unchanged: known pair or documented cross (only `evo_known_pairs.json` or the `chimera_data.json` hybrids table) is a real hybrid; the same genus is a "hybrid candidate" with the speculative close-relatives label; everything else is a chimera, or a mythic composite in mythic mode. When either parent's taxonomy is unknown (GBIF down), neither the documented-cross table nor the genus test is consulted, so the pair is a speculative chimera. `Animal.claims` (model claims of crosses) is never read by routing. The mythic label is now "mythic composite" (was "mythic design"), and the six-limb label says "mythic composite" too. The card's `kind` comes only from the RC-R9-01 vocabulary: hybrid, chimera, mythic composite. A same-genus pair with no documented cross keeps the word "speculative" in front of hybrid, so the unqualified word is used only on the real-hybrid route. A new test scans every string literal in `app/evolution/*.py` for database animal names and known-pair names. It found two: the RC-R2-08 check named lion and tiger, and the RC-R2-11 check named `hybrid_bear`. Both now read the pair's cards from data.

**D-059 Function audit: code decides where a card covers the case, one Spark call judges the rest, before the render (E4, R9 section 2).**
`evolution/audit.py` runs in `finish()` right after the physical checks and fills `Genome.audit` with one entry per function (breathing, feeding, support, movement, heat, senses). Code decides breathing when the body's organ is known (RC-R9-03, RC-R9-07, RC-R9-12), feeding for teeth or a beak (RC-R9-04, RC-R9-05), support from the posture and size checks (RC-R3-06 to RC-R3-09, RC-R9-06, RC-R9-08), movement from flight anatomy, the ability match and part jobs (RC-R3-02 to RC-R3-04, RC-R9-12, RC-R9-13), heat from a profiled habitat (R4) and senses from the head (R6). Anything else is `pending`: in `realize()`, before the prompt is compiled, one Muse Spark call (`evo_audit`) judges every pending function from a plain-words summary of the plan. A model repair is written into the plan as a note, so the prompt shows it. A missing or failed judgment becomes `labeled` with an "unchecked" label, never a pass. The body's breathing system belongs to the host (both parents in a hybrid). A donor's visible external gills are a donor appendage. On land they have no job (RC-R9-12), so realistic mode drops them; other modes keep them as display frills and say they do not breathe. Every audit or model text that mentions oxygen is hedged as debated (RC-R9-09). New hard checks: RC-R9-01 (labels never mixed), RC-R9-02 (all six functions audited; skipped for a model plan before `finish()`), RC-R9-03, RC-R9-06 and RC-R9-09.

**D-060 Fiction budget and design modes; speculative is the default (E4, R9 section 3).**
`Genome.design_mode` is `realistic`, `speculative` or `mythic`, set by the user, never by the model (it is code-owned in the live plan schema). `/evo/fuse` takes `mode` (the old `myth` flag still means mythic) and `compare`, which renders the realistic version plus `compare_with` (speculative or mythic) as a pair. The mode is part of the cache key. The default is speculative: before E4 the engine already allowed one bent rule with a label (for example arthropod parts at size), so making realistic the default would have quietly changed every existing creature. The budget is in `evo_config.json`: realistic 0, speculative 1, mythic 3. "Several" is a product decision that R9 leaves open. `fiction.settle` takes the audit's needs and grants licenses up to the budget, unrepairable needs first. It repairs the rest where a repair exists (six limbs become forelimb wings; gills on land get assumed lungs and vestigial slits) and labels what is left. A license can only be made for a card listed as bendable in R9 3.2. The honesty rules and the believability floor (`never_licensable`) are refused by `make_license`. Each license's compensation is written into the body (and, for legs, the limbs) note and into the prompt as "Declared fiction: <rule>, shown with <compensation>". The honest check label (for example "speculative: arthropod parts at large size") stays when a license is granted: a license declares a bend, it never hides one. A mythic design with licenses gets the RC-R9-11 label that believability drops with each extra license. RC-R9-10 is a hard check: licenses within the budget, only on bendable cards, and each compensation present in the plan.

**D-061 Checklist critic on every route; the open critic is a logged second opinion (E4, supersedes E2d item 4).**
`judge.generated_checklist` builds 4 to 6 yes/no items from the plan for every route, in this order: the frame (host body shape, or an in-between body), the head with visible eyes, each license's compensation, donor parts (wings, signature parts, kept gills), donor surface patches, and the coat pattern. A short list is padded with floor items ("feet resting on the ground"). A hand-written checklist in `evo_known_pairs.json` still wins on the real-hybrid route. The one checklist call per image also returns the creature count, which feeds the silhouette rule that counts a mask in pieces as one creature (E2b), and the animals it sees, which feed the third-animal check and its single re-render. The forced choice is now offered on every route ("a mix of both" replaces the hybrid's name off the real-hybrid route) and is logged, not scored. The open critic ("which animals do you see") runs once on the full image as a logged second opinion (`judge.open_critic`); it is never scored, and its failure never fails the judge. That adds one Spark call per render: plan, polish, checklist, thumbnail checklist and open critic make 5 (6 with an audit call). The output card adds `kind` (RC-R9-01), `design_mode`, `can_it_live` (function, result, detail, cards, decided by code or model), `licenses` with compensations, and `provenance` (per-fact sources for each parent, plus unverified model claims). Every prompt, in every mode and on the real-hybrid route too, carries the prosaic-detail line from `evo_config.json` (RC-R9-15; the specific cues are project choices, as R9 says). Donor appendages (for example kept gills) now reach the prompt as "small display frills".

**D-062 A part the audit drops stays dropped: flagged on the plan, stripped from notes, checked as absent (E4 live fix).**
In the live realistic axolotl x pangolin, the audit removed the axolotl's external gills, but the accepted model plan's notes ("axolotl gills attached externally") went into the prompt and the gills were rendered. The generated checklist had no item about gills, so the image scored 1.0. Now a dropped part is recorded as a `dropped part: <part>` flag on the body trait (the genome schema is unchanged). Note clauses that mention it are removed from the plan, and the prompt compiler treats any remaining mention as a plan conflict and leaves it out. The checklist gains a "no <part>" item. A regression test replays the live model's words. The image was not re-rendered. Also recorded: a cached creature does not keep its `model_plan` outcome. The live outputs were rebuilt from the cache with `scripts/e4_live.py --recover` at no cost, after the script's own folder bug.

**D-063 RC-R3-01 and RC-R3-02 cover vertebrate wing donors only; insect wings are a body-plan license on a dorsal mount (S2, E4c).**
A bird's or bat's wings are built from forelimbs, so they still take the forelimb slot (or, in mythic mode, form a labeled six-limbed design). An insect's wings are not forelimbs. In E4 the beetle x bear plan put beetle wings in place of the bear's forelegs, and the image drew them on top of four legs. Now:
- **Where they go:** a flying non-vertebrate donor (movement includes "fly" and its class lists wings) brings insect wings as an appendage "on a dorsal mount", and the vertebrate host keeps all four legs.
- **Old plans:** a plan that put insect wings in a limb slot is repaired the same way.
- **License:** the mount is a new bendable entry `insect_wings` in `evo_config.json`. It cites RC-R3-09, the card that names insect wings as an arthropod part, because R9 3.2 has no closer card. Its compensation is "insect wings rising from a raised, plated mount between the shoulder blades, with all four legs kept".
- **Over budget:** the repair drops the wings (`dropped part: wings`, checklist item "no wings"). In speculative mode the one license normally goes to arthropod parts at large size, so a big host loses the insect wings. A small host such as a rabbit keeps them under the one license. Mythic mode keeps them as a second license.
- **Hard check:** the RC-R3-01/02 hard check now looks only at vertebrate wing donors.

**D-064 Class part lists (`data/class_parts.json`, "model-estimated, reviewed") gate every donor part and every saved trait (S2, E4c).**
- **What the file holds:** for 11 classes (Insecta, Arachnida, Malacostraca, Mammalia, Aves, Reptilia, Amphibia, Actinopterygii, Chondrichthyes, Cephalopoda, Gastropoda), the allowed body plans, coverings, mouthparts and breathing organs. It also lists the visible parts, most recognizable first, each with aliases, an attach slot, a prompt shape and a job, plus a `never` list of parts the class cannot have. `Elasmobranchii` maps to Chondrichthyes. I wrote it from standard anatomy and reviewed it against the database (every database insect is `multi_legged`); owner review is pending.
- **Donor parts:** `parts.fix_parts` runs in `seed_plan` and in `finish`, so model plans are checked too. An invalid part is replaced by the donor's most recognizable valid part: the first of the donor's own visible features that names a valid part, else the class's first part. A tail-slot replacement stays in the tail trait; any other replacement becomes an appendage and the tail goes back to the host.
- **Limb slots:** a slot whose kind the donor's class does not have goes back to the host.
- **Saved traits:** body plan, covering, mouthparts and breathing must be in the class lists. Free-text features are rejected only when they name a forbidden part, because a positive list cannot cover phrases like "friendly expression". Learned entries are checked when learned and again on load. A correction is applied with its old value kept in `corrections` (by, at, reason), and its provenance becomes "model-estimated, corrected by class_parts.json".
- **The beetle:** the learned European rhinoceros beetle had body plan `multi_legged` + `winged`. "Winged" makes it a forelimb wing donor and gave it the bird patch regions (forequarters and neck), so it was corrected to `multi_legged`, logged in the entry. Its signature "jointed tail segments" (the arthropod default) is not an Insecta part, so it is replaced by its head horn.
- **Part jobs:** the part-job audit falls back to the class list's job when `part_jobs` has no entry. The `part_jobs` water rules still come first.

**D-065 Hosted prompts: one grouped donor clause, parts as materials and shapes (S2, E4c).**
Chimera and mythic prompts (`prompt.compile_hosted`) now give:
- **Host clause:** the host's body, legs and own surface.
- **Donor clause:** one grouped clause, "from the <donor>, as parts and materials on the <host>'s own body: …". The donor is named once there. Its head (mythic swap), wings, dorsal insect wings, tail part, appendages, surface patches and patch pattern are each described with the class list's shape and surface wording ("hard, glossy chitin plates with fine seams", "a single curved horn of hard, glossy chitin rising from the brow"), not as "<donor> exoskeleton".
- **Pattern exception:** E2b's rule that a pattern is always "<animal>-type <type>" is kept, so a patterned donor's type designator may appear a second time.
- **Silhouette:** recomputed last in `finish()`, and `route.silhouette_issues` must find no disagreement with the final limb plan (forelimb wings, six limbs, dorsal mount, tail part, two hind legs only with wing forelimbs).

**D-066 The render prompt reads only structured fields; the forced choice is removed (S2, ROADMAP Q4 and Q6).**
`compile_prompt` (hosted, hybrid and real-hybrid) builds the prompt only from the plan's structured fields (silhouette, host, limb plan, traits' donors, operators, regions, strengths, parts and flags, licenses, habitat cue), the data tables (`class_parts.json` shapes, coat patterns, known-pair prompt blocks) and a new code-owned plan field, `render_details`.
- **`render_details`:** holds the visual details code adds while checking and repairing: a deep keel, posture, thicker limb bones, jointless soft parts, a deep chest at size, digging forelimbs, vestigial gill slits.
- **Rebuilt each pass:** `finish()` clears and rebuilds it on every pass.
- **Not in it:** model-judged audit repairs, which stay on the card, and license compensations, which reach the prompt once through the license clause.
- **Notes:** trait notes, which a model plan can write, are kept for the card and logs but are never read by the compiler.
- **Hybrid extremes:** the beyond-both-parents note on hybrids is now phrased from the BLEND value and flag.
- **Forced choice:** removed from the checklist schema, instructions, request, parser (an old recording's `choice` is ignored), the EvoSpark protocol (`checklist(image, items)`), the mock and the judge verdict. It answered "a mix of both" on every image and was never scored.

**D-067 The plan as six typed operations; code fills every derived list (S2, ROADMAP 5b).**
The step-3 agent never writes a whole plan: S1 showed Spark Open looping inside an unbounded `card_trace` array until it hit the output-token limit. `ops.PlanSession` (opened with `engine.plan_session`) edits a plan through six operations:
- **`set_host(animal)`:** chimera and mythic routes only.
- **`set_region(region, donor, operator)`:** head, tail and forelimbs take PICK; the surface regions take PATCH, OVERLAY, or PICK with the host to give a region back. At most `max_patches` patch regions; an overlay needs a donor that has a coat pattern; a tail part must be in the donor's class list; forelimbs only from a wing-bearing donor. Hybrids take head or tail only, and real hybrids take none.
- **`set_habitat(name)`:** one of the profiled habitats.
- **`set_mode(mode)`:** license requests beyond the new budget are removed, with a warning.
- **`add_license(rule, compensation)`:** the rule is a bendable id or its card; it must be a rule the plan really bends, within the budget, never an honesty or floor rule, and the compensation is 1 to 240 characters with no franchise names. Requested licenses take the budget first, with the agent's own compensation wording (`settle(requests=…)`).
- **`drop_part(part, reason)`:** the part must be in the plan, and the reason is required.

How a call works:
- **Rebuild:** the session keeps the accepted operations as intents and rebuilds from `seed_plan` plus the intents plus `finish` on every call, so code always fills `card_trace`, labels, checks, audit, licenses, `render_details` and the silhouette.
- **Errors:** an operation with bad arguments, or one whose result breaks a hard card, is not applied. It returns `OpError`s (code, message, field, hint, valid values) and leaves the session unchanged. Every call is logged.
- **Legacy path:** for the step-5 comparison it keeps working, but `labels`, `processes` and `card_trace` are now code-owned (`CODE_FIELDS`) and are no longer in the model's plan schema.

**D-068 Web-cited traits: Meta Spark 1.3 with web search, a citation per field, verified against the pages it opened (S2, ROADMAP Q5).**
- **New resolver step:** for any animal not in `chimera_data.json`, the resolver's trait step is now `cite_traits`, a Meta Responses API call with `tools: [{"type": "web_search"}]` and a strict schema in which every trait field is `{value, source_url, evidence}`. It gets its own 240 s timeout.
- **Verification:** a field counts as web-cited only when its `source_url` is a page the model opened (a `web_search_call` `open_page` action) or a `url_citation` annotation in the same response. A URL the model merely wrote down is not a citation, and that field stays "model-estimated".
- **Storage:** verified fields are stored with provenance "web-cited" and their URL and quote in `citations`. The cited values are cleaned to the engine's vocabularies (duplicates removed) and checked against `class_parts.json` like any saved trait.
- **Fallback:** if the cited call fails, the old model-estimated trait call runs and `traits_note` says why. A budget stop is never swallowed.
- **Re-resolving a known animal (`Resolver.cite`):** each field is reported as matched (same value, same set, or overlapping range), corrected (it differs) or uncited. A learned entry takes the cited value and keeps the old one in `corrections` (by "web-cited", with the URL). A database animal is compared only: `chimera_data.json` stays the source of truth.
- **Known limit:** a verified URL proves the page was opened, not that the quoted evidence supports the value. The live run has a few weak sources and quotes, listed in `S2_FIXPACK.md`.

**D-069 Spark calls are routed per call type; Spark Open where S1 showed parity, Meta for plans and traits (S2, ROADMAP 5b).**
- **The table:** `evo_config.json` `routing` sends `identify`, `checklist` (full image and thumbnail), `polish` and the logged open `critic` to Muse Spark Open on Baseten. It sends `write_plan` (the legacy full-plan path), `learn_traits`, `cite_traits`, `judge_functions` and `vary` to Muse Spark 1.3 on the Meta API.
- **Output caps:** each Spark Open call carries a `max_tokens` cap at about 3x the largest output seen in S1, reasoning included: identify 5000, checklist 6000, polish 15000, open critic 4000.
- **Router:** `routing.RoutedSpark` wraps the two adapters (built in `live.build_live`). A Baseten failure, including an unreadable answer from one cut off at its cap, falls back to Meta once, and the router logs both entries. A budget stop is never turned into a fallback. Without a Baseten key everything goes to Meta, with a note.
- **Provider on records:** every usage record carries `provider` (from the endpoint). `LIVE_LOG.md` writes the model as `provider/model`.
- **Provider on the card:** each creature's document and card carry `providers`: the provider and model per call type, any fallbacks, plus `meta:` Muse Image and SAM 3.1. Mock mode reports the mock adapter.

**D-070 Inspect and one plan-worded edit turn replace the E2b third-animal re-render (S2, ROADMAP Q2, Q3, 5b).**
`inspect.plan_items` turns the plan into checklist items with a kind, whether it is structural, an optional SAM prompt and a fix sentence written from the plan. The structural items are the frame, the head, each license compensation, each dropped part ("no wings"), each donor part (wings, dorsal insect wings, a tail part, appendages such as a horn or gills) and "only parts and materials of the donor, no whole donor animals on the body". Surface and pattern items are informational. The generated checklist is these items, structural first, and its cap rose from 6 to 8 (D-061) so they fit in the one critic call that inspect reuses.

How each item is judged:
- **Planned parts:** a part passes when the critic says yes or SAM 3.1 finds it (fill ≥ 0.2 percent), and fails only on a critic "no" with no SAM mask.
- **Everything else:** absences, frame, compensations and "no whole animals" are decided by the critic. An empty SAM mask never fails an item on its own (S1: SAM missed five beetle bodies), and absences are never SAM-tested.
- **Count and third animals:** two or more creatures, or a third animal, are structural failures.
- **Real hybrids:** a hand-written checklist is descriptive, so only the count and third animals apply.

What happens on a failure:
- **One edit turn:** `realize()` makes a single Muse Image edit turn (`previous_response_id`). Its instruction joins the fix sentences of up to 3 failed items, each worded from the plan ("Show the planned … as …; keep everything else the same"), never from the symptom. S1's "remove the beetle bodies" also removed the planned chitin plates.
- **Re-inspect:** the edited image is judged and inspected again.
- **Which image is kept:** the edited image, unless it has more structural failures than the first render, in which case the first is kept, with a warning. A miss that survives the edit is kept with the warning "structural miss after one edit turn: …".
- **No loop:** there is only ever one edit.
- **Errors:** an edit-call error keeps the first render, with a warning; a budget stop is raised.
- **Records:** the document carries `inspect` (before, edit, after, kept) and `response_id`.
- **Mock:** the mock image generator supports `previous_response_id` edits.

**D-071 Code-owned labels are checked on the finished plan only (S2 live finding).**
Part 3 made `labels` code-owned: they leave the model schema, the skeleton's labels are copied onto a model plan, and `finish()` adds the check labels. But the pre-finish hard check of a model plan (`final=False`) still demanded the RC-R3-09 arthropod-size label and the RC-R3-02 six-limb label, which only `finish()` adds. So every large-arthropod model plan was rejected and the code skeleton used. The first live beetle x bear (run 1) hit this: "rejected, code skeleton used (RC-R3-09: arthropod parts at large size without the labeled reason)". Both label requirements now apply only when `final` is true, after `finish()` has run the physical checks that add them. The finished plan is still checked with the label required. A regression test fuses the beetle x bear in mock mode and requires `model_plan == "accepted"`.

**D-072 Inspect uses a plan-blind, two-critic protocol; "uncertain" is a fail signal (S3a, ROADMAP Q3, 5b).**
The S2 inspect reused one plan-worded checklist and missed 3 of the 6 owner-labeled failures, including the run-1 whole-beetle plate. Inspect now runs `critic.protocol` on every route:
- **Steps:** a free description from the image alone, then counts; a balanced checklist with at least half the questions expecting "no", worded as visible features with the expected answers never sent; integration questions for protective donor coverings.
- **Two critics:** Spark Open and Meta Spark 1.3 answer independently. Disagreement or "unclear" is `uncertain`, and counts as a failure for the edit turn and the agent.
- **Description check:** code matches each description against the plan for extras and omissions.
- **SAM:** it may only confirm presence.
- **Kept:** the S2 version stays as `inspect_checklist`, the calibration baseline.
- **Cost:** 4 Spark calls per inspect, accepted on quality grounds.
- **Calibration:** on the gold set, confirmed on a fresh run: each critic alone and the pair catch 6/6 failures with 0/5 false alarms.

**D-073 Calibration rules for the critic (S3a part 3).**
- **Answer format:** answers come back as a bare ordered list. Copying the question text made Spark Open run to its 8000-token cap on 4 of 11 calls. A failed critic call is retried once.
- **Description matching:** negated clauses are dropped; wing cases are plates, not wings; a feather ruff is not a mane; one dorsal stripe is not a striped coat.
- **Integration scope:** integration questions apply only to protective coverings (RC-R10-12 scope). The presence of a soft surface patch is informational, as in S2.
- **Hybrid frame:** real hybrids get a "mixing both parents" frame question.
- **Record:** every iteration is in `benchmark/calibration/ITERATIONS.md`.

**D-074 A web citation counts only after code verification (S3a part 4).**
- **The checks:** a cited field stays web-cited only when all of these hold:
  - its page is tier 1 or tier 2 in `data/source_tiers.json`;
  - the page fetched in code (PDFs via pypdf, a new dependency) contains the model's quote;
  - the page names the animal.
- **Rejected and unlisted:** stores, dictionaries, children's encyclopedias and general wikis are rejected. Unlisted domains are not accepted until added with a reason.
- **Fallback:** a failing field falls back to `model-estimated (citation not accepted: <reason>)`. For learned animals, the old citation moves to `rejected_citations`.
- **S2 re-check:** of the 4 S2 animals, 16 of 50 citations survive. Ten fail only because the site blocks automated fetches.
- **Not used:** an archive-copy fallback for blocked sites. It was denied as a workaround of the site's block.

**D-075 Research card IDs may have two-digit doc numbers (S3a part 5).**
Both research scripts matched `RC-R\d-` and would have skipped R10 silently. They now accept `RC-R\d+-` and sort by doc number. RC-R10-12 to 14 are added, keeping the owner's numbers; RC-R10-01 to 11 are not in the repository.

**D-076 The default prompt compiler does not change after the integration experiment until the owner rates it (S3a part 8).**
- **Findings:** rewording the covering as a replacement (V1, V2) fixes scattering on both pairs. A hard shell over fur still reads as laid on top, mostly an image-model limit. The shoulders signal is a plan conflict: the plan says back and flanks, RC-R10-13 says shoulders to hips.
- **Proposed after the ratings:** V2 wording for protective coverings; V5 (growth by edit) only as a repair; and in the plan, a dorsal shield covering shoulders to hips.

**D-077 The owner's R10 cards are in; mass never breaks a host tie (S3b part 0, RC-R10-01).**
The owner supplied R10 with RC-R10-01 to 14, the verbatim S3a review and `plan_evolution_sim.py`; they were placed in `research/`, `benchmark/` and `scripts/`. RC-R10-01 is hard ("neither size nor mass decides which parent wins"), and `choose_host` broke equal-structure ties by mass. On a tie, the first-named parent now hosts by default, logged with RC-R10-01, and the user or agent switches it. A hard-card test swaps the masses and requires the same host. Four E4 tests that relied on the pangolin hosting by mass now name the host. Consequence seen live: tortoise × goat hosts the tortoise. A real tie rule should come from RC-R10-02 and 03 (per-region fitness, empty niches); that is not done here.

**D-078 RC-R10-15 and RC-R10-16 VERIFIED; cards may be superseded (S3b part 1).**
- **Sources:** both checked against the fetched page. UC Berkeley Understanding Evolution, homologies and analogies, for RC-R10-15. NC State General Entomology, arthropods ("exoskeleton (and its jointed appendages)", "membranous joints"), for RC-R10-16.
- **Supersession:** RC-R10-13 carries `superseded_by: RC-R10-15`. The research scripts and loader accept the field, keep the card and never apply it.
- **verify_research:** the run had 2 failures, both on the owner's RC-R10-07 source (`ria.ua.pt`). Every request to that host, including its home page, is reset from this network and from a second fetch path, so the source is unreachable rather than shown dead. Its status is left as the owner set it.

**D-079 Every donor feature is a typed transfer (S3b part 2, RC-R10-15).**
- **The record:** class (material, homologous, non-homologous), anchor, extent with a reason, scale rule, connections, identity cues, and who set it. Code derives it from `data/transfer_rules.json` in `finish()`.
- **Classes:**
  - Homologous needs a matching host structure (both vertebrates, the host has the slot).
  - Non-homologous back shapes (elytra) fold into material.
  - Extents come from the donor's own covering system (an exoskeleton covers the whole body; pangolin scales leave the belly and face soft); a patch-type covering keeps its plan regions.
- **Connections:** a part on the head pulls the covering onto the head and connects to it.
- **Regions:** the covering's extent becomes the coat traits' regions as one layer (RC-R10-06), exempt from the patch-count soft penalty.
- **Typed operations:** set_transfer_class, set_extent, connect_features and set_identity_cues. An exoskeleton extent that leaves the legs bare needs a stated reason; identity cues must be positive and must not name the other parent.

**D-080 The default compiler words a covering from its transfer (S3b part 3).**
- **Wording:** the V2 replacement wording without donor-icon shapes: material, extent, "each plate sized to the host's own body segments and muscle masses, one per segment or muscle mass", "joined by flexible cuticle at every joint", "conforms to the host's body". The host keeps its covering and pattern only on the uncovered zones.
- **"Bands":** dropped ("flexible bands" tripped the pattern-leak check; an image model may draw stripes).
- **Parts:** worded by class, anchor, connection and identity cues.
- **Tests:** S2 tests that pinned the old horn shape text were updated to the new intent.

**D-081 Growth by edit is an option for coverings only, with a drift check (S3b part 4).**
`fuse(growth="edit")` works in four steps:
1. Render the host with its discrete parts (never grown by edit).
2. Grow the covering in one edit, worded from the transfer.
3. Compare head, walking-leg and tail counts from both critics' plan-blind descriptions, before and after.
4. On drift, render the full plan in one pass instead.

No repair edit follows a growth edit. The task's "fall back to the first-pass render" is read as the first-pass render of the full plan, because the plain-host image lacks the planned covering. The describe call now also counts tails.

**D-082 New critic items; Meta Spark decides inspect (S3b part 5). Pending owner confirmation.**
- **New items:** follows the body vs keeps a separate outline; plates sized to the body; legs covered and abrupt stop (armor); parts connect; an open "which animal did this part come from" per discrete part, scored by code ("rhinoceros" fails for a beetle's horn).
- **Placement:** going beyond an extent with no reason (an old plan's bare regions) is informational.
- **Recalibration:** 33 owner-labeled images (18 fail, 15 good).
  - Spark Open calls grown pangolin scales on an axolotl "laid on top" in nearly every owner-good image, and the S3a pair rule inherits that: 9 to 11 false alarms of 15.
  - Meta Spark alone: 18/18 caught, 3/15 false alarms, in two live runs.
- **Configuration:** `critic_decision` is `primary: meta_spark`. Spark Open still answers every image, and its disagreement is kept on each row.
- **Why confirmation is needed:** this departs from the owner's S3a rule ("disagreement is a fail signal"). It is the configuration that meets the owner's target on the owner's labels. Setting the mode to `pair` restores the S3a rule.

**D-083 Validation fixes (S3b part 6).**
Held-out and live runs exposed three general bugs:
- A model-written plan prefixed a part with the parent's id, so the part got no transfer. Parts are now normalized to the common name.
- Plates made a bear's short tail visible (0 → 1 tails), and that counted as drift although the plan has a tail. Drift now means a count that changed and also differs from the plan.
- Turtles and tortoises have beaks, which the description matcher did not expect.

Each has a test. The two affected runs were rerun beside the originals (`r1_fix`, fresh cache; the first rerun attempt hit the engine's fuse cache and was discarded).

**D-084 Owner decision D1: Meta Spark decides inspect (S3c).**
`critic_decision` stays `primary: meta_spark` by default, confirming D-082. Spark Open still answers every item; its answers are kept on each row (`pair_status`) as information, never as a fail signal. `mode: pair` still restores the S3a rule.

**D-085 Owner decision D2: no tie rule for the host (S3c, RC-R10-01).**
The first-named-parent rule from D-077 is removed. On a structural tie, `route.host_tie` reports both parents. `propose_candidates` (the agent) returns a candidate for each host, and the agent picks one with a stated reason, or calls `ask_user` in an interactive run. The fixed pipeline no longer chooses: `fuse` on a tie without `host` returns `needs_choice` with both options (VALIDATION_FAILED, details `needs_choice: host`). The plan is still built on the sire as a provisional frame so the candidates can be compared.
- Tests that fused a tied pair (lion x eagle) only to exercise something else now pass `host="sire"`. None of them was about host choice.
- *Alternative:* keep a default for the fixed pipeline. Rejected: any default is a tie rule by another name.

**D-086 Owner decision D3: the axolotl's external gills are its identity part (S3c).**
The gold-set label for `e4/b_axolotl_x_pangolin` changes from fail ("external gills on a land creature") to good, marked "owner decision S3c (D3)", in `gold_set.json` (now 5 fail, 6 good) and `gold_set_s3b.json` (17 fail, 16 good). The S3a and S3b calibration numbers were computed on the old label and are not recomputed here.

**D-087 Owner decision D4: one declared identity part per donor (S3c, `identity.py`).**
- **Choice:** the identity part comes from the donor's own visible features, in their listed order. It is the first feature that names a class part the donor has in that form. Coverings and back shapes (carapace, wing cases) are material, not parts. A sex or age qualifier ("in males") is dropped from the wording. The source is the donor's provenance for that field (web-cited URL, model-estimated, or the data file).
- **Fallback:** a donor with no recorded features at all may keep a class part already in the plan, marked model-estimated. It never gets a part added.
- **Enforcement:** where the donor has no homologous structure on the host (an arthropod on a vertebrate):
  - speculative and mythic modes keep exactly the identity part and drop every other donor-shaped part, including a class signature tail and dorsal insect wings. Each drop is logged as a Check;
  - realistic mode drops them all, so identity is shown only by color, texture and material.
- **Vertebrate donors:** keep the existing homologous-part rules. Their identity part is declared from the parts already in the plan, never added or dropped.
- **Agent pick:** the agent changes the identity part with `set_identity_part(donor, part, reason)`, validated against the same candidates. Code never re-adds a part the agent cleared or dropped.
- **"Listed in the fiction budget":** read as "listed with the licenses on the card" (`card.identity_parts`). It does not take a license slot, because it bends no R9 3.2 card.
- **Critic:** a named item per identity part: "Does the <part> look like it came from a <donor>?" The open "which animal" answer still comes with every part.

**D-088 Plan fixes from the S3b images (S3c part 1). General rules only.**
- **(a) Fiction clauses come from the donor's traits.** The arthropod-size compensation is "thick supporting legs", plus a respiratory clause only when the donor's breathing trait has an outside sign (`evo_config visible_breathing`: tracheae → spiracles; gills, book lungs, lungs → none). The license `reason` records where the clause came from. An agent's compensation that names breathing openings the donor lacks is rejected (`not_a_donor_trait`).
- **(b) A covering keeps the host's outline.** The covering clause says every covered part keeps the host's own length and shape, and the tail stays the host's own tail. A donor-shaped appendage survives only as the identity part (D-087).
- **(c) Plate layout from the donor.**
  - The covering transfer carries `plate_pattern` and `plate_source`, from the first donor feature that names a layout (`transfer_rules.json plate_patterns`): wing cases → a few large fused plates; carapace → one carapace shield with jointed limb plates; overlapping scales → many scales in rows; bands or rings → bands, the only banded layout.
  - With no match, a class default, marked model-estimated.
  - The compiler words the plates from the pattern, and the S3b "one plate per segment or muscle mass" wording now applies only to overlapping scales.
- **(d) Identity part selection and the critic item:** D-087.
- **(e) RC-R10-17:** the turtle shell is skeleton (Hirasawa, Nagashima and Kuratani 2013, Nature Communications; the RePEc abstract states that the costal and neural plates are continuous with the ribs and vertebrae). VERIFIED against the fetched page.
  - On a turtle host the covering grows only on the skin zones (head, neck, legs, tail). The shell keeps its form, and only its color changes. `set_extent` rejects shell zones.
  - `verify_research`: the same 2 failures as S3b, both the unreachable `ria.ua.pt` source. `rule_cards.json` has 126 cards (18 hard).
- **Found while testing (e):** GBIF files turtles under class Testudines, so the shell check, the class part list and the vertebrate group all missed the tortoise. Testudines, Squamata and Crocodylia are now reptile aliases (`class_parts.json`, `evo_config.json class_groups`).
- **Test hygiene:** `test_real_mode_refuses_before_any_call` passed only when an earlier test had cleared the env, because a `.env` META key made it order-dependent. It now sets `meta_api_key=""`.

**D-089 The agent core: Spark Open picks, code guards (S3c part 2, `agent.py`).**
- **Tools:** the brief's eight tools, plus `choose_candidate` (adopt a candidate; its typed operations are replayed) and `plan_op` (one PlanSession operation). The agent can only pick and apply typed operations. It never sends plan JSON, and code fills card_trace and every derived field.
- **Candidates:** `propose_candidates` is code. It returns one plan per host option, both as equals on a tie and the less structured host marked "advised against" (RC-R6-08, soft) otherwise. It adds a variant with the donor's second diagnostic identity part when one exists. Each candidate has R10 notes (niche, autonomy, survival, identity) and a score that only ranks the notes.
- **Guardrails in code:**
  - a plan must pass `audit_plan` (by content) before `render`;
  - hard cards and an unchosen tie are blocking;
  - `edit` takes only covering or surface failure keys (integration, coverage, placement, pattern, surface groups); structural ones (counts, frame, extra or missing parts, identity, connection, a third animal) return `structural_failure`, with the hint to change the plan and re-render;
  - after any edit, `inspect` compares the critics' head, walking-leg and tail counts with the parent image (S3b drift rule) and adds a `host_drift` structural failure.
- **Caps (`evo_config agent`):** 4 renders, 30 tool calls, 6 edits, `max_tokens` 8000 on every Spark Open agent call. At a cap, or when the agent stops calling tools (3 nudges), code finalizes the best inspected image (fewest structural, then fewest failures) and the card lists the remaining failures.
- **Every call needs a `reason`.** The trace records the tool, arguments, reason, result summary, cards cited and any text the agent wrote. Reference portraits stay off.
- **Fixed pipeline:** `fuse` keeps the fixed pipeline, and `agent_fuse` is the agent path.
- **Smoke-run fixes:** the live smoke run on beetle x bear (kept as `live/s3c/agent/beetle_bear/smoke_r1`) found two gaps, both fixed before the validation runs:
  - the agent repeated an operation that changed nothing and re-rendered the same plan, so `plan_op` now says `changed: false`;
  - it finalized its sixth image although its first was better, so inspect now returns every image's failure counts and the best so far, and the system prompt says to finalize the best image, not the latest.

**D-090 Agent runs keep images on disk and resume from disk (S3c finish).**
- **Images:** the agent keeps only an image's path and size. Inspect, the drift check and finalize load the bytes
  for one call and release them. Its history holds JSON summaries only, and a test checks this.
- **Live runs:**
  - `s3c_live.py` saves the trace, plans, prompts, images and critic answers after every tool step.
  - doc.json is written last and is the only "finalized" marker.
  - A rerun skips finalized runs and redoes a partial one, keeping the partial folder for the record.
  - One creature runs per foreground invocation (`--max 1`), never in a background shell.
- **Why:** the first full run was stopped by the host reclaiming memory from background shells. The measured
  in-process saving is small (about 0.5 MB per image). The protection comes from the foreground runs and the
  resume.

**D-091 The two-failure rule (S3c finish).**
- **The rule:** after two inspects in a row with covering failures, the agent stops editing the covering. It
  changes the plan with typed operations instead, then audits and renders again:
  - `set_extent` on the covering, with fewer zones and a reason; or
  - `set_transfer_class non_homologous` or `drop_part`, so the donor shows by material and color only.
- **In the prompt and in code:**
  - the second such inspect locks covering edits on that plan's content;
  - `edit` refuses with `two_failure_rule` until the plan changes;
  - an operation that changes nothing keeps the lock;
  - a clean inspect or a plan change resets the streak.
- **Live result:** the rule fired in 4 of 8 runs. It changed what the agent did next, but it did not reduce the
  remaining failures on tortoise × goat or beetle × bear.
- **Open, for the owner:** a covering has no "material and color only" operation (`covering_is_material`).
  `S3c_AGENT.md` proposes one.

**D-092 S5 D1: `set_covering_material_only` (owner decision).**
- **What it does:** a typed plan operation, `set_covering_material_only(reason)`. The covering transfer gets
  `form: material_only` and a recorded reason. The host keeps its own covering (fur, skin or feathers), and over the
  covering's zones that covering takes the donor's colors, gloss, surface texture and pattern. Discrete identity
  parts are kept.
- **Compiler:** `covering_clause` and `host_clause` word it without plate, scale or shell nouns. A connected part
  (a horn) grows from its own anchor, no longer "out of the covering".
- **Critic:** a material-only covering is checked with `material_look` (yes), `host_cover_kept` (yes) and
  `donor_pieces` (no). The grown-covering items (grows_out, on_top, continuous, follows_body, sizes, joints,
  connections) are not asked.
- **Agent:** the two-failure rule's second route is now this operation. The rule text and the edit-lock hint name
  it.
- **Why:** in S3c the rule's "material and color only" route had no operation for a covering. The agent's 4 tries
  with `set_transfer_class` on the covering were refused (`covering_is_material`).

**D-093 S5 D2: finalizing against the code's ranking needs a reason (owner decision).**
- **The rule:** code ranks inspected images by fewest structural failures, then fewest failures, then the latest.
  `finalize` on an image other than the code's best is refused (`needs_why_not_best`) unless it carries
  `why_not_best`.
- **The card:** `final_choice` holds `shown_first: agent`, `agree`, `agent_pick` and `code_pick`. Each pick has its
  image id, stored image key, rank, structural and total failures, and reason (the agent's reason; the code's
  ranking rule). When the two picks differ, the code's image is stored too.
- **Why:** in S3c, beetle × bear r2's agent finalized the image the code ranked lower, with no reason recorded.

**D-094 S5 D3: one schema per plan operation; the 15 refused S3c calls (owner decision).**
- **Tools:** S3c's single `plan_op(op, args)` tool is replaced by one tool per typed operation, 12 in all. Each has
  its own argument schema:
  - the operation's own reason is `plan_reason` (at least 12 characters), separate from the call's `reason`;
  - `set_extent` takes only `extent` and `plan_reason`;
  - `set_transfer_class` takes only homologous or non_homologous.
- **Schema checks:** the loop checks every call against its schema before running it (required, unknown keys,
  enums, minLength, item enums) and refuses a bad call with error `schema`. The plan-operation schemas are built
  each turn with the current plan's own parts and features as enums. `plan_op` remains as an internal alias for
  tests, and it is not offered to the agent.
- **The 15 refused calls**, replayed in `test_s5.py` from `tests/fixtures/s3c_refused_calls.json`:

| # | run, step | call | refused | cause | fix | refused now by |
|---|---|---|---|---|---|---|
| 1 | tortoise_goat r1, 10 | set_transfer_class covering → non_homologous | covering_is_material | the rule pointed at set_transfer_class for "material only"; a covering has no class to change | `feature` enum lists the plan's parts only; the description sends a covering to set_covering_material_only | schema |
| 2 | tortoise_goat r2, 10 | same | covering_is_material | same | same | schema |
| 3 | tortoise_goat r2, 12 | set_extent without reason | bad_arguments | op args were a free object; the op's reason was invisible | `plan_reason` required (12+ chars) | schema |
| 4 | fox_owl r1, 8 | set_identity_cues on covering (cues as a list) | not_a_part | free-form `feature`; cues type unchecked | `feature` enum = plan parts; `cues` must be a string; "Parts only" | schema |
| 5 | fox_owl r1, 12 | drop_part "spots" (a critic's extra_spots) | no_such_part | the agent treated an unplanned feature as a plan part | `part` enum = plan.parts; description and system prompt: an extra_* or third_animal is not a plan part | schema |
| 6 | crab_wolf r1, 10 | set_extent without reason | bad_arguments | as 3 | as 3 | schema |
| 7 | crab_wolf r1, 15 | set_transfer_class covering → non_homologous | covering_is_material | as 1 | as 1 | schema |
| 8 | crab_wolf r2, 9 | drop_part "segmented tail" (a critic's dropped_segmented_tail) | no_such_part | the part was already dropped by the plan; the critic flagged it | as 5 | schema |
| 9 | crab_wolf r2, 18 | set_transfer_class covering → non_homologous | covering_is_material | as 1 | as 1 | schema |
| 10 | crab_wolf r2, 20 | set_identity_cues on covering | not_a_part | as 4 | as 4 | schema |
| 11 | beetle_bear r1, 10 | set_extent without legs, reason silent on legs | unexplained_gap | RC-R10-16 (an exoskeleton covers the limbs unless a reason says why not) was not in the tool description | set_extent description: "name the legs in plan_reason" | code, now explained up front |
| 12 | beetle_bear r1, 18 | same | unexplained_gap | same | same | code, now explained |
| 13 | beetle_bear r2, 10 | set_identity_cues on covering | not_a_part | as 4 | as 4 | schema |
| 14 | beetle_bear r2, 11 | set_extent without reason | bad_arguments | as 3 | as 3 | schema |
| 15 | beetle_bear r2, 12 | set_extent without legs, reason silent on legs | unexplained_gap | as 11 | as 11 | code, now explained |

12 of the 15 are now stopped by the schema before anything runs. The 3 `unexplained_gap` refusals depend on the
donor (an exoskeleton), so they stay a code check, and the description now says what that check requires. The test
also confirms that each one passes once its plan_reason names the legs.

**D-095 S5: the fixed benchmark, and the engine is frozen for the demo.**
- **Benchmark:** `data/evo_benchmark.json` holds 11 cases and never changes; a test checks its canonical hash.
  Scores are computed only in code (`app/evolution/benchmark.py`) from the saved results:
  - full match: no failing or uncertain critic row;
  - failures split into structure, identity and integration (integration includes the coverage, placement,
    pattern and connection groups);
  - per-parent identity: whether the deciding critic's (Meta Spark) "which animals" answer names the parent, as a
    whole word, by full name or last word;
  - renders, edits, tool calls, calls per provider and wall time.
- **Result:**
  - Agent: 5/11 full matches, 1.82 average failures, both parents named in 7 cases.
  - Fixed pipeline: 6/11, 1.91, and 5.
  - Per creature, the agent costs about 1.6 times the calls and 1.27 times the wall time.
- **Frozen:** after S5 the engine gets no further quality tuning; only the demo work remains.
- **Proposed, pending the owner's ratings in `benchmark/s5_review.html`:**
  - the agent is the demo path, because it chooses the host on a tie and shows its trace;
  - showcase: b09, b01, b03, b08, b11 and b05;
  - the material-only critic items get gold labels before their failures are trusted.
