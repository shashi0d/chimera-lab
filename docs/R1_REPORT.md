# R1 report: parallel build toward submission

Branch `evo`, Nov 1 to 2, 2026. Engine frozen; mock mode only; no paid model calls. Contract `docs/api_contract.md`
(1.1), fixtures `docs/api_fixtures/`. Decisions D-096 to D-099. `main` is untouched.

## How it ran

- **Step 0** (lead, `990703e`): the contract, the SSE schema and 11 fixtures built from real S5 runs.
- **The streams.** The three streams launched from the owner's laptop never reached GitHub, so they were rerun here
  as three parallel subagents on git worktrees: `r1-api` (backend/), `r1-ui` (frontend/) and `r1-docs`
  (docs/submission/).
  - Every command ran in mock mode with the API keys removed from its environment.
  - A container restart stopped Stream B midway. Its commits survived, and it resumed from its transcript.
- **Merges.** All three branches are merged into `evo`. The owner's own push during R1 (S5: 7 of 11 cases are host
  ties, not 6) was merged too, and carried into the submission docs.

## What each stream built

### Stream A: backend (`docs/r1/api_notes.md`)

- **Package.** A new `backend/app/agentapi/`. No file in `backend/app/evolution/` changed (checked with `git diff`).
- **Endpoints:**
  - `POST /evo/agent/runs`
  - `GET /evo/agent/runs/{id}`
  - `GET /evo/agent/runs/{id}/events` (SSE)
  - `POST /evo/agent/runs/{id}/choice`
  - `GET /evo/agent/limits`
  - `GET /evo/creatures/{id}`
  - `GET /evo/gallery`
  - `GET /evo/files/{key}`
- **Job runner:**
  - In-process tasks with a heartbeat lease (D-016).
  - A concurrent limit of 3, with a queue that reports positions.
  - Choices expire after 120 s.
  - At 14 minutes a `cap_reached` (time) event fires and the agent finalizes its best image; at 15 minutes the
    runner stops the run.
  - The `X-Mock-Scenario` header replays any fixture through the real runner, event store and SSE path.
- **SSE:**
  - Event ids have no gaps.
  - Streams resume from `Last-Event-ID` or `?after=`.
  - A `: ping` keep-alive is sent every 15 s.
  - The stream closes after `finalize` or `error`.
- **Uploads:**
  - JPEG, PNG or WebP, detected from the file content.
  - At most 8 MB, decode-checked, and resized to 1024 px before any model call.
  - Identified with the v1 identify step, then discarded. Photos are never stored.
  - Photos of people and images with no animal are refused with the contract's messages.
- **Caps:**
  - 50 runs per day in total and 3 per visitor per day (429 `CAP_REACHED`).
  - 5 POSTs per minute per IP (429 `RATE_LIMITED` with `Retry-After`).
  - All are env-configurable.
- **Creatures and gallery:**
  - Saved in the existing `creatures` table with card, plan, trace, images and anatomy map.
  - The material-only checks are hidden and counted in `hiddenChecks`.
  - Showcase seeded from S5 (`EVO_SHOWCASE`: b09, b01, b03, b08, b11, b05).
  - The gallery works while live runs are capped.
- **One origin.** `frontend/dist` is served at `/` with an SPA fallback, and the API under `/evo`.
  `modal_app.py` still works and ships the dist, the showcase and the fixtures.
- **Migration.** `backend/app/adapters/supabase/001_agent_api.sql` adds the `agent_runs` table and a public
  `chimera-public` bucket. Writes need the service key.
- **Deploy checklist.** `docs/r1/deploy_checklist.md`: what a host must provide, env vars and secrets, Supabase
  steps, start and smoke commands, and the host comparison below.

### Stream B: frontend (`docs/r1/ui_notes.md`)

- **Screens:**
  - The gallery is the first screen, with one action to make a new creature and the run limits shown, including the
    capped state before any upload.
  - The agent Fusion node takes two photos or two typed names, plus a mode. The v1 fusion path is gone from the
    UI; its backend endpoints stay, unused.
  - The live trace panel shows:
    - each step with the agent's reason and the cited rule cards
    - "A creature takes about 5 minutes"
    - the queue position
    - the per-run cap as a notice, not an end
    - the host-tie question with its expiry
  - The creature card shows:
    - image, and host with its reason
    - the Can-it-live summary
    - "Generated fusion" on every generated image
    - the anatomy overlay toggle with a parent legend
    - an honest count of hidden checks
    - both picks only when the agent and the code ranking differ
  - Identify confirmation dialog; every refusal, the daily cap, the rate limit and errors each have their own
    message.
- **Routing and resume:**
  - The run id is in the URL (`?run=`). Reloading resumes from the last event, and a finished run opens the creature.
  - Routes are query strings on `/` (`?view=lab`, `?run=`, `?creature=`), so nothing collides with the API paths.
- **Mock transport:**
  - Fixture-backed, for dev and tests, selected with `?mock=<scenario>`. Fixture images are served by the dev server.
  - Neither ends up in the production bundle (check-bundle).
- **Screenshots.** 60 reviewed screenshots (15 states × 1440x900 and 390x844 × light and dark) in
  `docs/r1/ui_shots/`, re-shot after the palette change. Review found 12 defects, 6 of them major and 1 a serious
  accessibility issue; all are fixed (table in the notes).

### Stream C: submission docs (`docs/r1/docs_notes.md`, `docs/submission/`)

- **Documents:**
  - `README.md`: the rewrite, now at the repo root, with its status line updated for R1.
  - `docs/submission/BUILT_DURING_HACKATHON.md`: dated list from git history, plus a table of what came from outside.
  - `ARCHITECTURE.md`: two Mermaid diagrams, rendered and checked.
  - `VIDEO_SCRIPT.md`: 3:00, marked pending the owner's ratings.
  - `SUBMISSION_FORM.md` and `X_POST.md`.
- **Correction found.** S5 known limit 4 was wrong for b03: the plan picks the eagle's head. It is corrected in
  `S5_BENCHMARK.md`, with better examples of the image model ignoring a prompt (b08, b06, b02). Still open: the b03
  anatomy map colours that head as the lion's.

### Lead

- **Contract 1.1:** six clarifications from Stream A, none blocking:
  - the queue's `ahead` field
  - three extra mock scenarios
  - one `needs_choice` kind
  - one option on a live identify
  - a 413 refused before the form is parsed
  - null fields in the error envelope
- **End-to-end suite.** `frontend/tests/integration/r1_end_to_end.spec.ts` with `playwright.integration.config.ts`:
  the built UI is served by the real backend in mock mode and driven through every fixture scenario.
- **Chimera palette (D-098).** The owner asked to keep the ZD backbone and replace every colour.
  - The brand is teal, the ink a warm graphite, and the status colours are retuned. Donor B is amber, matching the
    engine's anatomy map.
  - All 27 contrast pairs pass in both themes, and axe stays at 0 serious or critical.
- **Owner answers recorded (D-097):**
  - The dataset may be public.
  - ZD is the owner's own work.
  - The data and research were made during the event.
  - The pitch stays as written.

## Contract changes

1.1 only, as listed above. Neither the UI nor the docs stream asked for a change. Stream B asked for one fixture: a
creature where `agree` is false. It built a labelled constructed one in the mock instead. Converting a real case with
a split pick would let the both-picks view show real data.

## Test results (all on the merged `evo`)

| Suite | Result | Before R1 |
|---|---|---|
| Backend (pytest, mock) | **997 passed, 6 skipped** (38 new in `tests/agentapi/`) | 959 passed, 6 skipped |
| Frontend unit and component (vitest) | **189 passed** (v1-only tests removed, agent API tests added) | 193 |
| Browser e2e (Playwright, mock transport) | **40 passed** (one per fixture, resume, axe light and dark, keyboard, layout at 390, 1024 and 1440) | 40 (v1 suite) |
| End to end, built UI through the real backend (mock) | **15 passed**: gallery, success (saved and listed), resume after reload, host tie, identify choice, render cap, queued, error, 4 refusals, daily cap at POST and via limits, unknown run | none |
| `scripts/check-css.sh` | pass | |
| `scripts/check-bundle.sh` | pass (676 KB; no secrets, test hooks or mock code) | |

**Flaky test:** on one full Playwright run the first axe test failed on a cold start, then passed on two full
reruns. If it recurs, give the first test a warm-up.

## Blocked or not verified

- **Live mode** was not exercised (by design: no paid calls in R1).
- **Supabase:** the adapters and the new migration have never run against a live project (`P7-03`).
- **One process only.** Choices and live wake-ups are in-process, so the deploy must be one instance and one worker
  (D-016).
- **Host claims.** The host sites were blocked from the session, so the host claims come from search results, with
  the third-party and unconfirmed ones marked.
- **Mock timers.** In mock mode the elapsed timer reads about 00:00, because the replay clock is sped up.
- **Narrow screens.** At 390 px the canvas can sit partly under the floating tool rail; the canvas is desktop-first
  by agreement.
- **Pixel baselines.** The v1 pixel baselines were removed with the v1 UI. The reviewed screenshots stand in until
  the UI settles; add new baselines in R2.

## Host comparison (from `docs/r1/deploy_checklist.md`)

| | Render | Railway | Fly.io | Modal |
|---|---|---|---|---|
| One long process | yes | yes | yes | yes, with one container min and max |
| 15-minute SSE | 100-min request timeout (third-party) | 15-min HTTP cap, the same as our hard stop (third-party); some 5-min reports | unverified | 150 s request cap (official): the trace reconnects every 150 s |
| Free tier | 750 h/month, but sleeps after 15 idle min and takes about 1 min to wake | $5 trial credit (third-party) | none for new orgs | $30/month credits |
| Small paid box | Starter $7/month (third-party) | Hobby $5/month (third-party) | about $6/month (third-party) | per second |

Stream A recommends **Render Starter**, or Railway Hobby. Both are one always-on uvicorn process with long SSE.
Modal works but reconnects the trace every 150 s, and Fly.io has no free tier. Check the official pricing pages
before paying.

## What R2 needs

1. **Host choice** (owner). Then build with `npm ci && npx vite build` and start with the one-worker uvicorn command
   in `docs/r1/deploy_checklist.md` section 4.
2. **Secrets on the host:**
   - `META_API_KEY`, `BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `CHIMERA_MODE=real`
   - the caps (`EVO_DAILY_RUNS`, `EVO_VISITOR_DAILY_RUNS`, `EVO_MAX_CONCURRENT_RUNS`,
     `EVO_RUNS_PER_MINUTE_PER_IP`)
   - `EVO_SHOWCASE`
3. **Supabase:**
   - Run `backend/app/adapters/supabase/schema.sql`, then `001_agent_api.sql`.
   - Confirm the `chimera-public` bucket is public-read, and that writes work only with the service key.
4. **Smoke tests.** Mock mode first, with the curl sequence in the checklist. Then one live run end to end from the
   deployed UI, which is the first paid run since S5.
5. **Owner inputs:**
   - S5 ratings, which set `EVO_SHOWCASE` and the video script.
   - Problem-statement wording, prize flags, and whether to mention the Claude Code build.
6. **Visual baselines.** New pixel baselines for the gallery, trace and card once the UI is final.
7. **b03 anatomy map** (optional): find why the head is coloured as the lion's when the plan's head is the eagle's.
   That is engine work, so it needs the owner's approval while the engine is frozen.
