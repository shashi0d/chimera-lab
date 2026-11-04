# R1 deploy checklist (Stream A)

> **Updated Nov 3:** the app is live-only (no `CHIMERA_MODE`, no mock fixtures) and has accounts (Supabase Auth).
> Runs, the Lab and caps belong to the signed-in user; requests carry `Authorization: Bearer <token>`, not
> `X-Session-Id`. The Lab and its setup: `docs/LAB.md`. The host comparison below is unchanged.

Status: **not deployed** (R1 rule). This page lists what any host must provide, how to configure it, and compares four
hosts. The app is one FastAPI process (uvicorn) serving the built frontend at `/` and the API under `/evo`
(D-096). Nothing in it depends on Modal.

## 1. What the host must provide

| need | why | notes |
|---|---|---|
| **One long-running Python 3.11+ process**, kept alive, **exactly one worker** | agent runs are in-process asyncio tasks (D-016) that last up to 15 min (`EVO_RUN_HARD_SECONDS`=900); the queue, choices and live SSE wake-ups are in memory | do not scale to 2+ instances or `--workers 2`: a choice POST or an SSE stream landing on another process cannot reach the run. Scale-to-zero must not kill the process while a run is going (an idle-timer that only counts inbound HTTP is fine as long as a client streams; see risks) |
| **Streaming HTTP responses** (SSE, `text/event-stream`) without buffering | the live trace | the app sends `: ping` every 15 s and `X-Accel-Buffering: no`. A platform request-time cap is survivable: the stream resumes with `Last-Event-ID` (EventSource reconnects by itself) |
| **Outbound HTTPS** | Meta API (`api.meta.ai`), Baseten (`inference.baseten.co`), GBIF, Supabase | |
| **Secrets as env vars** | below | never in the frontend bundle (`scripts/check-bundle.sh`) |
| ~1 GB RAM | engine + PIL on 1600 px images; images live on disk, not in memory (D-090) | measured limits: UNVERIFIED for live runs on a 512 MB box |
| Writable local disk (ephemeral is fine with Supabase) | per-run image folder `LOCAL_DATA_DIR/agent_runs/<runId>` (deleted after finalize); without Supabase, also the SQLite store and `/evo/files` | without Supabase an ephemeral disk loses the gallery on restart |
| The repo's `data/` and `docs/evolution/live/s5/` (showcase source) | the showcase is seeded from the S5 outputs at startup | a missing case folder is skipped with a log warning |

## 2. Environment variables and secrets

Secrets (set in the host's secret store):

| name | needed for |
|---|---|
| `META_API_KEY` | real mode: identify (Muse Spark), renders (Muse Image), critics, SAM |
| `BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26` | real mode: the agent brain (Muse Spark Open on Baseten) |
| `SUPABASE_URL` | persistent store + public image bucket |
| `SUPABASE_SERVICE_KEY` | backend-only writes (service role). Never expose it to the browser |

Configuration (defaults in `backend/app/config.py`):

| name | default | meaning |
|---|---|---|
| `EVO_DAILY_RUNS` | 50 | agent runs per UTC day, all visitors |
| `EVO_VISITOR_DAILY_RUNS` | 3 | per signed-in user per day |
| `LAB_DAILY_ACTIONS` / `LAB_USER_DAILY_ACTIONS` | 100 / 20 | Lab edits, reviews and collaborator messages per day |
| `EVO_MAX_CONCURRENT_RUNS` | 3 | more are queued with a position |
| `EVO_RUNS_PER_MINUTE_PER_IP` | 5 | POST rate limit |
| `EVO_RUN_SOFT_SECONDS` / `EVO_RUN_HARD_SECONDS` | 840 / 900 | finalize-best at 14 min, stop at 15 |
| `EVO_CHOICE_SECONDS` | 120 | host-tie choice wait |
| `EVO_SHOWCASE` | `b09,b01,b03,b08,b11,b05` | S5 case ids (or `crt_...` creature ids), gallery order; update after the owner's ratings |
| `EVO_PROXY_HOPS` | 1 | trusted proxies in front (client IP = X-Forwarded-For entry this many from the right). Set 0 when nothing proxies |
| `EVO_PUBLIC_BUCKET` | `chimera-public` | Supabase public bucket for generated images |
| `EVO_IDENTIFY_MIN_CONFIDENCE` | 0.6 | below: POST returns needs_choice |
| `FRONTEND_DIST` | `frontend/dist` | built SPA |
| `EVO_SHOWCASE_DIR`, `EVO_FIXTURES_DIR`, `LOCAL_DATA_DIR`, `DATA_PATH` | repo paths | relative paths resolve from the repo root |
| `CORS_ORIGINS` | localhost:5173 | only for two-port local dev; production is one origin |

Per-run caps (4 renders, 30 tool calls, 6 edits) are the engine's `data/evo_config.json` `agent` block (frozen).
Spend guards also apply: `DAILY_GENERATION_CAP`, `DAILY_TOKEN_CAP`, `MAX_TOKENS_PER_RUN`.

## 3. Supabase setup

1. Create the project; copy the URL and the **secret** key (`sb_secret_...`, legacy name service_role) into the
   host secrets as `SUPABASE_URL` and `SUPABASE_SECRET_KEY` (`SUPABASE_SERVICE_KEY` is also accepted).
2. SQL editor: run `backend/app/adapters/supabase/schema.sql` (existing tables, `incr_counter`, private
   `chimera-assets` bucket), then `backend/app/adapters/supabase/001_agent_api.sql` (adds `agent_runs`, a
   `creatures.kind` index, and the **public** `chimera-public` bucket; no write policies, so only the service key
   writes), then `002_lockdown_and_indexes.sql` (only the service role may call `incr_counter`; `assets` indexes),
   then `003_table_grants.sql` (newer projects give the API roles no data privileges on new tables: this grants
   them to service_role only; without it every write fails with `permission denied for table assets`).
   Then `004_lab_owner_index.sql`. Also set `SUPABASE_PUBLISHABLE_KEY` (sign-in) and, under Authentication →
   URL Configuration, the Site URL and Redirect URLs for the host (docs/LAB.md → Setup).
3. Check: `select id, public from storage.buckets;` shows `chimera-public | true`.
4. Image URLs then look like `$SUPABASE_URL/storage/v1/object/public/chimera-public/runs/<runId>/img1.webp`;
   `/evo/files/...` redirects there.
5. Verified 2026-11-03 against a live project (Postgres 17): document put/get/list, upsert, `incr_counter`, both
   buckets, and that the publishable key can neither read, write nor call `incr_counter`.

## 4. Build, start and smoke-test

```bash
# build (repo root)
python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci && npx vite build)          # -> frontend/dist
bash scripts/check-bundle.sh                        # must print "no secrets or test hooks"

# start (one process, one worker; PORT from the host)
cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8300}" \
    --workers 1 --proxy-headers --timeout-keep-alive 75
```

Smoke (no paid calls; `B=https://<host>` or `http://127.0.0.1:8300`):

```bash
curl -s $B/health                                   # {"status":"ok","version":...}
curl -s -o /dev/null -w "%{http_code}\n" $B/        # 200 (index.html)
curl -s $B/evo/config                               # supabaseUrl, publishable key, authConfigured true
curl -s "$B/evo/gallery?limit=6" | head -c 300      # six showcase creatures
curl -s -o /dev/null -w "%{http_code}\n" $B/evo/lab/workspace   # 401 without a sign-in
```

Then sign in through the app (magic link) and run **one** Fusion run by names. This costs model calls; only the
owner starts it.

## 5. Host comparison

Every claim has a source. Direct page fetches from this session were blocked (render.com, railway.com, fly.io and
modal.com are outside the session's network allow-list); the claims below come from web-search results. A claim
backed only by a community thread or a third-party site is marked **(third-party)**; one I could not confirm at all
is **UNVERIFIED**. Check the official pricing page before paying.

| | Render | Railway | Fly.io | Modal |
|---|---|---|---|---|
| **Fit: one long process** | yes (web service) | yes (service) | yes (Machine) | yes, with `min_containers=1, max_containers=1` (D-016, `backend/app/modal_app.py`) |
| **Fit: 15-min SSE** | HTTP request timeout 100 min **(third-party: forum staff reply)** [r3] | platform HTTP timeout 15 min, not configurable **(third-party: staff replies)**; some users report 5-min cutoffs [y1] | UNVERIFIED (no timeout found in search) | web endpoints cap a request at **150 s** (official docs) [m2]; our stream would reconnect via Last-Event-ID about every 150 s, UNVERIFIED whether a streaming response is cut or redirected |
| **Free tier** | 750 free instance hours per workspace per month; free web services spin down after 15 min with no inbound traffic and take up to a minute to wake [r1] | trial with $5 credit **(third-party)** [y2] | no free allowance for new orgs, only a short trial; legacy free VMs only for old orgs **(third-party + Fly docs mirror)** [f1] | Starter plan $0 with $30/month compute credits [m1] |
| **Paid cost (small box)** | Starter $7/month, 512 MB, 0.5 CPU **(third-party)** [y2] | Hobby $5/month including $5 usage **(third-party)** [y2] | shared-cpu-1x 1 GB about $5.70 to $6.70/month always-on **(third-party; RAM price rise not confirmed)** [f1] | per second: memory $0.00000222/GiB/s, CPU about $0.0000131/core/s **(sources differ)** [m1]; 1 always-warm small container is roughly a few dollars to tens per month, UNVERIFIED |
| **Setup** | connect GitHub repo; build: install + vite build; start: the uvicorn command; set secrets | same (Nixpacks/Dockerfile); set `PORT` start command | `fly launch` with a Dockerfile; `auto_stop_machines` off for the demo | `modal deploy backend/app/modal_app.py`; secret `chimera-lab` |
| **Risk** | free tier sleeps after 15 idle min and its disk is ephemeral [r1]: an idle demo wakes in ~1 min; use Supabase; a run in progress keeps traffic flowing only while a client streams | 15-min HTTP cap equals our hard cap; reconnect covers it; 5-min reports [y1] | no free tier; must disable auto-stop or a run can be killed when idle | 150 s request cap [m2]; CORS-free single origin still fine; the app needs no Modal feature, but `min_containers=1` costs credits all month |

**Recommendation (for the lead):** Render Starter (or the free tier with a warm-up ping before judging) or Railway
Hobby are the simplest fits for one always-on uvicorn process with long SSE; Modal works today but its 150 s request
cap makes the live trace reconnect repeatedly. Fly.io fits technically but has no free tier. Whatever the host:
one instance, one worker, Supabase for persistence.

Sources:
- [r1] Render, Deploy for Free: https://render.com/docs/free
- [r3] Render community, "Need to increase Requests Timeout of 5 minutes": https://community.render.com/t/need-to-increase-requests-timeout-of-5-minutes/4001 and "Using free plan doesn't respond for some APIs": https://community.render.com/t/using-free-plan-doesnt-respond-for-some-apis/11441
- [y1] Railway Station, "Can the 900-second HTTP request timeout be raised for a streaming service?": https://station.railway.com/questions/can-the-900-second-http-request-timeout-ff86a21d and "Increase Max HTTP Timeout Beyond 5 Minutes": https://station.railway.com/feedback/increase-max-platform-timeout-beyond-5-m-9d15d4ee
- [y2] CostBench, Render vs Railway pricing (third-party): https://costbench.com/compare/railway-vs-render/
- [f1] Fly.io Resource Pricing: https://fly.io/docs/about/pricing/ ; Fly community "Can I use fly for free for very small projects?": https://community.fly.io/t/can-i-use-fly-for-free-for-very-small-projects/23321 ; third-party 2026 price note: https://www.buildmvpfast.com/blog/fly-io-pricing-2026-ram-increase-vs-hetzner
- [m1] Modal pricing: https://modal.com/pricing ; usagepricing.com Modal calculator (third-party): https://usagepricing.com/tools/pricing-calculator/modal
- [m2] Modal, Request timeouts: https://modal.com/docs/guide/webhook-timeouts
