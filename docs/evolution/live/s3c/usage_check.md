# S3c usage check (step 5)

**The 540 Spark Open calls are the project's running total, not one creature's.** 540 is the `spark_baseten`
counter in `docs/live/budget.json` at commit 9b80010. That counter is shared across every live run since S1. It
stood at 507 before S3c (commit 91bbde3). The smoke creature's own count can't be read off cleanly, because the
smoke runs and agent r1 logged under the same step label (`s3c:agent:beetle_bear:1`).

**No creature went over the 30-tool-call cap.** Tool calls per creature, from each trace.md, against Spark Open API
calls from docs/LIVE_LOG.md by step:

| run | tool calls | evo_agent API calls | all Spark Open calls |
|---|---|---|---|
| beetle_bear smoke_r1 | 19 | (shared label, see below) | (shared label) |
| beetle_bear r1 (v1) | 12 | 29 with smoke_r1 and a pre-fix smoke | 55 with smoke_r1 and a pre-fix smoke |
| beetle_bear r2 (v1) | 19 | 18 | 35 |
| crab_wolf r1 (v1) | 14 | 13 | 27 |
| crab_wolf r2 (v1) | 22 | 21 | 38 |
| fox_owl r1 (v1) | 14 | 14 | 26 |
| fox_owl r2 (v1) | 16 | 15 | 27 |
| tortoise_goat r1 (v1) | 17 | 16 | 29 |
| tortoise_goat r2 (v1) | 15 | 15 | 28 |

Why the Spark Open count is higher than the tool-call count:

- Only `evo_agent` calls are the agent's own turns, about one per tool call.
- Every `inspect` also runs the plan-blind critics: Spark Open answers `evo_describe`, `evo_ask` and
  `evo_checklist`, and Meta Spark answers in parallel.
- Every single-pass render also makes one `evo_polish` call.
- `finalize` runs the judge (`evo_critic`).

Those are costs of the tools, not agent calls, and the 30-call cap counts tool calls by design. A creature's Spark
Open total therefore runs about 1.5 to 2 times its tool calls.

Nothing broke through the cap, so there was no cap fix and no new cap test. The existing test
`test_the_render_cap_and_code_finalize_with_remaining_failures` already drives a brain to exactly 30 calls and checks
the stop.

One fix did come out of this check, in step 3: the run step label now includes the repeat folder
(`s3c:agent:<pair>:<r1|smoke_r1>`), so a smoke run and r1 are counted apart.
