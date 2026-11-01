# Chimera Lab

**Give Chimera Lab two animals (a photo or a name for each) and a design mode; an agent returns one generated
creature with a card that says how it was built, which parent each part came from and what still looks wrong. It is
for creature designers in games, film and tabletop, and for people learning biology by designing.**

Every creature is generated. The app labels each one "Generated fusion" and never presents it as a real animal.
Documented real hybrids (a mule, a liger) are labelled separately.

**Status (Nov 1, commit `990703e`):** the engine and the agent are built and benchmarked live (S5). The
gallery-first UI, the run API with its live trace, and hosting are being built in round R1 (`docs/api_contract.md`).
The "What you get" list below describes the R1 target.

- What was built during the hackathon, and what came from outside: `docs/submission/BUILT_DURING_HACKATHON.md`
- Architecture diagrams: `docs/submission/ARCHITECTURE.md`
- The benchmark behind the numbers below: `docs/evolution/S5_BENCHMARK.md`

## What you get

- **A gallery first.** Finished creatures, with six showcase creatures from the benchmark run first (D-096). The six
  are proposed and wait for the owner's ratings (D-095).
- **A live trace.** Every agent step appears as it happens: the tool, its arguments, the agent's reason and the
  rule cards it cited. A run takes about 5 minutes; you can leave and come back to it (D-096).
- **A creature card:**
  - the creature's label (below) and its design mode;
  - the host, the parent that sets the body frame, and why the agent chose it;
  - "Can it live?": six body functions checked against the plan, with any declared rule-bends and what compensates
    for them;
  - the critic failures the final image still has, stated, not hidden;
  - an anatomy map: each part SAM 3.1 finds, colored by the parent it came from (host blue, donor orange, a blend
    purple), and every part it could not find listed as "not located".

## Who it helps

- **Creature designers** (games, film, tabletop): a fast, reasoned starting design, with a stated reason for each
  anatomy choice and a plain list of what does not work yet.
- **People learning biology by designing:** the agent's choices cite rule cards built from research on real
  hybrids, lab chimeras, body-plan limits and perception (`docs/evolution/research/`), so a learner can see why a
  wing replaces a foreleg in a vertebrate or why a large insect needs a label.

No user testing has been done. These are the intended users, not measured ones.

## The three creature labels

Code sets the label from taxonomy and the data, never the model (RC-R9-01, `backend/app/evolution/route.py`):

| Label | When | Example from the benchmark |
|---|---|---|
| **real hybrid** ("real hybrid precedent") | the pair is a documented cross in the data | b05 donkey × horse, a mule |
| **speculative chimera** ("speculative chimera, no real-world precedent") | any other pair, in realistic or speculative mode | b09 Indian pangolin × horse |
| **mythic composite** | mythic mode; may bend up to 3 declared rules | b03 lion × golden eagle |

A fourth label, "speculative hybrid of close relatives, no documented cross", covers close relatives with no
recorded cross (D-055).

## How the agent works

The agent is **Muse Spark Open on Baseten**, running a tool loop over the engine
(`backend/app/evolution/agent.py`). It decides; code supplies the tools and enforces the rules.

1. **Resolve** both parents: the dataset, then a learned cache, then the open world (GBIF exact species match, and
   traits from Muse Spark 1.3 web search with citations that code checks against the fetched page; D-068, D-074).
2. **Propose:** code returns candidate plans, one per possible host, each with notes on niche, autonomy, survival
   and identity. They are advice; the agent chooses (D-089).
3. **Choose and edit the plan** with typed operations only (12 of them, such as `set_host`, `set_extent`,
   `set_covering_material_only`). The agent never writes plan JSON. Each call is checked against its own schema
   before it runs; in the benchmark run no call was refused (D-094).
4. **Audit:** physical checks, a six-function audit and the hard rule cards. A plan with a blocking item cannot be
   rendered.
5. **Render** with Muse Image 1.0. The prompt is compiled by code from the structured plan only (D-066).
6. **Inspect** with two critics that never see the plan (D-072): each describes the image and counts heads, legs and
   tails, then answers a balanced checklist. Muse Spark 1.3 decides; Spark Open's answers are kept as information
   (D-084). SAM 3.1 confirms that planned parts are present.
7. **Edit or re-plan:** a covering or surface failure gets one plan-worded Muse Image edit; a structural failure
   needs a plan change and a new render. **The two-failure rule:** after two inspects in a row with covering
   failures, covering edits are locked until the plan changes (D-091).
8. **Finalize** the best inspected image. If the agent picks an image the code ranks lower, it must say why, and
   the card shows both picks (D-093).

Guardrails in code: audit before render, a host tie must be chosen, a reason on every call, and runaway caps of 4
renders, 30 tool calls and 6 edits per creature (`data/evo_config.json`, `agent`). The rule cards (126, 18 hard)
come from ten research docs, `data/rule_cards.json`.

## Models

| Model | Where | What it does here |
|---|---|---|
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`) | Baseten, OpenAI-compatible API | The agent brain (tool calling); one of the two critics; identify, checklist and prompt polish (`data/evo_config.json`, `routing`) |
| **Muse Spark 1.3** | Meta Model API | Plans for the fixed pipeline, web-cited traits, the function audit, and the deciding critic |
| **Muse Image 1.0** | Meta Model API, Responses API | Renders, and edit turns on the same image (`previous_response_id`) |
| **SAM 3.1** | Meta Model API | Text-prompted part segmentation: presence checks during inspect, and the anatomy map |

Calls in the 22-creature benchmark run: Spark Open 362, Muse Spark 1.3 110, Muse Image 49 images, SAM 3.1 179
(`docs/evolution/S5_BENCHMARK.md`). Money cost per run was not measured.

## The benchmark, stated honestly

An 11-case benchmark (`data/evo_benchmark.json`, frozen; a test checks its hash) was run once with the agent and
once with the fixed pipeline, live, 22 creatures, no reruns. Scores are computed in code from the saved results
(`docs/evolution/live/s5/scores.json`).

| | agent | fixed pipeline |
|---|---|---|
| full matches (no failing critic item) | 5 of 11 | 6 of 11 |
| average critic failures | 1.82 | 1.91 |
| structural / integration failures (average) | 0.55 / 1.27 | 0.91 / 1.0 |
| both parents named by the deciding critic | 7 of 11 | 5 of 11 |
| calls per creature | 39.3 | 24.4 |
| wall time per creature | 295 s | 233 s |

- **Overall the two are about even.** The agent does not beat the pipeline on the critics' scores.
- **The agent wins host ties.** In 7 of 11 cases neither parent is structurally better as host, and the pipeline
  has no rule, so it falls back to the first-named parent. The agent chose the horse for pangolin × horse and the
  goat for tortoise × goat, with reasons, and in those two cases its images named both parents where the pipeline's did not.
- **It loses when it re-rolls on a critic misread.** Octopus × horse spent all 4 renders on mottled skin the critic
  read as a toad.
- The owner has not yet rated the images (`docs/evolution/benchmark/s5_review.html`). The critic scores are the
  only measurement so far.

## Known limits

- **Hard plates and shells over fur look worn, not grown.** Seen from S2 to S5. In b02 (beetle × bear) the prompt
  says the plates grow from the skin, and both systems still drew armor (7 integration failures each). Scales over
  skin or hide work (b01, b09).
- **A run takes about 5 minutes** (295 s on average in S5, 141 s to 474 s). You can leave and resume.
- **Daily caps:** 50 live runs per day in total and 3 per visitor, by default (D-096). The gallery stays open when
  they are used up.
- **The image model sometimes ignores a correct prompt.** The same compiled prompt gives different bodies: in b08
  (fox × owl) the first render had one failure and the second, from the identical compiled prompt, had extra legs.
  In b06 four renders of one unchanged plan all failed. In b01 a re-render of the same plan fixed a failure.
- **The critics misread a donor's own pattern** (owl or cheetah spots called extra spots) or a texture (called a
  third animal).
- **The material-only critic checks are not calibrated.** They failed in all 4 uses, so the card hides them until
  the owner has labelled examples (D-096).
- **The anatomy map rarely finds the torso (3 of 22) or a covering (5 of 20),** and it colors by the plan's parent,
  not by what is drawn.

## Run it

### Mock mode (no keys, no paid calls)

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd frontend && npm install && cd ..
scripts/dev.sh
```

`scripts/dev.sh` starts the backend on <http://localhost:8000> in mock mode and the frontend dev server on
<http://localhost:5173>. In mock mode no model is called: the agent is driven by a scripted policy brain
(`PolicyBrain` in `agent.py`) and the models are deterministic mocks.

R1 (in progress at the time of writing) adds the agent endpoints under `/evo/agent/...` and serves the built
frontend from the same app at `/` (`docs/api_contract.md`). In mock mode the header `X-Mock-Scenario` picks a
scenario (success, host tie, cap, error, queued, refused upload).

### Live mode

Set these in `.env` (see `.env.example`); keys stay on the backend:

| Variable | What |
|---|---|
| `CHIMERA_MODE=real` | use the live adapters |
| `META_API_KEY` | Meta Model API: Muse Spark 1.3, Muse Image 1.0, SAM 3.1 |
| `BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26` | Baseten: Muse Spark Open, the agent |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | optional: Postgres and Storage instead of local files and SQLite |
| `EVO_DAILY_RUNS`, `EVO_VISITOR_DAILY_RUNS` | public caps, defaults 50 and 3 (R1, `docs/api_contract.md`) |
| `CHIMERA_LIVE_BUDGET_FILE` and `CHIMERA_LIVE_MAX_*` | optional hard cap on live calls across processes |

The benchmark runner spends real calls, one creature per invocation, and resumes from disk:

```bash
.venv/bin/python scripts/s5_live.py run --max 1
.venv/bin/python scripts/s5_live.py score
```

### Tests

| Command | What |
|---|---|
| `.venv/bin/python -m pytest backend` | backend, all in mock mode (956 passed, 6 live tests skipped, at S5) |
| `cd frontend && npm test` | frontend unit and component tests |
| `cd frontend && npm run e2e` | Playwright end-to-end tests |

## Repository map

```
backend/app/evolution/   the engine and the agent (agent.py, inspect.py, critic.py, anatomy.py, benchmark.py)
backend/app/adapters/    Meta, Baseten, Supabase and mock adapters
data/                    dataset, rule cards, engine config, the frozen benchmark
docs/evolution/          research, algorithm, step reports, live outputs (live/s5/ is the benchmark run)
docs/submission/         submission documents
frontend/src/            the UI
scripts/                 dev server, live runners, review sheets, checks
```

The v1 fusion app (`main` branch, node canvas) is still in the history and its backend endpoints still exist, but
it is no longer in the UI (D-096).
