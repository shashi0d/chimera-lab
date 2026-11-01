# Built during the hackathon

The hackathon rules ask that new work be clearly identified and that the demo show only work built during the event
(building period Oct 27 to Nov 4, 2026). This file lists what was built, when, and in which commits. It also lists
everything in the repo that came from outside or existed before the repo, with its licence where known.

Sources: `git log --all` on branches `main` and `evo`, `docs/BUILD_LOG.md`, `docs/DECISIONS.md` and the step reports
in `docs/evolution/`. Times below are US Eastern (the deadline's time zone), converted from the commit timestamps.

## Summary

- **First commit:** `176c6b7` "Initial commit", Oct 29, 2026, 10:19 PM Eastern (Oct 30, 02:19 UTC). The repo is
  `shashi0d/chimera-lab` (D-001). `docs/BUILD_LOG.md` dates the first phases 2026-10-30, which is the UTC date.
- **Last commit at the time of writing:** `990703e` "R1 step 0: API contract", Nov 1, 2026, 5:24 PM Eastern.
- **Every commit in the repo falls inside the building period.** 121 commits on `evo` (which contains all 21 of
  `main`).
- **Who built it:** a solo developer (the owner, git author `shashi0d`) with Claude Code as the coding agent. 20
  commits have the author `Claude`; the other 101 have the author `shashi0d`, and their messages carry a
  `Co-Authored-By: Claude` trailer (for example `98d4d8c`). `TASKSHEET.md` names the builder as "Claude Code cloud
  (autonomous)".
- **Two products in the history:**
  - `main` (Oct 29 to 30): v1, a node-canvas app that fuses two photos in a fixed pipeline. D-096 removes it from the
    UI; its backend endpoints stay, unused.
  - `evo` (Oct 31 to Nov 1, branched from `main` at `239078b`): the evolution engine and the agent, which is the
    demo path (D-096).
- **What existed before the repo or came from outside:** the animal dataset (built Oct 28 per its own metadata),
  the research documents the owner supplied, the ZD design system tokens, fonts, third-party libraries and the
  hosted models. See the table at the end.

## Dated list, by date and phase

### Oct 28 (before the repo): the dataset

- `data/chimera_data.json` carries `"built": "2026-10-28"` and `"from": "Muse final.json (Tier 2 script data + Tier
  11 research), cleaned by Claude"` in its `meta` block, with four cleaning passes dated 2026-10-28. It entered git
  on Oct 30 in `d60ca90` (D1).
- When "Muse final.json" itself was gathered is not recorded in the repo: **unknown**. The file it refers to
  (`chimera_info.md`) is not in the repo.

### Oct 29, 10:19 PM to Oct 30, 12:03 AM: v1 app (branch `main`)

`176c6b7` to `e58ca0a`. Phases P0 to F2 in `docs/BUILD_LOG.md`.

| Commit | Phase | What |
|---|---|---|
| `176c6b7` | | Initial commit (README only), made on GitHub |
| `43adbf3` | P0, P3 | FastAPI app, adapters (mock, local, Meta, Supabase), the v1 fusion pipeline, backend tests |
| `7337e66` | P1, P2, P4 | React node canvas, node registry, image, fusion and result nodes, runs, autosave, theme |
| `8dab0f7` | P6 | Frontend unit and component tests, contrast, no-any and bundle checks |
| `06a2f35` | P5, P6 | Playwright end-to-end tests; fixes the tests found (D-019 to D-022) |
| `243aa6f`, `35ba4b6` | PV | Screenshot rounds pv-1 to pv-3, UI standard, defects fixed, docs |
| `290117e` | F1 | Anatomy controls (part donor pins) |
| `69b9123`, `d37fa19`, `e58ca0a` | F2 | Field-guide card node, PNG export, README |
| `bd27b86` (Oct 30, 6:55 AM) | | Merge of the GitHub initial commit |

### Oct 30, 6:50 PM to 9:22 PM: real data, live Meta models, redesign, direct experiments (branch `main`)

`d60ca90` to `239078b`.

| Commit | Phase | What |
|---|---|---|
| `d60ca90` | D1 | Real data schema: the dataset committed (D-033), hybrid lookup, explicit rule map (44 of 130 rules, D-035), mythology matching, data health |
| `7d1d47b` | L1 | Live Meta integration: Muse Spark 1.3 and Muse Image 1.0 adapters, token accounting, a hard live budget, record and replay mocks; verified live on 5 fusions (`docs/LIVE_REPORT.md`) |
| `71a091b`, `9926710`, `95b3a21` | U1 | UI redesign with the ZD design system tokens (frontend only); 250 screenshots |
| `eb7189d`, `bfcdeb1`, `958863c`, `239078b` | | Four direct Meta API experiments with no app logic (`docs/live/direct*/README.md`) |

### Oct 31, 7:54 AM to 11:58 PM: the evolution engine (branch `evo`)

| Commits | Phase | What | Report |
|---|---|---|---|
| `98d4d8c` to `2ea3666` | E1 | Owner's research docs added; `scripts/verify_research.py`; the engine under `/evo` against mocks; rule cards (94, 11 hard) | `docs/evolution/E1_OFFLINE.md` |
| `e082ef1` to `0997a50` | E2, E2b to E2d | Live Spark, SAM 3.1 and Muse Image adapters; SAM mask parser; the 4 worked examples live; third-animal leakage fixes; real-hybrid prompt; checklist critic | `docs/evolution/E2_LIVE.md` |
| `3ada791` to `98bef76`, `50a1633` | E4 | Open-world resolver (database, learned cache, GBIF exact match), routing by taxonomy distance, function audit, fiction budget, "Can it live" | `docs/evolution/E4_OPEN_WORLD.md` |
| `34884a7` to `ec8b198` | S1 | Baseten adapter for Muse Spark Open; live probes of Spark Open, Muse Image references and edits, SAM part prompts | `docs/evolution/S1_CAPABILITIES.md` |
| `155c6da` to `37c8dc6` | S2 | Fix pack: prompt compiled only from the structured plan, typed plan operations, web-cited traits, routing per call type, inspect and one edit turn | `docs/evolution/S2_FIXPACK.md` |
| `d0c38b7` to `4eba284` | S3a (parts 1, 2, 4, 5) | Gold set of owner-labelled images, plan-blind critic protocol, citation verification, R10 cards 12 to 14 | `docs/evolution/S3a_TRUST.md` |

### Nov 1, 12:14 AM to 5:24 PM: trust layer, traits, the agent, the benchmark (branch `evo`)

Clocks changed from EDT to EST at 2 AM on Nov 1, so the commit offsets change from -0400 to -0500.

| Commits | Phase | What | Report |
|---|---|---|---|
| `1f6b0ed` to `cb1181b` | S3a (parts 3, 6 to 9) | Critic calibration (6 of 6 failures caught, 0 of 5 false alarms), tests, integration experiment (30 images), owner review sheet | `docs/evolution/S3a_TRUST.md` |
| `6e47b91` to `68d02af` | S3b | Owner's R10 files placed; trait transfer instead of part transfer; covering compiler; growth by edit; critic recalibrated on 33 owner-labelled images | `docs/evolution/S3b_TRAITS.md` |
| `cbd1b1a` to `bc13dd0` | S3c | Plan fixes from owner decisions; the agent core (Spark Open tool loop with guardrails in code); images on disk and resumable runs; the two-failure rule; 8 live validation creatures plus the fixed pipeline | `docs/evolution/S3c_AGENT.md` |
| `ed64cd9` to `9ec64e1` | S5 | Material-only operation, finalize reason, one schema per plan operation; the anatomy map; the frozen 11-case benchmark; 22 live creatures (`d6b5d8f` to `3d0b519`); blind owner review sheet | `docs/evolution/S5_BENCHMARK.md` |
| `990703e` | R1 step 0 | API contract and fixtures for the submission build; owner decisions D-096 | `docs/api_contract.md` |

### Nov 1 onward: R1, the submission build (in progress)

Three parallel streams on branches `r1-api` (backend), `r1-ui` (frontend) and `r1-docs` (these documents), each
based on `evo` at `990703e`. Their commits will be listed here by the lead at merge. Nothing from R1 was merged at
the time of writing.

## What the demo may show

Everything the demo shows comes from the commits above: the agent, the engine, the UI built in R1, and the creatures
from the S5 benchmark run (`docs/evolution/live/s5/`, commits `d6b5d8f` to `3d0b519`, Nov 1) or from live runs made
after R1. The ZD design system gives the UI its colors and type; the UI components themselves were written in this
repo (U1, `71a091b`). The owner should confirm the ZD question below before the video.

## From outside, or existing before the repo

| Item | Where in the repo | Origin | When | Licence |
|---|---|---|---|---|
| Animal dataset: 200 animals, 1,778 tier-2 animals, 5,827 measurements, 31 hybrids, 254 mythology rows, 130 rules | `data/chimera_data.json` | Owner's research data; its `meta` says built from "Muse final.json", cleaned by Claude. Per-row source URLs point to animaldiversity.org (638 URLs), api.gbif.org (1,978), zenodo.org record 6468938 (5,540) and en.wikipedia.org (381) | Built Oct 28 (its metadata); committed Oct 30 (`d60ca90`) | **Unknown.** The file states no licence. The licences of Animal Diversity Web, GBIF records, the Zenodo record and Wikipedia text as used here have not been checked. Which dataset Zenodo record 6468938 is has not been confirmed in the repo. |
| Research docs R1 to R10, RESEARCH_SUMMARY, ALGORITHM v1 | `docs/evolution/research/`, `docs/evolution/ALGORITHM.md` | Supplied by the owner ("The docs were already in docs/evolution/", BUILD_LOG E1). They cite third-party papers and pages by URL; `scripts/verify_research.py` checks the links | Headers say "first pass (Oct 31, 2026)"; committed Oct 31 (`98d4d8c`); R10 placed Nov 1 (`6e47b91`) | The docs: the owner's own (to confirm). How they were written is not recorded in the repo: **unknown**. The cited works keep their own copyrights. |
| Owner's planning script and review notes | `scripts/plan_evolution_sim.py`, `docs/evolution/benchmark/s3a_owner_review.md` | The owner | Placed Nov 1 (`6e47b91`) | The owner's own |
| ZD design system tokens (183 tokens) and usage notes | `docs/design-system/zd-tokens.css`, `docs/design-system/ZD.md`; pasted verbatim into `frontend/src/styles/theme.css` (D-045) | `ZD.md`: exported from the Claude Design project `ZeroDistanceCMSDesignSystem_3e5a47` (`ZeroDistance_Dashboard.html`). Tokens only; the component code was written here | The export date is **unknown**. Committed Oct 30, 8:14 PM (`71a091b`) | **Unknown.** Whether it may be public is an open question for the owner. |
| Fonts: Space Grotesk, Hanken Grotesk, JetBrains Mono (woff2) | `frontend/public/fonts/` | `@fontsource/*` npm packages | Third party | OFL-1.1 (from the packages' `package.json`) |
| React Flow structural CSS | vendored into `theme.css` (D-010) | `@xyflow/react` | Third party | MIT (package metadata) |
| SAM mask parser `meta-sam-parser==0.1.0` | `backend/requirements.txt` | Meta; decodes SAM 3.1 masks (E2). Installed with the owner's approval (BUILD_LOG E2) | Third party | "SAM License" (package metadata). `backend/app/evolution/live.py` notes it forbids reverse engineering the mask format, which is why the package is used |
| Other backend libraries | `backend/requirements.txt` (FastAPI, uvicorn, Pydantic, Pillow, pillow-heif, httpx, openai, supabase, pypdf) | Third party | | FastAPI MIT, pypdf BSD (package metadata); the rest not checked |
| Frontend libraries | `frontend/package.json` (React, React Flow, Zustand, idb-keyval; dev tools) | Third party | | React, @xyflow/react and Zustand MIT; idb-keyval Apache-2.0 (package metadata); dev tools not checked |
| Hosted models and services | adapters in `backend/app/adapters/` and `backend/app/evolution/` | Meta Model API (Muse Spark 1.3, Muse Image 1.0, SAM 3.1), Baseten (Muse Spark Open), GBIF API, Supabase | Used at run time, not copied in | The providers' terms; not reviewed here |
| Test and fixture images | `backend/tests/fixtures/images/`, `backend/tests/fixtures/live/` | Generated, not photographs: v1 fixtures painted by a script (D-008); six live fixtures made with Muse Image (D-044) | Built during the event | Generated in this repo |

## Not built, or cut

- **Goal mode** (ROADMAP step 6): cut for the submission (D-096).
- **Evolve carry-over, battle and collectible features, self-hosted Muse Glimmer:** deferred until after the
  submission (`docs/evolution/ROADMAP.md` section 6).
- **Deployment:** hosting is not decided (D-096). Supabase and Modal adapters exist but were not verified live
  (the v1 README's "Not verified live" list, at `990703e`: "Supabase adapters and Modal deployment").
