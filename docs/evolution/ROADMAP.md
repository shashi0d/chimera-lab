# Chimera Lab roadmap: audit, platform map and the next 10 steps

Doc: docs/evolution/ROADMAP.md
Written: Nov 1, 2026. Submission deadline: Nov 4, 9 PM Eastern.
Read this before every step. Each step's prompt refers to its section here.

## 1. Principles (from the project's own decisions)

1. Models drive the decisions. Rules, data and code are guardrails, tools and sources for the agent, not a deterministic engine that restricts it.
2. Quality over cost. Budgets exist to be used. Caps are runaway guards (about 3x a step's planned use), never quality limits. Good engineering keeps cost sane on its own: cache what repeats, use the right model per job, measure before changing defaults.
3. Every claim traces to a source, and every model-estimated fact is marked.
4. Verify, don't trust: every model output that matters is checked by an independent signal (rule cards, SAM, a separate critic context, a human sheet).
5. Ship a working, impressive demo. Demo is 25 percent of the score and is the biggest current risk.

## 2. Audit findings

Direction
- A1. Drift from principle 1: code makes nearly every decision (route, host, traits, repairs) and the model's plan is often rejected. The engine is a workflow with model calls, not an agent.
- A2. Cost framing shaped decisions (trimmed calls, tight caps, dropping critics). Wrong lens; reversed.
- A3. The redesigned UI (main) and the engine (evo) are not connected. No demo flow exists.
- A4. Photo input, needs_choice, compare mode and evolve have never run live.

Quality
- Q1. Rendering is text only. Muse Image supports up to 10 reference images, precise edits and series consistency, none of which we use.
- Q2. Structural failures are detected but nothing acts on them. An edit turn could fix one part without re-rolling the creature.
- Q3. The critic is the same model family grading a plan it wrote, and it sees the plan. Independent part-level checks are missing; SAM 3.1 can provide them.
- Q4. Model plan notes can leak into the image prompt. Prompts must be compiled only from the structured plan.
- Q5. Model-estimated traits are never checked against a source. Spark's built-in web search with citations can ground them.
- Q6. The forced-choice question adds nothing ("a mix of both" every time). Drop it.
- Q7. No benchmark exists, so improvements are judgments, not measurements.

Product
- P1. Impact (30 percent) needs a clear user: people learning biology through design, and creature designers for games, film and tabletop.
- P2. Prize fit: Indie track; Best Build on Meta Open Weight Models (Muse Spark Open via Baseten); Best Agentic Use-Case; Best Creative Build (Muse Image); Most Viral; Community Vote.

## 3. Platform map: what each platform offers and what we use

Status: V = verified in docs or our own live runs; U = unverified, to be probed.

### Meta Model API (api.meta.ai/v1)

| Feature | Use in Chimera Lab | Status |
|---|---|---|
| Muse Spark 1.3: Responses, Chat Completions, Messages formats; tools; structured output; prompt caching | Fallback brain; tasks needing built-in web search | V |
| Spark web_search tool with inline citations | Trait enrichment for unknown animals, with cited provenance instead of "model-estimated" | V (docs), U (our use) |
| Responses state via previous_response_id; background jobs with polling, streaming and cancel | Multi-turn image edits; long jobs without blocking | V (docs and our direct experiment) |
| Muse Image 1.0: text-to-image, up to 10 reference images, precise local edits, multi-reference composition, @ImageN prompt references, series consistency with shared references, web and image search grounding | Parent reference portraits; targeted edit fixes; consistent variants; compare views | V (docs), U (our use) |
| SAM 3.1: text-prompted detection and segmentation in one call | Part-level verification ("wings", "gills"); a donor-colored anatomy map in the UI | V (silhouette live), U (parts) |
| Muse Wonder 1.0: frontier agent model, tools, long tasks, sub-agents | Optional A/B against Spark Open as the agent brain; candidate for an "expert creature request" mode | V (docs), U (our use) |
| Muse Voice Transcribe: streaming speech to text over WebSocket, or recorded audio | Voice input for goal mode in the app | V (docs), U (our use) |

### Baseten (inference.baseten.co/v1)

| Feature | Use | Status |
|---|---|---|
| Muse Spark Open Model API: OpenAI compatible, tool calling, reasoning output, 1M context, image input | Primary agent brain and all text and vision reasoning calls; qualifies for the open-weight prize | V (docs), U (exact model name and our key) |
| Dedicated deployments, async inference | Not needed now | Not used |

Note: one public project reports Baseten listing the model as meta-models/muse-spark-open without "-1026". Our key is for "-1026". Use it exactly and report if it fails.

### Modal

| Feature | Use | Status |
|---|---|---|
| asgi_app FastAPI with StreamingResponse (SSE) | Serve the engine API and stream the agent trace live to the UI | V (docs) |
| spawn for background calls | Run each agent job in the background and stream progress | V (docs) |
| Secrets | Meta and Baseten keys | V |
| Volume | Learned animals, reference portrait cache, benchmark outputs | V (docs) |
| Dict | Run state and short-lived caches | V (docs) |
| Schedule | Optional nightly benchmark | V (docs), optional |
| GPUs | Could self-host Muse Glimmer (30B, Apache 2.0); not needed | Not used |

### Supabase

| Feature | Use | Status |
|---|---|---|
| Postgres and Storage | Saved creatures, images, public gallery for the community vote | V (already in the stack) |
| Realtime | Alternative to SSE for pushing trace events | Optional |

### Not used, with reasons

- Muse Glimmer: Spark Open covers the open-weight prize and is stronger. Self-hosting adds risk with no quality gain in this window.
- Spark's own image_generation tool: failed three times in our direct experiment. Keep Muse Image as a separate tool.

## 4. Target architecture

The agent: Muse Spark Open on Baseten, running a tool loop with a visible trace.

Tools (existing code becomes tools):
- resolve_animal: database, learned cache, GBIF exact match, Spark web search for cited traits.
- propose_candidates: plan-level search (R10 selection: niche, autonomy, survival, identity), returning ranked arrangements with reasons. It advises; it does not decide.
- audit_plan: physical checks, R9 function audit, fiction budget, hard cards. Hard-card failures are blocking errors the agent must fix; soft cards come back as advice.
- make_reference_portraits: one cached portrait per parent (text-generated, so there are no license issues).
- render: Muse Image with the compiled prompt and the parent references.
- inspect: SAM part checks plus a checklist critic that sees only the image and checklist, never the plan.
- edit: a targeted Muse Image edit turn for a failed part.
- ask_user: needs_choice for unclear names, near-tie hosts and goal mode choices.
- finalize: build the card (Can it live, licenses, provenance, host reasoning, anatomy map).

Guardrails: hard cards gate tool outputs; runaway caps per run; every decision is logged with its reason and the cards behind it.

Modes: realistic, speculative, mythic, compare; plus goal mode (the user states abilities and habitat, the agent proposes parent pairs).

## 5. The 10 steps

| # | Step | Deliverable | Done when |
|---|---|---|---|
| 1 | Capability probe | S1_CAPABILITIES.md | Each capability has a use / don't use / needs work verdict |
| 2 | Fix pack and agent prep | E4c fixes; prompt compiled only from the structured plan; forced choice removed; plan schema split into small typed edits; cited web-search traits; routing per call type; inspect (SAM presence plus critic) and one plan-worded edit turn | Tests pass; beetle-bear fixed live; 4 animals have cited traits |
| 3 | Agent core | Spark Open tool loop over the tools above, trace log, guardrails | One live creature built end to end by the agent, with a readable trace |
| 4 | Verification upgrade | SAM part checks, a plan-blind critic, the anatomy map, a human review sheet | Part checks agree with human review on the existing images |
| 5 | Benchmark and A/B | Fixed eval set; A/Bs: references vs none, edit vs re-render, agent vs pipeline, Spark Open vs Wonder as brain | Defaults chosen by measured results |
| 6 | Goal mode and multi-parent | Goal to proposed parent pairs; voice input; 3-parent family trees | A goal request produces 3 sensible pairs and one finished creature |
| 7 | API, streaming, deploy | Modal asgi app with SSE trace, background runs, Volume caches, Supabase persistence | Deployed endpoint streams a live run |
| 8 | Frontend integration | The redesigned graph UI runs the agent: trace panel, card, Can-it-live panel, anatomy map, variants | A full run from the UI, recorded |
| 9 | Hardening and merge | End-to-end live runs, failure handling, owner review, evo merged to main, README, a log of what was built during the hackathon | Owner approves the merge |
| 10 | Demo and launch | Showcase creatures, a 3-minute video, X post, gallery submission with prize flags | Submitted before Nov 4, 9 PM Eastern |

Suggested timing: steps 1 to 3 on Nov 1; 4 to 6 on Nov 2; 7 to 8 on Nov 3; 9 to 10 on Nov 4.

## 5b. Decisions after S1 (Nov 1)

| Finding (S1) | Decision |
|---|---|
| Spark Open tool calling: fully correct across 4 turns, parallel calls, ids passed correctly; no refusals in 8 planning prompts | Spark Open is the agent brain (step 3) |
| Spark Open checklist critic: 15 of 15 answers agree with Meta; polish and resolver match | Checklist, thumbnail critic, polish and identify move to Spark Open |
| Spark Open full plans and trait lists run away (card_trace repeated to the output limit) | The agent never writes a whole plan. It picks among candidates from propose_candidates and makes small typed edits through tools. Code fills card_trace and derived lists. Every Spark Open call gets an output cap. |
| Trait enrichment needs grounding | Meta Spark 1.3 with web_search writes cited traits (step 2). Spark Open does not write traits. |
| Reference portraits gave no anatomy gain, only skin and style | References off by default. Used only for variants (series consistency) and user photos. |
| Edit turns modify the same creature (3.7 percent of pixels changed) but a symptom-worded fix removed a planned part | Structural fixes use one edit turn worded from the plan item ("show the planned chitin plates as plates on the shoulders, not whole beetles"), then re-inspect |
| SAM finds named parts reliably; an empty mask did not prove absence (the beetle bodies) | SAM confirms presence of planned parts. Absence checks stay with the critic. Both feed the inspect tool. |
| S1b scope | Folded into later steps: web-search traits into step 2, anatomy map into step 4, series consistency into step 5, voice into step 6. Dropped: @ImageN multi-reference tests, image-search on/off, a Muse Wonder A/B (Spark Open already orchestrates correctly). |
| S2: the fix pack fixed beetle x bear structurally (four legs, no wings, horn on the brow), but the Spark Open checklist answered yes to every item on both runs, including run 1's whole-beetle plate; plates spread onto the shoulders and legs, and the owner judges them armor pieces sitting on the fur, not grown in the skin | S3a: the critic is the weakest link, so it is rebuilt and calibrated before the agent core trusts it: a plan-blind describe-first critic, count questions, a balanced checklist (half the answers "no"), integration items, two critics (Spark Open and Meta Spark 1.3) with disagreement as "uncertain" (a fail signal), and code matching the free description against the plan. Calibrated on an owner-labeled gold set of 11 existing images. |
| S2: cited traits verify that a URL was opened, not that the quote supports the value; some sources are weak (a store page, a dictionary, a children's encyclopedia) | S3a: source tiers (tier 1 academic, museum, government, ADW; tier 2 zoos, aquariums, major science media; stores, dictionaries, children's encyclopedias and general wikis rejected) and a code fetch that requires the model's quote to appear on the page; anything else falls back to "model-estimated" |
| S3a owner review (`benchmark/s3a_owner_review.md`): beetle-bear has no good variant (the shell is pasted on, keeps the beetle's shape, leaves the legs bare, ignores insect scale; the horn is disconnected; V5 read as a rhinoceros); axolotl-pangolin works in V1 to V5, V2 best, V5 closest to a real hybrid but changed the tail | S3b: transfer traits, not shapes (RC-R10-15). Every donor feature gets a transfer class (material or covering, homologous structure, non-homologous structure), an anchor, connections and identity cues; an exoskeleton is a whole-body system (RC-R10-16). The compiler words coverings by material, extent, host-scaled plates and joints, conforming to the host body; growth by edit is an option for coverings only, with a host-drift check. New plan-blind critic items; recalibration with the owner's notes as labels; held-out pairs validate generality. "Edit the animal, not the image": general fixes only, never patches for the two reviewed images. |
| S3a: integration (donor coverings grown in the skin vs pieces on top) may be a plan, wording or image-model limit | S3a runs a 6-variant prompt experiment (covering replacement, functional analogy, anatomy anchors, material reference, growth by edit) on two pairs with the new critic and an owner rating sheet. The default prompt compiler does not change until the owner's ratings decide. |
| S3b: integration rules generalized to held-out hosts (92% of held-out integration answers pass vs 98% tuned), but donor identity failed: a crab's class-level segmented tail and banded whole-body plating read as a woodlouse or pill bug, a fixed arthropod clause drew breathing openings on a crab, and tortoise x goat put fur over the shell because the tie rule made the tortoise host by name order. Meta Spark alone met the critic target (18/18, 3/15) where the S3a pair rule did not | S3c (owner decisions D1 to D4): Meta decides inspect, Spark Open answers as information; no tie rule (the agent picks a tied host with a reason, or asks the user); the axolotl's external gills are its identity part; each donor gets one identity part chosen from its own diagnostic traits, sourced, anchored by function and listed in the fiction budget (realistic: color, texture and material only). Fiction clauses come from the donor's own traits; plate layout from the donor's own features (bands only when it has them); a covering never changes a part's length or shape; a turtle shell is skeleton (RC-R10-17). Then the agent core (step 3): Spark Open runs the tool loop |

## 6. Deferred until after submission

LAYER operator, evolve carry-over (RC-R10-11), battle and collectible features, Muse Glimmer self-hosting.

## 7. Risks

- Time: the steps are sequential; if a step slips, cut 6 (goal mode) to a minimal version before cutting demo work.
- The exact Baseten model name may fail; fallback is the Meta API Spark, with the open-weight prize at risk.
- Spark Open's extra safety training may refuse some mythic or creature prompts; measured in step 1.
- Image model limits: the agent can detect and edit, but cannot force perfect anatomy. The demo uses real, unedited runs and states this honestly.
