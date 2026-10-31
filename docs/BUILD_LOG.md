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
