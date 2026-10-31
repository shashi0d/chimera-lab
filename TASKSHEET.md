# Chimera Lab: Build Tasksheet (v1: Two-Image Fusion)

Owner: Shashi
Builder: Claude Code cloud (autonomous)
Deadline context: hackathon submission due Nov 4, 2026

This file is the living plan. Claude Code owns it and keeps it describing what is actually being built. Every change from the original defaults is logged in `docs/DECISIONS.md` (D-xxx). Phase history is in `docs/BUILD_LOG.md`.

---

## 0. Instructions for Claude Code

### 0.1 Autonomy charter

Shashi has handed full decision authority over this build. Everything after Section 0 is a well-researched default, not a rule. That covers stack, architecture, contracts, pipeline, state matrix, phase order, UI design, UI standard, verification methods, test tools and feature rounds. Change anything that gives a better product, demo or build, provided you:

1. **log every meaningful decision** in `docs/DECISIONS.md` (what, why, alternative, impact), and
2. **keep this file true**: edit the relevant section in the same session.

### 0.2 The only fixed points

1. **No live services from this environment.** Every external service goes through a swappable adapter. Everything runs and is tested in mock mode. Real adapters are written but unverified until P7.
2. **No secrets in client code or the frontend bundle.** (Enforced by `scripts/check-bundle.sh` and `tests/unit/codeRules.test.ts`.)
3. **A per-run limit on paid model calls must exist.** (`MAX_GENERATIONS_PER_RUN`, `MAX_VISION_CALLS_PER_RUN`, `DAILY_GENERATION_CAP`; every attempt counts. D-003)
4. **Generated creatures are never presented as real animals.** (Every plate caption reads "Generated fusion"; the alt text says "Not a real animal"; real hybrids are labelled separately.)
5. **P7 stays Shashi's.**

### 0.3 Working loop

1. Read this file, `docs/DECISIONS.md` and `docs/BUILD_LOG.md` before writing code. Continue from the first unfinished task.
2. Phase order as built: P0 → **P3 → P1 → P2 → P4** → P5 → P6 → PV → F1 → F2. (Backend contracts came first so the UI was built against real behaviour; see BUILD_LOG.)
3. After each phase, update the checkboxes here and append to `docs/BUILD_LOG.md`.
4. If blocked, mark `[BLOCKED]` with the reason and a workaround, then continue.
5. Verify the UI visually: screenshots you have actually reviewed (PV, `docs/UI_STANDARD.md`).
6. Finish by updating `docs/TEST_REPORT.md` and confirming Section 9.

---

## 1. What v1 does

**Core:** a user drops two animal images onto a node canvas, connects both to a Fusion node, clicks Fuse, and gets one generated chimera image back, with every loading, error, broken and offline state handled.

User flow (as built):

1. User drops, pastes or picks Image A and Image B. Each becomes an Image Input node. **On a canvas without a Fusion node, one is added and both images are wired to it automatically (D-012).** Inputs can also be (re)connected by dragging ports or with the slot selectors (keyboard).
2. User clicks **Fuse**. A Result node appears at once, with a skeleton (D-013).
3. The backend runs the pipeline (Section 5). The Fusion node shows step-by-step progress.
4. The result appears in the Result node (and as a summary with thumbnail in the Fusion node). Re-running adds a version; old versions are kept.

No labels or species input from the user. Identification findings are only in the expandable "How this was made" panel.

### Non-goals for v1

No accounts or auth (an anonymous `X-Session-Id`, D-017); no modifier nodes shipped (the architecture supports them, see `docs/ADDING_A_NODE.md`); no 3D, video or animation; no sharing; desktop first, with nothing broken at 1024px.

---

## 2. Stack and constraints

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18 + TypeScript (strict) + Vite | |
| Canvas | `@xyflow/react` 12 | controlled nodes; base CSS vendored into theme.css (D-010) |
| Client state | Zustand | graph, runs, connectivity, ui, toasts |
| Styling | **One file: `frontend/src/styles/theme.css`** | Section 6 |
| Backend | Python 3.11-compatible (3.13 locally, D-002) + FastAPI | `create_app()` factory |
| Hosting | Modal (`modal_app.py`), uvicorn locally | in-process run tasks + lease (D-016) |
| Database + storage | Supabase (real) / SQLite + files (dev) | behind adapters |
| Models | Meta Muse Spark (vision + planning), Muse Image | behind adapters; ids in config |
| Tests | Vitest + RTL, pytest, Playwright 1.63 (D-018) + axe-core | all against mocks |

Defaults (as built): no secrets in the frontend; every external call goes through an adapter selected by `CHIMERA_MODE=mock|real` and by the presence of Supabase credentials; spend guard defaults 2 generations and 4 vision calls per run, plus a 200/day cap. Tests use `backend/tests/fixtures/chimera_data.sample.json` (10 animals, 6 tier-2, 3 hybrids, 10 rules). Without `data/chimera_data.json` the app falls back to the sample and says so in `/health`.

---

## 3. Repository layout

As specified, plus:

- `frontend/src/test-hooks/`: test-mode-only `window.__chimera`
- `frontend/src/nodes/unsupported/`: the placeholder view
- `frontend/tests/visual/capture.ts`: the screenshot matrix
- `frontend/tests/visual/baselines/`: Playwright baselines
- `scripts/`: `check-bundle.sh`, `make_fixture_images.py`, `contact_sheets.py`, `shrink_shots.py`
- `backend/tests/fixtures/images/`: generated fixture photos and edge-case files (D-008)

---

## 4. Architecture contracts

See `docs/ARCHITECTURE.md` (with diagrams). Changes from the original contracts:

- `NodeDefinition` gained `icon`, `addable` and `defaultData()`. `NodeViewProps` gained `catalog`.
- `VisionAdapter.plan_fusion()` was added for the compile step (D-004).
- `GET /runs/{id}` embeds the creature spec in `result` (D-005). `Run.failedInput` names the offending slot.
- The error envelope adds `errorId` (for `INTERNAL`). The code list adds `NOT_FOUND`. The client adds `NETWORK`, `OFFLINE`, `ABORTED` and `UNKNOWN`.
- Mock faults add `budget`. Mock vision identifies by hue (D-006). Mock generation paints a deterministic composite (D-007).
- The graph schema has a defined v0 → v1 migration (D-015).

---

## 5. v1 fusion pipeline

As specified: `load_inputs → identify → match → hybrid_check → rules_check → compile → generate → store`.

- Retries: 1s, 2s, 4s; max 3 attempts; honour `retryAfterMs`. Retries stop when the spend guard is exhausted (D-003).
- Timeouts: identify 30s, generate 120s.
- Lease: 180s.
- Rules run as Python predicates keyed by each rule's `check` field. Unknown check types are skipped and counted in the step detail.
- The prompt template is `pipeline/steps/compile_template.txt`.

### 5.3 Meta Model API facts

Verified from public docs (Oct 2026):

- Base URL `https://api.meta.ai/v1` with OpenAI-compatible formats.
- Muse Spark takes image input and supports structured output.
- Muse Image takes 1 to 10 reference images, with no seed and no mask.

**To verify in P7:**

- the Muse Image endpoint path (currently `/images/generations`) and its fields (`reference_images`, `aspect_ratio`, `response_format`)
- model ids
- rate limits and error shapes

The builders and parsers are isolated at the top of `adapters/meta/client.py`.

### 5.4 Data schema

The field names were inferred. The loader accepts aliases (`common_name`/`name`, `parent_a`/`sire`, …). `|` lists are split on read. Ranges stay strings and are compared by their bounds, never by midpoints.

---

## 6. Theme and styling rules

As specified, plus:

- light is the default theme and dark is the override (D-009)
- port shapes encode type (D-011)
- React Flow structural CSS is vendored (D-010)

Enforced by `scripts/check-css.sh`. Design is in `docs/DESIGN.md`. All strings are in `frontend/src/copy.ts`.

---

## 7. State matrix

Every row has UI and a test. The mapping is in `docs/TEST_REPORT.md`.

---

## 8. Phases and tasks

### P0 Foundation

- [x] P0-01 Scaffold the repo layout, plus `scripts/dev.sh`.
- [x] P0-02 `create_app()`, `config.py` (all Section 13 vars), `/health`.
- [x] P0-03 `modal_app.py` (importable, lint-clean; not deployed).
- [x] P0-04 Adapter Protocols and mocks with fault injection and realistic delays.
- [x] P0-05 Local adapters (files + SQLite). Supabase adapters written, untested here.
- [x] P0-06 Pydantic as the single source of types; `scripts/gen_types.sh`.
- [x] P0-07 `theme.css` token set and structure; `scripts/check-css.sh`.
- [x] P0-08 `npm test`, `pytest`, `npm run e2e` wired and passing.
- [x] P0-09 `docs/DESIGN.md`, self-reviewed before styling.
- [x] P0-10 `npm run shots` with test-only hooks.

### P1 Canvas and node system

- [x] P1-01 Registry with `image-input`, `fusion`, `result`.
- [x] P1-02 Canvas: pan, zoom, grid, fit view, minimap, keyboard delete, undo/redo (100 steps).
- [x] P1-03 Shared node card (header, status, preview, typed ports, hover toolbar).
- [x] P1-04 Edge rules: type, single connection, no cycles, refusal feedback.
- [x] P1-05 Graph schema, serializer, validator, migration, unknown-node placeholder.
- [x] P1-06 IndexedDB autosave (500ms debounce, 2s max wait, flush on hide, D-019) plus backend save.
- [x] P1-07 Empty-canvas state.

### P2 Input handling

- [x] P2-01 Drop, paste and file picker.
- [x] P2-02 Client validation: type sniffing, size, decode, minimum size, 2048px downscale, EXIF orientation (re-encode strips metadata).
- [x] P2-03 Upload with progress, cancel and retry.
- [x] P2-04 Backend: content sniffing, HEIC, EXIF strip, sha256, dimensions, storage.
- [x] P2-05 Every 7.1 row tested.

### P3 Backend pipeline

- [x] P3-01 Data loader and query helpers.
- [x] P3-02 Run model, store, runner, lease-based `interrupted`.
- [x] P3-03 Steps `load_inputs` through `rules_check`.
- [x] P3-04 `compile` (spec + template prompt; mock returns a fixed structured plan).
- [x] P3-05 `generate` and `store`, with the spend guard.
- [x] P3-06 `POST /runs` (idempotency), `GET` (ETag), cancel.
- [x] P3-07 Retry and timeout policy.
- [x] P3-08 Real Meta adapters plus tests against recorded-shape responses. **Unverified against the live API.**

### P4 Fusion UX

- [x] P4-01 Fusion node: A/B ports, Fuse, validation hints, keyboard slot selectors.
- [x] P4-02 Run client: start, poll with backoff and ETag, cancel, resume after reload.
- [x] P4-03 Step progress, elapsed timer, long-wait messages.
- [x] P4-04 Result node with versions, plus "How this was made".
- [x] P4-05 Stale marking on upstream change.

### P5 Hardening

- [x] P5-01 Error message map and retry UX (including the rate-limit countdown).
- [x] P5-02 Error boundaries per node and at app level.
- [x] P5-03 Connectivity: offline vs unreachable, banners, upload queue, polling pause and resume.
- [x] P5-04 Accessibility: keyboard reachability, focus, live regions, alt text, never color alone.
- [x] P5-05 Security: CORS allowlist, server size limit, bundle secret check, per-session run rate limit.

### P6 Test suite and docs

- [x] P6-01 Playwright e2e (happy path, every fault, offline, reload mid-run, broken graphs).
- [x] P6-02 Not needed. Playwright runs against the preinstalled Chromium.
- [x] P6-03 `docs/ARCHITECTURE.md`.
- [x] P6-04 `docs/ADDING_A_NODE.md` (Style node worked example).
- [x] P6-05 `README.md`.
- [x] P6-06 `docs/TEST_REPORT.md`.

### PV Visual inspection and correction

Standard: `docs/UI_STANDARD.md`. Matrix: all states at 1440 in both themes, core states at 1280 and 1024 (D-023). Defects: `docs/visual-qa/DEFECTS.md`.

- [x] PV-00 `docs/UI_STANDARD.md`.
- [x] PV-01 Matrix captured (pv-1) and `INDEX.md` written.
- [x] PV-02 Rubric review and DEFECTS for pv-1.
- [x] PV-03 Correction rounds until the exit criteria hold (pv-1 → pv-2 → pv-3; 0 blockers/majors open).
- [x] PV-04 axe, keyboard walkthrough and layout assertions passing.
- [x] PV-05 Baselines saved and wired into `npm run e2e` (`tests/e2e/visual.spec.ts`).
- [x] PV-06 `BEFORE_AFTER.md`.

### F1 and F2 Feature rounds

Process as in the original tasksheet (review → 3 to 5 candidates → score → pick → spec → tasks → build → test → close out). Round docs are in `docs/rounds/`.

- [x] F1-00 ROUND-1.md: review, 5 candidates, scores, pick (Anatomy controls), mini-spec.
- [x] F1-01 Backend: `FusionExecutor.configure()` validates `donors`; pins stored on the run.
  - Acceptance: bad value → `GRAPH_INVALID`. Tests: `test_anatomy_controls.py`.
- [x] F1-02 `compile` honours pins, skips the plan call when all are pinned, and records `donorSource`. Mocks respond to pins.
- [x] F1-03 Fusion config v2 plus `migrate()` (v1 → all Auto, sanitise). Tests: `anatomy.test.tsx`.
- [x] F1-04 `AnatomyStrip` UI, advisory one-parent hint, Outdated on change, `updateNodeConfig` store API.
- [x] F1-05 Panel donor attribution (you / model).
- [x] F1-06 Visual QA round `f1` and baselines re-approved.
- [x] F1-99 Round 1 closed out (ROUND-1.md "Outcome").
- [x] F2-00 ROUND-2.md: review including F1, 4 candidates, scores, pick (Field-guide card), mini-spec.
- [x] F2-01 Registry-level `onRunUpdate` dispatch (`registerRunHandlers`); Fusion handler moved into its definition (D-030).
- [x] F2-02 Backend `FieldCardExecutor` (`load_creature → write_card → store_card`), `FieldCard` model, `RunResult.card`, mock + Meta `write_field_card`. Tests: `test_field_card.py`.
- [x] F2-03 Server-written provenance; size quotes the parents' ranges verbatim.
- [x] F2-04 `nodes/field-card/` view, validation, out-of-date detection, rewrite. Tests: `fieldCard.test.tsx`.
- [x] F2-05 PNG export (client canvas, offline-capable). Tests: e2e download check.
- [x] F2-06 Result node output port plus "Make field card" action.
- [x] F2-07 Visual QA round `f2`; baselines verified.
- [x] F2-99 Round 2 closed out (ROUND-2.md "Outcome").

### D1 Real data schema (backend only, no UI)

The real `data/chimera_data.json` uses a different schema from the invented sample. With it, the previous code found 0 hybrids and ran 0 rules, silently.

- [x] D1-01 Hybrid lookup on real `parent1`/`parent2` ("Panthera tigris (father)"): strip the role, resolve tier 1 → tier 2 → genus, match either order, keep the cross direction.
- [x] D1-02 Explicit `rule_id → check` table (`backend/app/data/rule_map.py`), new checks (R-A4-02, R-A4-03, R-A5-01, R-A2-03, R-A4-P04), step detail reports mapped/run/unmapped and is never a silent 0.
- [x] D1-03 `measurements_for` returns every row for an animal.
- [x] D1-04 Mythology resemblance (both parents, or a parent's genus/family for broad names like "bird"), with culture, verification, source. Never shown as verified unless it is.
- [x] D1-05 `backend/tests/fixtures/chimera_data.real_schema.json` (real field names and formats); full pipeline tests against both fixtures.
- [x] D1-06 Startup data check: errors logged and reported in `/health` when hybrids or rules exist but 0 resolve or map.
- [x] D1-07 Test against `data/chimera_data.json` (skipped when absent): ≥ 25/31 hybrids resolve, ≥ 40 rules map; numbers in TEST_REPORT.

**Acceptance:** pytest and npm test pass; lion+tiger finds tigon with the correct cross direction; horse+donkey finds mule; the rules step reports a nonzero mapped count; `/health` reports the data counts.

**Status: passed.** pytest 123, vitest 146. Real file: 29/31 hybrids resolve, 44/130 rules map (26 pair, 18 plan); lion+tiger → liger and tigon (tigon: father *Panthera tigris*, mother *Panthera leo*); horse+donkey → hinny and mule; bald eagle+lion → griffin.

### L1 Live Meta integration (backend only, no UI)

Budget: at most 15 image generations and 60 Muse Spark calls. Every live call is logged in `docs/LIVE_LOG.md`. Starts only after D1 passes.

- [x] L1-01 `MetaImageGen` on the Responses API (`muse-image-1.0`, `input_image` parts, `image_generation_call` result); WebP/PNG/JPEG by magic bytes; Meta response id stored on each version.
- [x] L1-02 Defaults `META_VISION_MODEL=muse-spark-1.3`, `META_IMAGE_MODEL=muse-image-1.0`.
- [x] L1-03 Retry policy: 429, 5xx, timeouts and connection errors with backoff + jitter; never 400/401/404.
- [x] L1-04 Spend guard tracks usage tokens per run and per day; tokens per step in the run detail.
- [x] L1-05 Timeouts set to about 2× the slowest observed live latency per step (numbers logged).
- [x] L1-06 Six AI-generated live fixture photos in `backend/tests/fixtures/live/` (+ README), generated once.
- [x] L1-07 `live` pytest marker (only with `CHIMERA_LIVE=1`): identify all 6, then 5 full fusions.
- [x] L1-08 Live fusions use `data/chimera_data.json` (present in the repo as of D1).
- [x] L1-09 Record and replay: live responses saved as key-free JSON fixtures; mocks return the recorded shapes.
- [x] L1-10 The plan step names the creature (no string-mash names).
- [x] L1-11 `docs/LIVE_REPORT.md` with per-fusion results, images in `docs/live/`, latency, tokens, cost, judgment, ranked problems.

**Acceptance:** default tests pass in mock mode; live tests pass or every failure is explained in LIVE_REPORT.md; budget respected; README real-mode section matches what was verified.

**Status: passed.**
- **Default runs:** pytest 132 (+6 live skipped), vitest 146, Playwright 39.
- **Live:** identify 6/6; fusions 5/5. The pinned fusion passed on its second run; the first failed with a plan timeout, explained in LIVE_REPORT problem 1.
- **Budget:** 11/15 images, 27/60 Spark calls, 367k tokens logged. Cost unknown (no reachable pricing page).

### U1 UI redesign with the ZD design system (frontend only)

ZD (`docs/design-system/ZD.md`, `zd-tokens.css`) replaces the "Field paper" identity. Design: `docs/DESIGN_U1.md`. No changes to backend behaviour, API contracts, the node registry pattern or test hooks. Leave room for L2 (wings slot, plan summary, cost) without building it.

- [x] U1-01 `docs/DESIGN_U1.md`: token usage, components, wireframes (canvas, nodes, toolbar, body diagram, result card, drawer).
- [x] U1-02 `theme.css`: ZD tokens verbatim (light `:root`, dark `[data-theme="dark"]`), Chimera tokens after them, `-aa` deviations only (logged). Self-hosted Space Grotesk, Hanken Grotesk, JetBrains Mono. `check-css.sh` and contrast tests updated for ZD.
- [x] U1-03 ZD components in React: Card, SegmentedTabs, LiveIndicator, Timeline, StatCard, BrandMark (Chimera glyph and name), Pill, Section.
- [x] U1-04 Image-first nodes: photo edge to edge, species title (never the filename), no catalog numbers.
- [x] U1-05 Fusion node: two portraits with species names, no dropdowns; slot selectors in the contextual toolbar; status + Timeline only (no result thumbnail).
- [x] U1-06 Result hero card: ≥ 2× input size, `--type-h2` name, Generated fusion pill, real-hybrid pill, SegmentedTabs versions.
- [x] U1-07 Glass contextual toolbar for node actions (hover, select, focus-within).
- [x] U1-08 Body diagram from a region list (Auto/A/B cycling, donor portraits).
- [x] U1-09 Drawer: frontend summary, stat cards (unknown, never 0), collapsible Timeline / hybrids / rules / mythology (always "Unverified") / planner notes / sources.
- [x] U1-10 12px floor for UI text (mono kickers excepted, `--text-muted` on cards).
- [x] U1-11 Screenshot round `u1` with real images (live fixtures + `docs/live/fusions`) in both themes at all viewports; review; fix blockers/majors; re-approve baselines; BEFORE_AFTER pv-3 vs u1.

**Acceptance:** backend, frontend and browser suites pass; check-css passes; axe 0 serious/critical in both themes; no ZD value edited; u1 screenshots use real images.

### P7 Shashi (needs keys)

- [ ] P7-01 Modal secret `chimera-lab` with the Meta key, Supabase URL and service key.
- [ ] P7-02 Confirm the Muse Image endpoint, fields and model ids; fix the builders and parsers in `adapters/meta/client.py` if needed.
- [ ] P7-03 Run `backend/app/adapters/supabase/schema.sql`.
- [ ] P7-04 `CHIMERA_MODE=real`, 5 real fusions, note cost and failures.
- [ ] P7-05 `modal deploy backend/app/modal_app.py`; build the frontend with `VITE_API_BASE_URL`.

---

## 9. Definition of done

- All boxes in P0 to P6, PV, F1 and F2 checked, or `[BLOCKED]` with a reason and workaround.
- `npm test`, `pytest`, `npm run e2e` (including baselines) pass; `scripts/check-css.sh` and `scripts/check-bundle.sh` pass.
- DESIGN, UI_STANDARD, DECISIONS, visual-qa INDEX, DEFECTS, BEFORE_AFTER and the round docs are complete.
- No open blocker or major visual defects. No TypeScript `any` in `nodes/`, `graph/`, `runs/`, `api/` (tested).
- A new node type needs changes only in `nodes/<type>/`, `nodes/registry.ts` and one backend executor (`docs/ADDING_A_NODE.md`).
- **Raised bar:** axe has 0 serious or critical violations in both themes; text contrast ≥ 4.5 for every text token pair (tested).

---

## 10. TEST_REPORT.md format

See `docs/TEST_REPORT.md`.

## 11. Parking lot

Fusion settings panel (edit part donors) · modifier nodes (Environment, Scale, Pose, Style, Verify) · turnaround sheet · Supabase Realtime · field-guide card output · accounts and sharing · Muse Spark Open on Modal.

## 12. Adding tasks (template)

```
- [ ] P<phase>-<nn> <one-line task>
  - Why:
  - Acceptance:
  - Touches:
  - Tests:
```

## 13. Environment variables

See `README.md` (adds `RUN_LEASE_SECONDS`, `MOCK_DELAY_SCALE`, `RETRY_BASE_SECONDS`, `LOCAL_DATA_DIR`, `RUNS_PER_MINUTE_PER_SESSION`).
