# Chimera Lab

Fuse two animals into one science-grounded creature. Drop two animal photos onto a node canvas, press **Fuse**, and Chimera Lab:

1. identifies both animals
2. matches them against curated field data
3. checks for documented real hybrids
4. runs anatomy rules
5. plans which parent donates each body part
6. generates a single creature image

Every result shows how it was made, and every generated image is labelled as a generated fusion.

Beyond the core flow:

- **Anatomy controls:** pin any body part (head, body, limbs, covering, tail) to parent A or B, or leave it on Auto for the model.
- **Field cards:** turn a Result into a field-guide specimen card (invented binomial, habitat, diet, the parents' recorded size ranges, provenance) and download it as a PNG.

- **Frontend:** React 18, TypeScript, Vite, React Flow (`@xyflow/react`), Zustand. One stylesheet: `frontend/src/styles/theme.css`.
- **Backend:** Python, FastAPI (`backend/app/main.py:create_app`). It runs locally with uvicorn and on Modal (`backend/app/modal_app.py`).
- **Models:** Meta Model API (Muse Spark for vision and planning, Muse Image for generation), behind adapters.
- **Storage/DB:** Supabase in real mode; local files plus SQLite in dev.

See `docs/ARCHITECTURE.md` for the design, `docs/DESIGN.md` for the visual system, and `TASKSHEET.md` for the build plan and status.

## Quick start (mock mode, no keys needed)

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
```

```bash
cd frontend && npm install && cd ..
```

```bash
scripts/dev.sh
```

`dev.sh` starts the backend on <http://localhost:8000> (mock mode) and the frontend on <http://localhost:5173>. In mock mode no model is called. Identification is deterministic, and the image generator paints a composite plate from your two inputs. Try the fixture photos in `backend/tests/fixtures/images/` (`lion.jpg` + `tiger.jpg` shows a documented real hybrid; `common_octopus.jpg` + `scarlet_macaw.jpg` shows rule warnings).

The field data lives in `data/chimera_data.json` (placed by hand, gitignored). Without it, the backend falls back to `backend/tests/fixtures/chimera_data.sample.json`, and `/health` reports `dataSource: "sample"`.

## Tests

| Command | What |
|---|---|
| `.venv/bin/python -m pytest backend` | backend unit and integration tests: full fusion in mock mode, every fault, assets, spend guard |
| `cd frontend && npm test` | Vitest unit and component tests (state matrix, edge rules, migration, contrast) |
| `cd frontend && npm run e2e` | Playwright: happy path, every fault, offline, reload mid-run, broken graphs, axe, keyboard-only flow, layout, visual baselines. Starts its own servers. |
| `cd frontend && npm run shots -- --round name` | screenshot matrix into `docs/visual-qa/<round>/` (see `docs/visual-qa/INDEX.md`) |
| `scripts/check-css.sh` | single CSS file, no inline styles, no raw hex outside tokens |
| `scripts/check-bundle.sh` | production bundle contains no secrets or test hooks |
| `scripts/gen_types.sh` | regenerate `frontend/src/types/api.ts` from the Pydantic models |

## Environment variables

| Var | Default | Notes |
|---|---|---|
| `CHIMERA_MODE` | `mock` | `real` uses the Meta adapters (needs `META_API_KEY`) |
| `META_API_BASE_URL` | `https://api.meta.ai/v1` | |
| `META_API_KEY` | none | backend only, never in the frontend |
| `META_VISION_MODEL` / `META_IMAGE_MODEL` | placeholders | set during P7 |
| `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` | none | if both are set, Supabase storage and DB replace the local adapters |
| `STORAGE_BUCKET` | `chimera-assets` | |
| `DATA_PATH` | `data/chimera_data.json` | relative to the repo root |
| `MAX_GENERATIONS_PER_RUN` | `2` | spend guard; every attempt counts |
| `MAX_VISION_CALLS_PER_RUN` | `4` | 2 identify + 1 plan + 1 spare retry |
| `DAILY_GENERATION_CAP` | `200` | global counter; blocks runs with `BUDGET_EXCEEDED` |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated allowlist |
| `RUN_LEASE_SECONDS` | `180` | silent runs become `interrupted` |
| `MOCK_DELAY_SCALE` | `1` | mock latency multiplier (tests use 0 to 0.1) |
| `VITE_API_BASE_URL` | `http://localhost:8000` | frontend build-time |

## Mock vs real, and switching adapters

Adapters are chosen in exactly one place, `backend/app/services.py:build_services`:

- `CHIMERA_MODE=mock`: `MockVision`, `MockImageGen`. These honour the `X-Mock-Fault` header (`timeout`, `rate_limit`, `server_error`, `refusal`, `not_animal`, `human`, `corrupt_output`, `slow`, `crash_mid_run`, `budget`), and only in mock mode.
- `CHIMERA_MODE=real`: `MetaVision`, `MetaImageGen` (`backend/app/adapters/meta/client.py`). Request builders and response parsers are small pure functions at the top of that file, so they can be corrected quickly once live responses are visible. **They have not been verified against the live API** (P7-02).
- Supabase credentials present: `SupabaseStorage` and `SupabaseDb`. Otherwise `LocalStorage` and `SqliteDb` under `.localdata/`.

## Deploy to Modal (P7)

1. Create the Supabase tables and bucket: run `backend/app/adapters/supabase/schema.sql` in the SQL editor.
2. Create a Modal secret named `chimera-lab` with `CHIMERA_MODE=real`, `META_API_KEY`, `META_VISION_MODEL`, `META_IMAGE_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` and `CORS_ORIGINS=<your frontend origin>`.
3. Put `data/chimera_data.json` in place (it is baked into the image).
4. Deploy:

   ```bash
   modal deploy backend/app/modal_app.py
   ```

5. Build the frontend against the Modal URL and host `frontend/dist`:

   ```bash
   cd frontend && VITE_API_BASE_URL=https://<your-modal-app>.modal.run npm run build
   ```

## Repository map

```
backend/app/        FastAPI app, adapters (mock / local / meta / supabase), pipeline steps, data loader, models
frontend/src/       canvas, node registry + nodes, graph (schema, migrate, undo), runs, api, connectivity, persistence, ui
docs/               ARCHITECTURE, DESIGN, UI_STANDARD, DECISIONS, BUILD_LOG, TEST_REPORT, visual-qa/, rounds/
scripts/            dev.sh, gen_types.sh, check-css.sh, check-bundle.sh, fixture + contact-sheet tools
```
