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
