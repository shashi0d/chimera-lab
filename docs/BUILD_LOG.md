# Build log

Short entries per phase: what was built, what was tested, what was deferred. Newest at the bottom.

## 2026-10-30: P0 Foundation

- **Built:** repo layout (Section 3) and `scripts/dev.sh` (uvicorn in mock mode plus Vite); backend `create_app()`, `config.py` covering every Section 13 env var, `/health`; `modal_app.py` (imports cleanly, not deployed).
  - **Adapters:** Protocols, mocks with all 10 faults and scaled delays, local filesystem storage and SQLite db, Supabase adapters plus `schema.sql` (untested here).
  - **Types:** Pydantic models as the single source, with `scripts/gen_types.sh` generating `frontend/src/types/api.ts`.
  - **Design:** `theme.css` with the full token set and the 8-section structure; `scripts/check-css.sh`; `docs/DESIGN.md` written and self-reviewed before any styling; fonts self-hosted.
- **Tested:** pytest, vitest and Playwright runners wired; CSS check passes; `npm run shots` produces the empty canvas and everything else.
- **Environment notes:**
  - GitHub repo creation is blocked from this session (D-001).
  - Wikimedia is blocked, so fixture images are generated (D-008).
  - Playwright is pinned to match the preinstalled browser (D-018).

## 2026-10-30: P3 Backend pipeline (built before P1/P2 UI; order logged)

- **Built:**
  - data loader with tolerant field aliases, plus a sample fixture (10 animals, 6 tier-2, 3 hybrids, 10 rules)
  - run model, `RunManager` with heartbeat, lease-based interruption and orphan interruption at startup
  - all 8 steps, with the prompt from the editable `compile_template.txt`
  - spend guard (per-run and daily) and retry/timeout policy
  - `POST /runs` with idempotency and per-session rate limit; `GET /runs/:id` with ETag/304; cancel
  - asset normalisation: content sniffing, HEIC conversion, EXIF orientation, metadata strip, 2048px cap, minimum size, server-side size limit
- **Built, unverified:** real Meta adapters with isolated builders and parsers. **Not verified against the live API.**
- **Tested:** 75 backend tests, including a full fusion in mock mode and every fault mapped to its error code and run status.
- **Why backend first:** the UI's step list, error map and types all depend on the run and error contracts, so fixing those first meant the UI was built against real behaviour.

## 2026-10-30: P1 Canvas, P2 Input, P4 Fusion UX

- **Built:**
  - registry and three node types
  - React Flow canvas: controlled nodes, dot/line grid, fit view, minimap, delete, undo/redo (100 steps)
  - shared specimen card, edge rules with refusal shake and toast
  - graph schema, migration (v0 → v1), unknown-node placeholder, autosave to IndexedDB plus backend save
  - drop, paste and picker; client validation, downscale and orientation; uploads with progress, cancel, retry and offline queue
  - Fusion node: slots usable as selects (keyboard connect), step list, timers, long-wait notes, rate-limit countdown
  - Result node: versions, badges, develop reveal, image-failure fallback; "How this was made" panel
- **First real run** (Playwright smoke): drop lion + tiger, auto-wired, fuse, 8 steps, plate with "Real hybrid exists: Liger".
- **Checkpoint screenshots** reviewed. The flow worked end to end on the first try; one CSS syntax error from the vendored block was caught by the screenshot.

## 2026-10-30: P5 Hardening and P6 tests

- **Tests:** 127 Vitest tests (unit and component) and 39 Playwright tests (happy path, every fault, offline, unreachable, reload mid-run, corrupt/legacy/newer/orphan graphs, node and app crash, client validation, EXIF/downscale, axe in both themes, keyboard-only walkthrough, hit targets, layout at three widths).
- **Real bugs the e2e suite found and fixed:**
  - Autosave never fired during continuous upload progress and was cleared on crash, losing the canvas (D-019).
  - Images added to a non-empty canvas landed on an existing node (D-020).
  - Duplicate progressbar roles; prohibited aria-label on ports; toast list semantics (D-021).
  - Faint-text contrast below AA (D-022).
- **Bundle check:** the production bundle has no secrets and no test hooks (`scripts/check-bundle.sh`).

## 2026-10-30: PV round pv-1

- Captured 56 states at 1440 in both themes, plus core states at 1280 and 1024 (`docs/visual-qa/pv-1`). Reviewed every image in contact sheets; defects are in `docs/visual-qa/DEFECTS.md`.

## 2026-10-30: PV rounds pv-2, pv-3 (PV complete)

- **pv-2:** full matrix after fixing PV1-01 to PV1-11. New findings: PV2-01 (reveal check underestimated height), PV2-02 (images not wired to an empty Fusion node, D-024).
- **pv-3:** affected states plus a 10-state regression sample. No blockers or majors open; lowest rubric score is 4 on every criterion.
- **Baselines:** 4 Playwright baselines saved (empty canvas, result + panel, both themes).
- **Tests:** full e2e 37/37, vitest 135/135, pytest 75/75.

## 2026-10-30: F1 Anatomy controls

- **Built:** part-donor pins on the Fusion node (config v2 with migration). Pins are honoured by planning, and the planning call is skipped when all five are pinned. `donorSource` attributes each part. The mock planner and generator respond to pins.
- **Tested:** +7 backend, +5 component, +1 e2e.
- **Visual:** round `f1` (36 shots), no blockers or majors; baselines re-approved (D-028).

## 2026-10-30: F2 Field-guide card

- **Built:**
  - Field card node: Result output port, "Make field card", backend executor with 3 steps, server-written provenance, verbatim ranges
  - PNG export
  - registry-level `onRunUpdate` (D-030)
- **Tested:** +7 backend, +6 component, +1 e2e (real PNG check).
- **Visual:** round `f2` (36 shots, including the exported PNG), no blockers or majors.
- **Totals:** pytest 89, vitest 146, Playwright 39; CSS and bundle checks pass.

## 2026-10-30: D1 Real data schema (passed)

- **Found:** with the real `chimera_data.json`, the old code resolved 0 hybrids and ran 0 rules, silently: it read invented field names (`parent_a`, `check`).
- **Built:**
  - Hybrid lookup on `parent1`/`parent2` with role suffixes, tier 1 → tier 2 → genus resolution and cross direction kept (D-034).
  - Explicit rule map with 44 rules in two phases, plus new checks: fly/swim need a donor, habitat overlap, 1000× mass ratio on range bounds, unrecorded active time (D-035).
  - All measurement rows per animal.
  - Mythology resemblance (D-037).
  - Real-schema fixture built from the real file (`scripts/make_real_schema_fixture.py`).
  - Startup data check, with counts in `/health` (status `degraded` on a silent zero).
- **Tested:** pytest 89 → 123 (sample, real-schema fixture and the real file), vitest 146. Frontend changes were type fixtures only.
- **Real-file numbers:** 29/31 hybrids resolve both parents; 44/130 rules mapped.

## 2026-10-30: L1 Live Meta integration (passed)

- **Built:**
  - OpenAI-SDK Meta adapters (chat completions for Spark; Responses API for Muse Image), magic-byte formats, response id stored per version
  - retry classification with jitter
  - per-step token accounting and token caps
  - hard live budget and call log
  - record and replay (mocks now run the real parsers on recorded shapes)
  - model-named creatures (planner always runs)
  - measured timeouts; live test marker
- **Live:**
  - 6 fixture photos generated; 6/6 identified and matched by scientific name
  - 5/5 fusions: tigon with cross direction, mule, griffin, rule warnings, pins honoured
  - the pinned fusion failed once on a plan timeout; root cause fixed afterwards (D-042)
- **Spend:** 11/15 images, 27/60 Spark calls, 367,116 tokens logged. Cost unknown.
- **Tests (mock):** pytest 132 (+6 live skipped by default), vitest 146, Playwright 39; bundle check passes.
- **Reports:** `docs/LIVE_REPORT.md` (per-fusion results, images in `docs/live/fusions/`, latency, tokens, judgment, ranked problems), `docs/LIVE_LOG.md` (every call).

## 2026-10-31: U1 UI redesign with the ZD design system

**Plan:** read ZD.md and zd-tokens.css; write `docs/DESIGN_U1.md` (token usage, components, wireframes); rebuild the frontend's look without touching the backend, the API contracts, the registry pattern or the test hooks.

**Built:**
- `theme.css` rewritten: self-hosted Space Grotesk, Hanken Grotesk and JetBrains Mono; ZD verbatim; a Chimera token block with four `-aa` deviations (D-045); then layout, components, nodes and drawer.
- `src/ui/`: Card, BrandMark, SegmentedTabs, LiveIndicator, Timeline, StatCard, Pill, Section, ContextToolbar.
- Nodes: image-first inputs titled by species (D-049); a Fusion node with portraits, a body diagram (D-050) and no thumbnail (D-054); a 500px Result hero card; a glass contextual toolbar (D-047).
- Drawer: summary, stat cards, collapsible sections; mythology always "Unverified" (D-051).
- Screenshots and baselines seeded with real L1 images (D-052).

**Found by the tests while building:**
- The new contrast test, which resolves ZD's `var()` chains and composites tints, showed the planned primary hover (`--indigo-700`) is 2.2:1 under white in dark mode. Fixed (D-046).
- The old Field-paper contrast test parsed only hex tokens; it could not see ZD's `rgba()` tints. Rewritten.

**Mistake:** running `prettier` without a project config reformatted ~70 untouched files. Reverted to the committed versions; only the files changed for U1 keep the repo's 160-column style.

## 2026-10-31: E1-offline evolution engine (mocks only)

**Plan:** build the engine in `docs/evolution/ALGORITHM.md` as a new module under `/evo`, against mocks, with no live API call. Full report: `docs/evolution/E1_OFFLINE.md`.

**Step 0, docs and verification:**
- The docs were already in `docs/evolution/`, and there was no verifier. I wrote `scripts/verify_research.py` (stdlib only) to the user's spec.
- Run 1 failed on 4 links. The user authorized 3 source fixes (RC-R8-01, RC-R1-07, R4 [S7]) and two warning rules: certificate-chain errors, and timeouts on links that resolved in an earlier recorded run.
- Run 4 passed with 14 bot-blocked links (403). See `docs/evolution/VERIFY_REPORT.md`.

**Built:**
- `scripts/build_rule_cards.py` produces `data/rule_cards.json` (94 cards, 11 hard).
- `backend/app/evolution/`, in pipeline order:
  - genome model validated by code
  - routing, host and silhouette
  - trait operators with GATE
  - habitat step
  - physical checks in fixed order
  - prompt compiler
  - hard filters and soft penalties
  - judge
  - evolve loop with a quality-diversity archive
  - output card
- 5 endpoints under `/evo`.
- Known-pair overrides and engine tables are data (`data/evo_known_pairs.json`, `data/evo_config.json`).
- Spark and SAM roles have protocols plus deterministic mocks. Real mode refuses before any call.
- `main.py` only mounts the router.

**Tested:**
- pytest: 217 passed, 6 skipped (132 existing unchanged, plus 85 new).
- Every hard card in section 8 has tests.
- The 4 worked examples pass over seeds 0 to 9.
- A mutation check confirms the tests catch broken hard checks.

**Calls for one live run of the 4 examples:** 16 Spark, 4 images, 4 SAM (names as input). Default evolve costs 39 Spark, 12 images and 12 SAM per seed.

**Deferred:**
- live Spark and SAM adapters, and a SAM budget counter
- person-checked quality tests
- the cost test that sets batch and rounds
- opening the 403 links in a browser

## 2026-10-31: E2-live, first live run of the evolution engine (4 worked examples)

**Plan:** two review fixes, live adapters, one SAM probe, then the 4 worked examples live (fuse only, no evolve). The `evo` → `main` merge was skipped on the user's instruction. Full report: `docs/evolution/E2_LIVE.md`.

**Built:**
- Review fixes: `LABEL_CLOSE` now says "speculative". The guanaco is now *Lama guanicoe*, and the cama still resolves for both dams (D-055).
- `backend/app/evolution/live.py`: live Muse Spark (first plan, polish, critic, thumbnail critic), SAM 3.1 and retrying Muse Image. All reuse `_MetaClient`, the budget guard, usage records and `call_with_retry`.
- Budget kind `sam` (`CHIMERA_LIVE_MAX_SAM`).
- SAM mask parser built on Meta's `meta-sam-parser==0.1.0`, because masks come back as arithmetic-coded base85 text tokens. The install was approved by the user.

**Live:**
- 1 SAM probe call, recorded in `backend/tests/fixtures/recorded/sam-01.json`.
- The 4 examples, all ok on the first try.
- Calls made: 16 Spark, 4 image, 4 SAM, exactly as predicted, with no retries.
- Budget counter: image 11→15, spark 27→43, sam 0→5.
- Quality: mule 0.45, liger 0.955, lion x eagle 0.768, eagle x octopus 0.70.

**Problems found, not fixed:**
- SAM returned empty masks when prompted with the host name ("horse", "golden eagle"), giving silhouette 0 on 2 of 4. Prompting with "animal" worked.
- The quadruped aspect band is too narrow for tall-eared animals.
- The mule's "faint" stripes render as zebra stripes.
- A habitat cue added leopard spots to the lion x eagle.

**Tested:** pytest 235 passed, 6 skipped. `openai` was missing from `.venv` although it was in `requirements.txt`, so I installed it.

## 2026-10-31: E2b third-animal leakage, examples 1 and 3 re-run live

**Plan:** stop third-animal leakage (E2's mule read as a zebra, and the lion x eagle had leopard spots), then re-run those two live. No merge. Report appended to `docs/evolution/E2_LIVE.md`.

**Built:**
- Pattern phrases are compiled by code only, as "<donor>-type <type>" (from a new `coat_patterns` table) or "plain coat, no stripes or spots".
- Mule and hinny overrides have a plain coat.
- The habitat step only scales an existing pattern.
- A polish that adds an animal or contradicts the limbs or mane is rejected.
- A critic naming a third animal triggers one re-render with the compiled prompt, then the creature is kept with a warning.
- SAM is prompted with "animal". A mask in pieces counts as one creature when the critic says one.
- Also: `finish()` re-runs GATE, and the RC-R2-03 check ignores `None` on both sides.

**Live:**
- 8 Spark, 2 image and 2 SAM calls, as predicted. No retries, no re-renders.
- Mule 0.45 → 0.67: no stripes, but it still reads as a donkey.
- Lion x eagle 0.768 → 0.94: no spots, no mane, critic names only lion and eagle.
- Budget counter: image 15→17, spark 43→51, sam 5→7.

**Tested:** pytest 503 passed, 6 skipped (+268 E2b tests).

## 2026-10-31: E2c real-hybrid prompt, example 1 re-run live

**Plan:** make the known-pair (real hybrid) prompt carry the host frame, then re-run only example 1 (donkey x horse) live. No merge. Report appended to `docs/evolution/E2_LIVE.md`.

**Built:**
- `prompt.compile_real_hybrid` opens with the name and cross, gives the frame in host terms first, and names the donor once in a grouped clause. Wording comes from a `prompt` block per known pair. The liger opens with "A liger (lion sire x tiger dam)".
- Real hybrids get no habitat step (`habitat.clear_habitat`, D-056).
- On the real-hybrid route the critic counts the hybrid's own name or an alias as both parents.
- `CHIMERA_LIVE_MAX_SAM` defaults to 15.

**Live:**
- 4 Spark, 1 image and 1 SAM call, as predicted. No retries, no re-render.
- Mule 0.67 → 0.685: taller, deeper-chested, longer-necked, plain coat, no habitat scrub. The image-only critic still names "donkey", so the critic and thumbnail scores stay at 0.5.
- Budget counter: image 17→18, spark 51→55, sam 7→8 (SAM cap now 15).

**Tested:** pytest 543 passed, 6 skipped (+40 E2c tests).

## 2026-10-31: E2d feature-checklist critic, re-score only

**Plan:** replace the open critic on the real-hybrid route with a checklist from each pair's R2 card, then re-score the E2c mule and the E2 liger live. No new images. No merge. Report appended to `docs/evolution/E2_LIVE.md`.

**Built:**
- A `checklist` (4 to 6 visible features) on each of the 7 known pairs.
- `LiveEvoSpark.checklist`, which asks for yes, no or unclear per item plus a forced choice (sire, dam, hybrid name, other) in one call.
- `judge.checklist_score` (yes 1, unclear 0.5, no 0). The forced choice is logged in `judge.forced_choice` and not scored.
- The thumbnail critic uses the same checklist. Other routes keep the open critic.
- `scripts/e2d_rescore.py` re-scores existing images.

**Live:**
- 4 Spark calls, 0 image, 0 SAM, as predicted.
- Mule: critic 0.5→0.8 and thumbnail 0.5→0.8; forced choice mule (full) and donkey (thumbnail); quality 0.685→0.835.
- Liger: critic 1.0, thumbnail 0.9; forced choice liger on both; quality 0.955→0.945.
- Budget counter: spark 55→59.

**Tested:** pytest 562 passed, 6 skipped (+19 E2d tests).

## 2026-10-31: E4 open world and R9 (in progress)

**Step 0:** `verify_research.py` gate passed with R9 (109 cards, 0 failures, 16 403s). Rule cards regenerated (109, 17 hard). ALGORITHM.md v2 (4.5b function audit, 4.5c fiction budget, design modes, RC-R9-01 labels, section 8 tests). New `docs/evolution/ENGINE_CONTRACT.md`.

**Step 1:** `evolution/resolve.py` (database, learned cache, Spark identify, GBIF exact match, Spark trait fill, refusals, needs_choice, offline fallback), `evolution/gbif.py` (client with timeout and retry, fixture replay), `/evo/resolve`. 12 recorded GBIF responses in `tests/fixtures/recorded/gbif/`. Animal gains order, genus, diet, movement, features, mouthparts, breathing, kind, provenance and claims. 23 resolver tests.

**Step 2:** routing by taxonomy distance (`Route.distance`), precedent only from data, unknown taxonomy means a speculative chimera, "mythic composite" label (RC-R9-01). A source scan found and removed two hard-coded animal or pair names in `checks.py`.

**Step 3:** `evolution/audit.py`: six functions, code-decided with cards, at most one Spark call for uncovered functions before the render, never a silent pass. Hard checks RC-R9-01, -02, -03, -06, -09.

**Step 4:** `evolution/fiction.py`: budget realistic 0, speculative 1, mythic 3; licenses only on R9 3.2 bendable cards, each with a compensation in the plan and prompt; repair down to the budget, then label; honesty and floor rules never licensable; compare mode; RC-R9-10.

**Step 5:** checklist generated from the plan for every route (hand-written pair checklists first), creature count and third-animal question in the same call, open critic logged only. The card gains `kind`, `can_it_live`, `licenses` and `provenance`; every prompt gets the prosaic-detail line.

**Step 6:** full suite 684 passed, 6 skipped (E4 adds 122 tests: resolver 23, routing 12, audit 30, fiction 24, output 22, hard cards 11). Ruff clean.

**Step 7 (live):**
- Calls: 24 Spark, 3 image, 3 SAM and 3 GBIF, exactly as predicted (the task estimated about 27 Spark). No retries, no re-renders.
- Budget counter: image 18→21, spark 59→83, sam 8→11; caps 27/100/16 not reached.
- Resolver: axolotl and jaguar from the database; golden retriever (breed) and woolly mammoth (extinct) via GBIF EXACT; pangolin (ambiguous) resolved to the Chinese pangolin via the tier2 table, with alternatives.
- Renders:
  - axolotl x pangolin, realistic: 1.0, but it shows the gills the audit dropped (a model-note leak).
  - lion x eagle, mythic: 0.962, six-limb license shown.
  - beetle x bear, speculative: 0.845, size license with visible breathing openings; the beetle wings were drawn on top of four legs, and the checklist answered no.
- Fixed after the run: a dropped part is flagged on the plan, its note clauses are stripped and kept out of the prompt, and the checklist asks "no <part>". Regression test added; 685 passed, 6 skipped.
- `e4_live.py` failed to write its outputs in run 1 (missing folder) after every call had succeeded. The outputs were rebuilt from the engine cache with `--recover` (0 calls), and the SAM masks were decoded offline from the recordings.

**Step 8:** report `docs/evolution/E4_OPEN_WORLD.md`.

**Follow-up (live):** b) axolotl x pangolin, realistic, re-rendered after the dropped-part fix (`e4_live.py --rerender-b`, fresh cache). Calls were 6 Spark, 1 image and 1 SAM, as predicted. The budget counter moved image 21→22, spark 83→89, sam 11→12. There are no gills in the prompt or the image. The checklist's "no external gills" item was answered yes, and quality was 0.975 (the thumbnail missed the patches). The axolotl reads only through its skin patches; the open critic saw a pangolin. Details are in `E4_OPEN_WORLD.md`.

## S1: capability probe for the new architecture (evo)

`docs/evolution/ROADMAP.md` is not in the repo (neither evo nor main), so S1 follows the task text alone.

**Part 1:** Baseten adapter `backend/app/adapters/baseten/` (`BasetenEvoSpark`). It is the existing EvoSpark interface over `https://inference.baseten.co/v1`, model `meta-models/muse-spark-open-1026`, and reuses the Meta request builders, parsers, `_MetaClient` (live-budget guard, usage records, key-free recordings), error mapping and `call_with_retry`. New budget kind `spark_baseten`, capped by `CHIMERA_LIVE_MAX_SPARK_BASETEN` (default 300, a runaway guard only). Recordings now refuse the Baseten key as well as the Meta key. The key is read from `BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26`; `.env.example` added with placeholders. No route uses the adapter yet. Tests: 11 new; full suite 696 passed, 6 skipped.

**Part 2 (live, Spark Open on Baseten):** `scripts/s1_probe.py spark`, outputs in `docs/evolution/live/s1/spark/`.
- First run: plan-sized calls hit the 60 s per-attempt timeout (9 attempts, `TIMEOUT_CANCELLED`). Stopped; the Baseten adapter now has its own 300 s timeout (`baseten_timeout_seconds`). The aborted run's recordings were removed; its attempts stay in `LIVE_LOG.md` and the counter.
- Strict JSON: identify and audit are clean, schema-valid JSON (2.5 s, 8.4 s). The enum-heavy traits call ran to `finish_reason: length` after 193 s. In the aborted run the same call returned valid JSON with nonsense duplicates (axolotl body plan "quadruped, biped, winged, finned, …").
- Image input: works. The lion x eagle render was identified as a griffin (kind mythic), and the critic answered eagle and lion, 1 creature.
- Tool calling: fully correct in 4 turns. It made both resolve calls in parallel, passed the returned ids to the audit, passed the audit id to the render, and the final reply contains the image id.
- Refusals: 0 of 5 planning prompts. But 4 of 5 ran away to 43,000 to 52,600 characters, cut off at the 32,768-token output limit (about 60 s each), so the JSON was unreadable. Only lion x goldfish (mythic) produced a plan, and it was accepted with no locked field changed.
- Redacted fixtures (4) are in `backend/tests/fixtures/recorded/baseten/`, with 5 replay tests. The suite is 701 passed, 6 skipped. Baseten spark counter: 19 → 33.

**Part 3 (parity, 10 recorded Meta Spark requests replayed on Baseten):** `scripts/s1_probe.py parity`, outputs in `docs/evolution/live/s1/parity/`. The three plan requests were rebuilt from code and match the recorded prompt lengths exactly (9004, 8815, 9096 characters). The other seven are the recorded bodies with only `model` changed (images re-attached for the checklists).
- Plans: 0 of 3 usable. Every answer ran to the output limit (about 49,000 to 50,500 characters, 62 to 68 s), looping inside `card_trace`. Meta's results for the same requests: b accepted, c and d fell back to the code skeleton.
- Polish: 2 of 2 accepted, as with Meta, within 13 characters of Meta's length.
- Resolver: 2 of 2 with the same kind and scientific name (woolly mammoth extinct; pangolin ambiguous, *Manis pentadactyla*), with 3 of 4 alternatives the same.
- Checklist: 15 of 15 items agree. Forced choice, animals and creature count are identical, items were echoed in order, and the JSON is schema-valid.
- A first parity attempt made 1 plan call (b) and then the script crashed on the unreadable answer (fixed); it is noted in `live/s1/parity_try1/NOTE.txt`. Baseten spark counter: 33 → 44.

**Part 4 (Muse Image on Meta, live):** `scripts/s1_probe.py image`, outputs in `docs/evolution/live/s1/image/`. There were 4 image calls, not the 3 the task named, because the reference render needs the 2 portraits first.
- Portraits (text only, 21 s and 24 s): both clean, 4 of 4 checklist items yes, one SAM component (the axolotl mask has 2).
- Reference render (the E4 axolotl x pangolin compiled prompt plus both portraits, 25 s): quality 0.975, the same as the text-only re-render. The references carried the axolotl's speckled skin and the portraits' engraving style into the patches but changed no anatomy (no gills, still pangolin-shaped). The open critic still answered "pangolin" only.
- Edit turn (`previous_response_id` of the E4 beetle x bear render, made a day earlier, 20 s): it edited the same creature. Only 3.7% of pixels changed by more than 32 levels, and the pose, wings, tail and breathing openings are identical. The beetle bodies are gone, but they were how the model drew the planned "exoskeleton patches on the forequarters", so that item now fails and quality dropped from 0.845 to 0.778. The "wings in place of the front legs" item still fails, as before.
- Budget counter: image 22 → 26, spark 89 → 97, sam 12 → 16.

**Part 5 (SAM 3.1 part prompts, live):** `scripts/s1_probe.py sam`, outputs in `docs/evolution/live/s1/sam/` (mask and overlay per prompt).
- Lion x eagle: "wings" gave 2 objects, exactly both wings; "eagle head" gave 1 object, exactly the head; "lion legs" gave 4 objects, exactly the four legs.
- Axolotl re-render: "external gills" gave 0 objects, a correct miss.
- Beetle x bear: "beetle" gave 0 objects, a false miss. Five glossy beetle bodies sit on the shoulders; SAM does not treat a beetle body grown into fur as a "beetle".
- Latency 1.2 to 3.4 s. SAM counter 16 → 21.

**Part 6:** report `docs/evolution/S1_CAPABILITIES.md`: one table per probe, a verdict per capability and a recommended route per call type (no routing switch; that is step 3). In short: Spark Open is good for tools, image input, short strict JSON, the checklist (15/15 parity), identify and polish, but not for plans (runaway `card_trace` array) or traits. The Muse Image edit turn edits the same creature; references change style, not anatomy. SAM part prompts confirm presence precisely but can miss embedded parts.

## S2: fix pack and agent preparation (evo)

Read `docs/evolution/ROADMAP.md` (now committed) sections 4, 5 and 5b. Caps for live runs: images 80, Spark 250, SAM 80, Spark Open 600 (runaway guards only).

**Part 1 (E4c fixes):** none of these were committed before. Details are in D-063 to D-065.
- **(a) Wings:** RC-R3-01/02 now apply to vertebrate wing donors only. Insect wings sit on a dorsal mount (bendable `insect_wings`, card RC-R3-09) and are dropped over budget.
- **(b) Class parts:** `data/class_parts.json` covers 11 classes, marked "model-estimated, reviewed". `parts.py` gates every donor part and saved trait. The learned beetle's body plan was corrected from `multi_legged, winged` to `multi_legged`, logged in its `corrections`. Its "jointed tail segments" became its head horn.
- **(c) Grouped clause:** each donor is named once in one grouped clause, with parts as materials and shapes.
- **(d) Silhouette:** recomputed last and checked against the limb plan.
- **Regression:** the E4 live beetle plan, replayed with the beetle as E4 saved it, now gives four bear legs, no wings ("dropped part: wings"), a chitin horn on the brow, chitin plates, and one license (arthropod size).
- **Tests:** 39 new (`test_s2_e4c.py`); one E2b test reworded ("lion body" instead of "lion coat"). Full suite 740 passed, 6 skipped.

**Part 2 (prompt hygiene, D-066):**
- **Prompt sources:** the prompt is compiled only from structured fields plus the code-owned `render_details`; trait notes never reach it on any route.
- **Forced choice:** removed from the schema, instructions, request, parser, protocol, mock and verdict. The `e2d_rescore`, `e4_live` and `s1_probe` scripts were updated to match.
- **Tests:** 13 new (`test_s2_prompt_hygiene.py`: poisoned notes on 6 routes, a model plan full of notes, code repairs present, compensation shown once, model-judged repair kept off the prompt, `render_details` code-owned and rebuilt). E2d tests rewritten for no choice. Full suite 752 passed, 6 skipped.

**Part 3 (typed operations, D-067):** `app/evolution/ops.py` (`PlanSession`, `engine.plan_session`) provides six operations: `set_host`, `set_region`, `set_habitat`, `set_mode`, `add_license` and `drop_part`.
- **Validation:** each is validated on its own and returns structured errors (code, field, valid values, hint). A failure, including a hard-card failure, leaves the session unchanged.
- **Derived fields:** code rebuilds every derived field on each call.
- **Legacy schema:** `labels`, `processes` and `card_trace` left the model's plan schema and became code-owned.
- **Tests:** 27 new (`test_s2_ops.py`); full suite 779 passed, 6 skipped.

**Part 4 (web-cited traits, D-068):**
- **Probe:** 1 Meta call confirmed that the Responses API returns strict JSON together with `web_search_call` items (search queries and opened pages) and `url_citation` annotations.
- **Code:** `live.build_cite_request`, `parse_cite_response`, `LiveEvoSpark.cite_traits`, a mock version, `Resolver._cite` (the new-animal trait step, with a logged fallback) and `Resolver.cite` (re-resolve with a per-field report).
- **Live:** re-resolved 4 animals with 4 Meta Spark calls (budget spark 98 → 102); outputs in `docs/evolution/live/s2/cited/`.

| Animal | Web-cited | Matched | Corrected | Uncited | Stored |
|---|---|---|---|---|---|
| axolotl | 13/13 | 8 | 5 | 0 | comparison only (database) |
| Chinese pangolin | 13/13 | 10 | 3 | 0 | learned entry updated |
| rhinoceros beetle | 12/13 | 9 | 3 | 1 (body mass) | learned entry updated |
| woolly mammoth | 12/13 | 10 | 2 | 1 (body length) | learned entry updated |

- **Tests:** 12 new (`test_s2_cited.py`, including a replay of the live probe response); suite 791 passed, 6 skipped.

**Part 5 (routing, D-069):**
- **Router:** `app/evolution/routing.py` (`RoutedSpark`), driven by the `routing` table in `evo_config.json`.
- **Spark Open with caps:** identify, checklist, thumbnail, polish and the open critic.
- **Meta:** plans, traits, cited traits, the audit and vary.
- **Fallback and provenance:** a logged fallback to Meta; the provider is on every call record and on the card.
- **Tests:** 18 new (`test_s2_routing.py`); 2 S1 tests updated. Suite 809 passed, 6 skipped.

**Part 6 (inspect and edit, D-070):** `app/evolution/inspect.py`:
- **Items:** the plan as structured checklist items.
- **Judging:** SAM presence for planned parts (never proof of absence); the critic for absences, the frame, compensations, count, third animals and separate bodies.
- **Edit loop:** `realize()` makes one plan-worded edit turn on a structural miss, inspects again, keeps the image with fewer misses, and warns if a miss remains. It replaces the E2b re-render. The checklist cap is now 8.
- **Mock:** the image generator chains edits by `previous_response_id`.
- **Tests:** 22 new (`test_s2_inspect.py`, with the S1 edit recording and the E4 beetle plan as regressions); E2b, E4 and worked-example tests updated for the extra SAM presence calls and the edit turn. Suite 831 passed, 6 skipped.
