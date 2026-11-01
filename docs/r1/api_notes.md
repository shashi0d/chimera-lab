# R1 Stream A notes: the agent API (branch r1-api)

## CONTRACT CHANGE REQUEST

None is blocking: everything in `docs/api_contract.md` is implemented as written. These are clarifications or
additions for the lead to accept, reject or word:

1. **`queued.ahead`.** The fixture has `position 2, ahead 2` then `position 1, ahead 1`, so `ahead` cannot mean
   "queued runs before this one". I implemented `ahead = position` ("runs that must finish or start before this
   one starts, with every slot full"). Proposed contract text: "`ahead`: how many runs must leave the queue or
   finish before this one starts (equal to `position` while every slot is busy)".
2. **Extra mock scenarios** (mock mode only, outside the contract list): `refused_animal` (the NOT_AN_ANIMAL case of
   `upload_refused.json`), `cap_daily` (POST returns `cap_daily.json`; `GET /evo/agent/limits` with the same header
   returns the capped state), `agent` (the engine's real agent loop over the mock adapters, with real identify of
   the photos and `X-Mock-Fault` honoured). Proposed: list them in the contract.
3. **`needs_choice.kind`.** The agent's `ask_user` can ask any question; every ask is sent as `kind: "host_tie"`,
   the contract's only kind. Proposed: add `kind: "question"` for asks that are not a host tie, or keep it as is.
4. **Identify options.** The v1 identify step returns one name with a confidence, so a live needs_choice has one
   option (plus `allowOther: true`). The fixture's three options only come from the mock scenario.
5. **413 before parsing.** A request whose Content-Length is over 2 x 8 MB + 2 MB is refused before the form is read,
   so `details.slot` is `null` there; a single over-size file gets its slot as in the fixture.
6. **Error envelope.** Error bodies also carry `retryAfterMs: null` and `errorId: null` (the existing envelope);
   the fixtures omit them. The UI should ignore them.

## What I built

A new package `backend/app/agentapi/` (thin wiring around the frozen engine; no file under
`backend/app/evolution/` changed):

| file | what |
|---|---|
| `routes.py` | `POST /evo/agent/runs`, `GET /evo/agent/runs/{id}`, `GET .../events` (SSE), `POST .../choice`, `GET /evo/agent/limits`, `GET /evo/creatures/{id}`, `GET /evo/gallery`, `GET /evo/files/{key}`; X-Mock-Scenario |
| `jobs.py` | `JobRunner` (in-process tasks, heartbeat lease, concurrent limit + queue with positions, choices, 14/15-min time caps), `AgentDriver` (engine `agent_fuse` with every trace step turned into events, renders uploaded as they arrive), `ReplayDriver` (fixture replay through the same runner), `DeadlineBrain` |
| `store.py` | run snapshot + stored events in the `agent_runs` collection; gapless ids; in-process wake-ups; lease interruption; startup orphans |
| `uploads.py` | type sniffing (JPEG/PNG/WebP by content), 8 MB limit, decode check, EXIF fix + resize to 1024 px before any model call, the v1 identify step, refusal wording |
| `caps.py` | daily total / per-visitor counters (UTC day), per-IP sliding-minute rate limit, client IP from X-Forwarded-For, limits view |
| `creature.py` | the Creature / GalleryItem views; hides `material_look`, `host_cover_kept`, `donor_pieces` |
| `gallery.py` | creatures in the existing `creatures` table (`kind: "evo_agent"`), the gallery order and cursor, the S5 showcase seed |
| `files.py` | public image storage: local (`/evo/files/...`) or the Supabase public bucket |
| `static.py` | one origin: `frontend/dist` at `/`, SPA fallback |
| `fixtures.py` | fixture loading for mock scenarios |

Other edits: `app/config.py` (all caps and paths as settings), `app/errors.py` (`CAP_REACHED` 429, a per-error
status override), `app/models/schemas.py` (`ErrorCode.CAP_REACHED`), `app/adapters/local/db.py` (`agent_runs`
collection), `app/pipeline/steps/identify.py` (its summary line works with one photo), `app/main.py` (wiring,
lifespan: orphans, showcase seed, shutdown), `app/modal_app.py` (ships dist/showcase/fixtures when present,
`timeout=1200`), `adapters/supabase/001_agent_api.sql` (new), `tests/conftest.py` (tests do not serve a frontend
or seed by default), `tests/agentapi/test_agent_api.py` (new).

## Decisions

1. **Agent runs get their own collection (`agent_runs`), with the events stored in the run document.** The v1
   `runs` collection is validated as v1 `Run` at startup (orphan scan), so mixing would break it. One document per
   run keeps the snapshot and its replay atomic; at about 30 events per run the rewrite per event is small. The
   migration adds only this table and a public bucket.
2. **Creatures reuse the existing `creatures` table** with `kind: "evo_agent"`; the saved doc holds the view
   (card, plan, images, anatomy map) and the full trace. `showcase` is computed from `EVO_SHOWCASE` at read time,
   so the list can change after the owner's ratings without re-seeding.
3. **Mock mode always replays a fixture** (default `success`), as the contract says; uploads are still checked by
   the real code first. The `agent` scenario exists so the real driver is tested end to end without paid calls.
4. **Replay timing**: fixture gaps x `EVO_MOCK_REPLAY_SCALE` (0.02), at most `EVO_MOCK_MAX_EVENT_DELAY` (1.5 s) per
   event, so a mock run takes a few seconds; tests use 0. A needs_choice waits for real (the real choice path); the
   replayed `ask_user` step says the actual answer, while the rest of the fixture continues as recorded.
5. **Mock `queued`** puts a queue placeholder ahead of the run and a start gate after it, so the run really goes
   through the queue (positions 2, 1, then start) without needing other runs.
6. **The 14-minute cap is a brain wrapper (`DeadlineBrain`)**: after the soft deadline the next turn calls the
   engine's own `finalize` on the best inspected image (or `inspect` on the last render first). The engine's
   decisions and wording are unchanged; the finalize event's `stop` says "at the 14-minute time cap". The 15-minute
   hard stop cancels the task (`error`, `RUN_INTERRUPTED`, retryable).
7. **Visitor = hash(X-Session-Id + client IP)**, as the contract says; rotating the session id is bounded by the
   per-IP rate limit and the daily total. Counters are incremented after identify and rolled back on a race, so a
   refused or needs_choice POST uses no run.
8. **Client IP** is the X-Forwarded-For entry `EVO_PROXY_HOPS` (1) from the right (the one the platform proxy
   wrote), never the client-supplied left end.
9. **A name beats a photo** in the same slot (that is how an identify choice is confirmed), and the photo is not read
   into a model call then.
10. **Images in public storage**: renders are stored as the model returned them (`runs/<runId>/imgN.webp`), the
    anatomy overlay and S5 showcase images as 1024 px JPEGs. Uploaded photos are never stored.
11. **Static files are served by a middleware before routing**, because the v1 route `/assets/{asset_id}` would
    otherwise shadow Vite's `dist/assets/*`. Paths under `/evo`, `/health`, `/runs`, `/graphs`, `/assets` never
    fall back to `index.html`. Stream B: avoid client routes starting with those segments.
12. **Status codes per the contract** where they differ from v1 (UNSUPPORTED_FILE 422, an answered choice 409) via
    a per-error override, so v1 keeps its own.
13. **The showcase is seeded in the background at startup** (and on first gallery read if that has not finished),
    from `docs/evolution/live/s5/<case>/agent/`; a missing folder is skipped with a warning.
14. **One process, one worker** stays the deployment rule (D-016). A choice POST or SSE wake-up on another process
    would not reach the run; SSE in another process falls back to polling the store every second.

## Tests

- New: `backend/tests/agentapi/test_agent_api.py`, **38 tests**. They cover the event sequence and payloads of
  every run fixture (success, cap, error, queued, host tie with the choice POST), the snapshot and creature against
  `run_success.json` / `creature_b09.json`, resume (Last-Event-ID, `?after=`, header wins, after the end), a resume
  mid-run, keep-alive pings, choice errors and expiry, refusals (fixture scenarios and the real checks: sniffed type,
  8 MB, corrupt, person, not an animal), identify_choice and its follow-up, real low-confidence needs_choice, daily
  and visitor caps, the cap_daily fixture, limits, the per-IP rate limit, the concurrent limit with queue positions,
  the lease and startup orphans, the gallery order and cursor, the showcase view, a configurable showcase, files,
  the time caps, the real agent path, and single-origin serving.
- Full suite: **997 passed, 6 skipped** (baseline 959 passed, 6 skipped).
- `scripts/check-bundle.sh`: passes ("no secrets or test hooks", 644K).
- Real-server smoke on port 8300 (uvicorn, mock mode, built frontend): `/`, a client route, a bundle file,
  limits, gallery, a host-tie run streamed live over HTTP with the choice posted mid-stream (29 events), resume
  from Last-Event-ID 27, the `agent` scenario with its images and anatomy overlay served, a refusal.

## Blocked or not done

- No deploy (R1 rule). The host comparison in `deploy_checklist.md` comes from web-search results only: direct
  fetches of render.com, railway.com, fly.io and modal.com were blocked by this session's network allow-list, so
  third-party and unconfirmed claims are marked.
- The Supabase adapters and the migration have not been run against a live project (no keys, as in P7-03).
- Real mode was not exercised (no paid calls). The AgentDriver's real-mode branch (SparkOpenBrain on Baseten)
  differs from the tested mock branch only in the brain it wraps.
- Choices and live wake-ups are per process (decision 14).
