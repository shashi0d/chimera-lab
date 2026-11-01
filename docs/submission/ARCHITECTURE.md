# Chimera Lab architecture

Two diagrams: the system as R1 builds it, and the agent loop. The engine and the agent loop exist and were run live
in S3c and S5. The browser UI, the agent API, the job runner and the event store are the R1 target described in
`docs/api_contract.md`; they were not merged at the time of writing (Nov 1, commit `990703e`). Hosting is not
decided (D-096), so the diagram shows one FastAPI app without a host.

## 1. System

```mermaid
flowchart TB
  subgraph browser["Browser UI"]
    gallery["Gallery, the first screen"]
    canvas["Canvas: two parents, photo or name, and a mode"]
    trace["Live trace and creature card"]
  end

  subgraph app["One FastAPI app, uvicorn"]
    static["Built frontend served at /"]
    api["Agent API under /evo"]
    runner["Agent job runner: queue, per-run and daily caps"]
    events["SSE event store: numbered events, replay after Last-Event-ID"]
  end

  subgraph engine["Engine tools, backend/app/evolution"]
    resolve["resolve_animal: dataset, learned cache, GBIF, cited traits"]
    plan["propose_candidates and typed plan operations"]
    audit["audit_plan: rule cards, function audit, fiction budget"]
    render["render and edit"]
    inspect["inspect: two plan-blind critics plus SAM presence"]
    finalize["finalize: card and anatomy map"]
  end

  subgraph providers["Model providers"]
    baseten["Baseten: Muse Spark Open, the agent and one critic"]
    spark["Meta API: Muse Spark 1.3, plans, cited traits, audit, deciding critic"]
    image["Meta API: Muse Image 1.0, renders and edits"]
    sam["Meta API: SAM 3.1, part masks"]
    gbif["GBIF API: exact species match"]
  end

  subgraph storage["Storage: Supabase, or local in dev"]
    pg["Postgres: runs, events, creatures"]
    bucket["Storage: images"]
  end

  gallery --> api
  canvas --> api
  trace -->|SSE| events
  static -->|serves| gallery
  api --> runner
  runner --> resolve
  runner --> events
  resolve --> plan --> audit --> render --> inspect --> finalize
  runner -.->|tool calls| baseten
  resolve --> gbif
  resolve --> spark
  audit --> spark
  render --> image
  inspect --> baseten
  inspect --> spark
  inspect --> sam
  finalize --> sam
  events --> pg
  finalize --> pg
  render --> bucket
```

What each part does, with its source:

| Part | What it does | Source |
|---|---|---|
| Browser UI | Gallery first; a run can be left and resumed; the trace shows every step | D-096, `docs/api_contract.md` |
| Agent API | `POST /evo/agent/runs`, run snapshot, SSE events, host-tie choice, limits, creatures, gallery | `docs/api_contract.md` |
| Job runner | Queues runs beyond 3 concurrent; refuses past 50 runs a day or 3 per visitor; finalizes the best image at 14 minutes, stops at 15 | `docs/api_contract.md`, "Caps" |
| Event store | Numbered events per run with no gaps, stored with the run, so a reconnect replays exactly | `docs/api_contract.md`, "Server-sent event schema" |
| Engine tools | The agent's tools, with guardrails in code | `backend/app/evolution/agent.py`, D-089 |
| Routing | Which provider serves each call type; a failed Baseten call falls back to Meta and is logged | `data/evo_config.json` `routing`, D-069 |
| Storage | Supabase when its credentials are set, else SQLite and local files. Supabase was not verified live | `backend/app/services.py`, v1 README |

Uploaded photos are identified, then discarded; only the names reach the job (`docs/api_contract.md`).

## 2. The agent loop

Muse Spark Open picks every step and gives a reason. The diamonds are checks code enforces.

```mermaid
flowchart TD
  start["Run starts: sire, dam, mode"] --> res["resolve_animal for each parent"]
  res --> prop["propose_candidates: one plan per host option, with notes"]
  prop --> tie{"Structural host tie?"}
  tie -->|yes| pick["choose_candidate with a stated reason, or ask_user"]
  tie -->|no| choose["choose_candidate"]
  pick --> ops["Typed plan operations, each checked against its schema"]
  choose --> ops
  ops --> aud{"audit_plan: any blocking item?"}
  aud -->|yes, fix the plan| ops
  aud -->|no| ren["render with Muse Image"]
  ren --> ins["inspect: describe and count, balanced checklist, two critics, SAM"]
  ins --> ok{"Failures left?"}
  ok -->|none| fin["finalize the best inspected image"]
  ok -->|structural| struct["Change the plan, or render the same plan again"]
  struct --> aud
  ok -->|covering or surface| two{"Two inspects in a row with covering failures?"}
  two -->|no| edit["edit: one plan-worded Muse Image edit"]
  edit --> ins
  two -->|yes, covering edits locked| rule["Change the plan: set_extent or set_covering_material_only"]
  rule --> aud
  ok -->|accept and stop| fin
  cap["Cap reached: 4 renders or 30 tool calls"] -.->|code finalizes| fin
  fin --> card["Card: label, host reason, Can it live, remaining failures, anatomy map"]
```

Notes on the loop, each from the code or a decision:

- **The agent never writes a plan.** It adopts a candidate and applies typed operations. Code fills every derived
  field (D-067, D-089).
- **Audit before render** is checked by content: a plan changed after its audit must be audited again (D-089).
- **Structural failures cannot be edited away.** `edit` refuses them with `structural_failure`; they need a plan
  change and a new render (D-089).
- **Drift check:** after any edit, inspect compares the critics' head, leg and tail counts with the image before
  the edit and adds a `host_drift` failure if they changed (D-089).
- **The two-failure rule** locks covering edits on that plan's content; a plan change or a clean inspect resets it
  (D-091). Its second route, `set_covering_material_only`, keeps the host's own covering and takes only the donor's
  color, gloss, texture and pattern (D-092).
- **Finalize:** code ranks images by fewest structural failures, then fewest failures, then the latest. Choosing a
  lower-ranked image needs `why_not_best` (D-093).
- **Resumable:** images are kept on disk and runs are saved after every tool step (D-090).

## 3. The fixed pipeline, for comparison

`engine.fuse` (the S5 baseline) runs the same engine without the agent: Muse Spark 1.3 writes the plan, code audits
and compiles it, Muse Image renders once, inspect runs the same critics, and at most one edit turn follows. On a
structural host tie it has no rule and uses the first-named parent (D-085, `docs/evolution/S5_BENCHMARK.md`).
