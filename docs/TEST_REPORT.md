# Test Report

Date: 2026-10-31
Mode: mock
Totals: frontend unit + component 192/192, backend 132/132 (sample + real-schema fixture + real file; 6 live tests skipped by default), e2e 39/39 (Playwright, Chromium; includes 4 visual baselines)

Commands: `cd frontend && npm test`, `.venv/bin/python -m pytest backend`, `cd frontend && npm run e2e`, `scripts/check-css.sh`, `scripts/check-bundle.sh`.

## State matrix coverage

Abbreviations for test files used below:

- **BE-A:** `backend/tests/integration/test_assets.py`
- **BE-R:** `backend/tests/integration/test_runs.py`
- **FL:** `frontend/tests/component/flows.test.tsx`
- **IMG:** `frontend/tests/unit/imagePrepare.test.ts`
- **FUS:** `frontend/tests/component/fusionNode.test.tsx`
- **IRN:** `frontend/tests/component/imageResultNodes.test.tsx`
- **SH:** `frontend/tests/component/shell.test.tsx`
- **E2E-H:** `e2e/happy.spec.ts`
- **E2E-F:** `e2e/faults.spec.ts`
- **E2E-R:** `e2e/resilience.spec.ts`
- **E2E-A:** `e2e/a11y.spec.ts`

| Section | Case | Test file | Result |
|---|---|---|---|
| 7.1 | Drop 1 image creates a node (plus Fusion, wired A) | FL "drop of 2…", E2E-H | pass |
| 7.1 | Drop 2+ at once: max 2, toast | FL "3+ at once" | pass |
| 7.1 | Paste from clipboard | Canvas paste handler; manual check in dev. *Not automated: Playwright can't synthesise a clipboard file paste in headless Chromium.* | partial |
| 7.1 | File picker | E2E-H, E2E-A (keyboard) | pass |
| 7.1 | Unsupported type (gif, svg, pdf) | IMG, FL, E2E-R, BE-A | pass |
| 7.1 | HEIC accepted, converted server-side | IMG (pass-through), BE-A `test_heic_converted_to_jpeg` | pass |
| 7.1 | Over 20 MB rejected client-side (and server) | IMG, BE-A | pass |
| 7.1 | Under 256px rejected | IMG, E2E-R, BE-A | pass |
| 7.1 | Corrupt / undecodable | IMG, E2E-R, BE-A | pass |
| 7.1 | Very large dimensions downscaled to 2048 | IMG, E2E-R, BE-A | pass |
| 7.1 | EXIF rotation applied, EXIF and GPS stripped | E2E-R (400×600), BE-A (no GPS or orientation tag) | pass |
| 7.1 | Same image twice: DUPLICATE_INPUTS | `unit/fusionValidate.test.ts`, E2E-R, BE-R | pass |
| 7.1 | Not an animal: run fails, input highlighted | FL, E2E-F, BE-R | pass |
| 7.1 | Human in photo: privacy-safe message | E2E-F, BE-R | pass |
| 7.1 | Replace image keeps id and edges, marks stale | FL, `unit/graphStore.test.ts` | pass |
| 7.2 | 0 or 1 inputs: Fuse disabled with hint | `unit/fusionValidate.test.ts`, FUS | pass |
| 7.2 | Wrong port type refused with shake and message | `unit/edgeRules.test.ts`, E2E-H | pass |
| 7.2 | Cycle refused | `unit/edgeRules.test.ts` | pass |
| 7.2 | Input still uploading / in error disables Fuse | `unit/fusionValidate.test.ts` | pass |
| 7.3 | Upload progress with percent, cancellable | IRN | pass |
| 7.3 | Step list with labels, status, elapsed | FUS | pass |
| 7.3 | Long wait (20s) and very long (120s) cancel | FUS | pass |
| 7.3 | Skeleton in Result node while generating | IRN | pass |
| 7.3 | Double-click Fuse ignored (button + idempotency key) | FUS, BE-R | pass |
| 7.4 | Success: image in the Result hero card beside the Fusion node (U1, D-054); "How this was made" | E2E-H, SH, `component/u1.test.tsx` | pass |
| 7.4 | Real hybrid badge plus facts | IRN, E2E-H, BE-R | pass |
| 7.4 | Warnings badge plus notes, image still shown | IRN, E2E-H | pass |
| 7.4 | Re-run creates v2, old versions kept, switcher | FL, IRN, E2E-H | pass |
| 7.4 | Result image fails to load: fallback with retry | IRN (screenshot state 26) | pass |
| 7.5 | One message per code; no raw upstream text | `unit/errorMessages.test.ts` | pass |
| 7.5 | Retryable shows Retry; non-retryable says what to change | FUS, E2E-F (all faults) | pass |
| 7.5 | RATE_LIMITED auto-retry countdown | FUS, E2E-F | pass |
| 7.5 | BUDGET_EXCEEDED: no retry | FUS, E2E-F, BE-R (per-run and daily caps) | pass |
| 7.5 | Unknown error: generic message + error id | FUS, `unit/errorMessages.test.ts` | pass |
| 7.6 | Node crash card; canvas usable | SH, E2E-R | pass |
| 7.6 | App crash screen; reload restores canvas | SH, E2E-R | pass |
| 7.6 | Unknown node type placeholder | SH, `unit/migrate.test.ts`, E2E-R | pass |
| 7.6 | Orphan edges removed and logged | `unit/migrate.test.ts`, FL, E2E-R | pass |
| 7.6 | Older schema migrated; newer read-only | `unit/migrate.test.ts`, E2E-R | pass |
| 7.6 | Backend restart mid-run: interrupted, re-run offered | BE-R (lease + orphan), E2E-F | pass |
| 7.6 | Corrupt IndexedDB autosave: discarded, toast | FL, E2E-R | pass |
| 7.7 | Offline banner; editing continues; autosave | SH, E2E-R | pass |
| 7.7 | Uploads queued offline, start on reconnect | FL, E2E-R | pass |
| 7.7 | Fuse disabled offline | `unit/fusionValidate.test.ts`, E2E-R | pass |
| 7.7 | Run in progress when the connection drops: pause, resume, final state | `unit/transport.test.ts`, E2E-R | pass |
| 7.7 | Server unreachable banner, distinct from offline | `unit/connectivity.test.ts`, SH, E2E-R | pass |
| 4.4/4.5 | Every mock fault gives the right code and status | BE-R (parametrised), E2E-F | pass |
| F1 | Pin parts; pins override plan; all pinned skips plan call; invalid config `GRAPH_INVALID`; v1→v2 migration; Outdated on change; one-parent hint; panel credits you/model | `test_anatomy_controls.py`, `component/anatomy.test.tsx`, E2E-H "F1 anatomy" | pass |
| F2 | Result→card connection; disabled hints; write card; ranges verbatim; server provenance; out of date + rewrite; PNG download (offline, 1600px); NOT_FOUND; timeout; vision budget | `test_field_card.py`, `component/fieldCard.test.tsx`, E2E-H "F2 field card" | pass |
| P5-05 | CORS allowlist, server size limit, rate limit, no secrets in bundle | `test_graphs_and_security.py`, BE-A, BE-R, `scripts/check-bundle.sh`, `unit/codeRules.test.ts` | pass |

## Real data (D1)

Tested against three data sources: the invented sample, the verbatim real-schema fixture (`backend/tests/fixtures/chimera_data.real_schema.json`), and the real `data/chimera_data.json` (`tests/integration/test_real_data_file.py`, skipped when the file is absent).

| Check | Real file result |
|---|---|
| Hybrids resolving both parents | **29 / 31** |
| Rules mapped to a check | **44 / 130** (26 pair, 18 plan); the 86 unmapped are data-integrity and mythology-record rules |
| lion + tiger | liger and tigon; tigon = father *Panthera tigris* × mother *Panthera leo* |
| horse + donkey | hinny and mule; mule = father *Equus asinus* × mother *Equus caballus* |
| bald eagle + lion | griffin (by name), plus bird-based matches (anzu, sphinx, …) |
| `/health` | 200 animals, 1,778 tier-2, 5,827 measurements, 31 hybrids (29 resolved), 130 rules (44 mapped), 254 mythology rows, no problems |

**Hybrids that do not resolve, and why:**

- **liliger, tiliger:** a parent is `hybrid:liger`, itself a hybrid. These can never match a pair of animal photos.

**Resolved only by genus:**

- **wolfdog, coydog:** "Canis familiaris" is not a name in either tier (domestic dog is recorded as *Canis lupus*), so it falls back to genus *Canis*. These matches are tagged `matchedVia: "genus"` and rank after exact matches.

## Live Meta API (L1)

Run with `CHIMERA_LIVE=1` only; details in [LIVE_REPORT.md](LIVE_REPORT.md), every call in [LIVE_LOG.md](LIVE_LOG.md).

| Live test | Result |
|---|---|
| Identify 6 AI-generated fixtures, match to the real data | **6/6** (all by scientific name, confidence 0.85 to 1.00) |
| lion + tiger → tigon with cross direction | pass |
| horse + donkey → mule | pass |
| bald eagle + lion → griffin | pass |
| lion + octopus → rule warnings | pass (4 warnings) |
| lion + eagle with pins (head A, limbs B) | pass on run 2; run 1 failed: plan timeout (LIVE_REPORT problem 1, fixed after) |

**Budget:** 11/15 image generations, 27/60 Muse Spark calls, 367,116 tokens logged. Cost unknown.

## U1 redesign (ZD design system)

| Check | Where | Result |
|---|---|---|
| ZD tokens pasted verbatim (no value edited) | `unit/contrast.test.ts` ("contains zd-tokens.css verbatim"); `zd-tokens.css` sha256 `b45304a3…` unchanged | pass |
| Contrast on resolved ZD tokens (var chains, tints composited on the card, color-mix): 23 text pairs at 4.5, 4 UI pairs at 3.0, both themes | `unit/contrast.test.ts` | pass (caught the dark `--indigo-700` hover at 2.2:1, D-046) |
| The four `-aa` deviations are needed (ZD value fails) and pass | `unit/contrast.test.ts` | pass |
| Gradient only on the brand mark | `unit/contrast.test.ts` | pass |
| 12px text floor (mono kickers excepted, muted) | `unit/textFloor.test.ts` | pass |
| Field-card PNG paints with tokens and fonts that exist | `unit/renderPngTokens.test.ts` (added after U1-03) | pass |
| Species titles, no filenames or catalog numbers; portraits, not dropdowns; no thumbnail in the Fusion node; hero card pills; body diagram keyboard cycling; drawer summary, "unknown" tokens, "Unverified" mythology, folded planner notes | `component/u1.test.tsx` (11 tests) | pass |
| Versions as a radiogroup (click and arrow keys) | `component/imageResultNodes.test.tsx` | pass |
| axe 0 serious/critical on empty, connected, result, drawer, error and offline states, light and dark | `e2e/a11y.spec.ts` | pass |
| Keyboard-only flow: add, fuse, open the drawer | `e2e/a11y.spec.ts` | pass |
| Visual baselines seeded with real L1 images | `e2e/visual.spec.ts` (4 baselines re-approved) | pass |

## Visual QA

- Screenshots captured: 112 (pv-1) + 162 (pv-2) + 66 (pv-3) + 36 (f1) + 36 (f2) + u1 (full matrix with real images; count in `docs/visual-qa/u1/manifest.json`). See [docs/visual-qa/INDEX.md](visual-qa/INDEX.md).
- Correction rounds: 3 (pv-1 → pv-2 → pv-3), plus u1 for the redesign (U1-01 to U1-10 in DEFECTS.md).
- Final rubric scores (lowest per criterion): hierarchy 4, clarity 4, state legibility 4, consistency 4, polish 4, craft 4.
- Defects fixed / remaining:
  - blocker: 1 fixed, 0 remaining
  - major: 9 fixed, 0 remaining
  - minor: 4 fixed, 1 wontfix (PV1-09, a throttling artefact)
- axe-core: serious 0, critical 0 (empty, connected, result, panel, error and offline states; light and dark).
- Keyboard walkthrough: pass. Hit targets ≥ 32px: pass. Layout (no overflow, no clipped text) at 1440, 1280 and 1024: pass.
- Visual regression baselines: 4 (`frontend/tests/visual/baselines/`), run in `npm run e2e`.

## Feature rounds

Round 1: **Anatomy controls** (pin head, body, limbs, covering or tail to a parent; Fusion config v2 with migration). See [docs/rounds/ROUND-1.md](rounds/ROUND-1.md). Visual round `f1`: 36 shots, no blocker or major defects.
Round 2: **Field-guide card node** (writes a specimen card with Muse Spark; downloadable PNG; server-written provenance) and registry-level run handlers. See [docs/rounds/ROUND-2.md](rounds/ROUND-2.md). Visual round `f2`: 36 shots including the exported PNG, no blocker or major defects.

## Known gaps

- Clipboard paste is implemented but not automated in e2e (headless clipboard file events).
- The 3-minute lease is tested with a 0.2s lease in the backend; the UI side uses a synthetic interrupted run.
- Mock-mode fixture photos (`backend/tests/fixtures/images/`) are flat generated illustrations (D-008). Screenshots and baselines use the L1 live images instead (D-052). In mock-run states, species labels are mock readings (U1-10).
- Runs are in-process; multi-container Modal scaling needs `Function.spawn` and a DB-backed lease (D-016).

## Unverified against live services

Verified live in L1: Muse Spark identify and plan, and Muse Image generation with references (see above). Still unverified:

- Muse Spark card writing (`write_field_card`, F2) and `previous_response_id` refinement turns.
- The 429 and 5xx retry paths (never observed live), and the Spark-client timeout fix (landed after the live runs).
- Supabase storage and DB adapters and `schema.sql`.
- Modal deployment (`modal_app.py` imports and builds its image definition; not deployed).
