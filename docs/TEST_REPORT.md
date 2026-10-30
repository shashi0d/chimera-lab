# Test Report

Date: 2026-10-30
Mode: mock
Totals: unit 95/95 (frontend) + 27/27 (backend), component 40/40, backend integration 48/48, e2e 37/37 (Playwright, Chromium; includes 4 visual baselines)

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
| 7.4 | Success: image in the Fusion summary and the Result node; "How this was made" | E2E-H, SH | pass |
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
| P5-05 | CORS allowlist, server size limit, rate limit, no secrets in bundle | `test_graphs_and_security.py`, BE-A, BE-R, `scripts/check-bundle.sh`, `unit/codeRules.test.ts` | pass |

## Visual QA

- Screenshots captured: 112 (pv-1) + 162 (pv-2) + 66 (pv-3). See [docs/visual-qa/INDEX.md](visual-qa/INDEX.md).
- Correction rounds: 3 (pv-1 → pv-2 → pv-3).
- Final rubric scores (lowest per criterion): hierarchy 4, clarity 4, state legibility 4, consistency 4, polish 4, craft 4.
- Defects fixed / remaining:
  - blocker: 1 fixed, 0 remaining
  - major: 9 fixed, 0 remaining
  - minor: 4 fixed, 1 wontfix (PV1-09, a throttling artefact)
- axe-core: serious 0, critical 0 (empty, connected, result, panel, error and offline states; light and dark).
- Keyboard walkthrough: pass. Hit targets ≥ 32px: pass. Layout (no overflow, no clipped text) at 1440, 1280 and 1024: pass.
- Visual regression baselines: 4 (`frontend/tests/visual/baselines/`), run in `npm run e2e`.

## Feature rounds

Round 1: see [docs/rounds/ROUND-1.md](rounds/ROUND-1.md) (in progress).
Round 2: see [docs/rounds/ROUND-2.md](rounds/ROUND-2.md) (pending).

## Known gaps

- Clipboard paste is implemented but not automated in e2e (headless clipboard file events).
- The 3-minute lease is tested with a 0.2s lease in the backend; the UI side uses a synthetic interrupted run.
- Fixture "photos" are generated illustrations (D-008). Real photos are needed for the demo video.
- Runs are in-process; multi-container Modal scaling needs `Function.spawn` and a DB-backed lease (D-016).

## Unverified against live services

- Meta Muse Spark / Muse Image adapters (`backend/app/adapters/meta/client.py`): request shapes, endpoint path, model ids and error mapping are tested only against recorded-shape fakes.
- Supabase storage and DB adapters and `schema.sql`.
- Modal deployment (`modal_app.py` imports and builds its image definition; not deployed).
