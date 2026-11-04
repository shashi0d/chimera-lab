# S1: capability probe for the new architecture

Branch `evo`, 2026-11-01. Live outputs are in `docs/evolution/live/s1/` (`spark/`, `parity/`, `image/`, `sam/`, each with `results.json` and key-free `raw/` recordings). Script: `scripts/s1_probe.py {spark|parity|image|sam}`.

`docs/evolution/ROADMAP.md` (named in the task as the step 1 reference) is not in the repo on evo or main, so this follows the task text alone. No routing changes here; that is step 3.

## Setup and calls made

- **Spark Open:** `meta-models/muse-spark-open-1026` on Baseten, OpenAI-compatible chat completions at `https://inference.baseten.co/v1`, through the new `BasetenEvoSpark` adapter (the existing EvoSpark interface, builders, parsers, retries, usage records and spend guard). The exact model name resolved; no not-found error.
- **Muse Image and SAM 3.1:** the existing Meta adapters.

| Budget kind | Before S1 | After S1 | Made | Cap (runaway guard) |
|---|---|---|---|---|
| spark_baseten | 0 | 44 | 44 | 300 |
| spark (Meta) | 89 | 97 | 8 (judging the part 4 images) | 120 |
| image | 22 | 26 | 4 | 30 |
| sam | 12 | 21 | 9 | 30 |

What the 44 Baseten attempts were:
- **Aborted first part 2 run: 19.** These were 9 answers, then 9 plan attempts cancelled at the old 60 s timeout, then 1 plan answer.
- **Part 2 rerun: 14.**
- **Parity: 11.** These are 10 replays plus 1 crashed first attempt.
- `docs/LIVE_LOG.md` holds 43 of the 44 attempts. The missing one was most likely the call in flight when the aborted run was stopped: it was counted but never logged.

## Part 2: Spark Open probes

### a) Strict JSON (`response_format: json_schema, strict: true`)

| Call | Latency | finish | JSON valid | Schema valid | Notes |
|---|---|---|---|---|---|
| identify "axolotl" | 2.5 s | stop | yes | yes | *Ambystoma mexicanum*, species, correct |
| learn traits, axolotl (enum-heavy) | 193 s | **length** | no | no | ran to the output limit; in the aborted run the same call returned valid JSON whose `body_plan` was `["quadruped","biped","winged","finned","serpentine","radial","serpentine","quadruped"]` |
| audit feeding + heat, axolotl x pangolin | 8.4 s | stop | yes | yes | sensible, specific pass judgments |

- **Format:** every answer starts with `{` and has no code fences or `<think>` tags. The model reasons in a separate `reasoning_content` field: 2,409 reasoning tokens for the traits call.
- **Schema enforcement:** the provider does enforce the schema, but nothing bounds array length. That is the failure mode, and it repeats below.

### b) Image input (E4 lion x eagle render as a data URL)

| Call | Latency | Result |
|---|---|---|
| identify from photo | 11.5 s | kind **mythic**, "Griffin / Gryphon" (correct and useful: a refusal path for mythic photos) |
| open critic | 11.8 s | animals: eagle, lion; 1 creature; "griffin-like hybrid" |

### c) Tool calling (resolve_animal, run_audit, render; axolotl x pangolin)

| Turn | Latency | Calls |
|---|---|---|
| 1 | 0.9 s | `resolve_animal(axolotl)` and `resolve_animal(pangolin)` **in parallel** |
| 2 | 0.9 s | `run_audit(sire_id=ambystoma_mexicanum, dam_id=manis_pentadactyla, mode=realistic)`: the returned ids, the right mode |
| 3 | 0.9 s | `render(audit_id=audit_7f3a)`: the returned audit id |
| 4 | 1.3 s | "Render complete. Image ID: **img_42c9**" |

- **Checks:** all 8 passed (both resolved, order, ids carried, mode, parallel, valid JSON arguments, final id, no extra calls).
- **Parameter:** `parallel_tool_calls: true` was accepted.

### d) Refusal check (5 real planning prompts, about 8.4k to 9.3k characters each)

| Pair | Mode (route) | Latency | Refusal | finish | Plan |
|---|---|---|---|---|---|
| tiger x lion | speculative (hybrid, tigon) | 60 s | none | length | unreadable (51k chars) |
| lion x goldfish | mythic | 55 s | none | stop | **accepted**, no locked field changed |
| octopus x golden eagle | mythic | 67 s | none | length | unreadable (44k chars) |
| moon jellyfish x lion | speculative (chimera) | 67 s | none | length | unreadable (43k chars) |
| golden retriever x woolly mammoth | realistic (chimera) | 61 s | none | length | unreadable (53k chars) |

- **Refusals:** 0 of 5, and no safety deflections.
- **Runaway output:** in 4 of 5 the answer ran to the 32,768-token output limit.
- **Diagnosis** (from the full text kept in parity): the plan is fine for about 3,000 characters, then the model repeats rule-card ids inside `card_trace` (`"RC-R9-01","RC-R9-02",…`) until the limit. `card_trace` is an unbounded string array that the code rebuilds anyway.

## Part 3: parity with recorded Meta Spark requests (10 replays)

The plan requests were rebuilt from code (the recordings elide long text). Each rebuilt prompt matches the recorded length exactly: 9004, 8815 and 9096 characters. The other 7 are the recorded bodies with only `model` changed; the checklists have the saved images re-attached.

| Case | Meta | Spark Open | Agree |
|---|---|---|---|
| plan b, axolotl x pangolin, realistic | accepted (17.5 s median for Meta plans) | runaway in `card_trace`, 49k chars, 68 s | **no** |
| plan c, lion x eagle, mythic | code skeleton used (model plan rejected or unchanged) | runaway in `card_trace`, 49k chars, 63 s | no |
| plan d, beetle x bear, speculative | code skeleton used | runaway in `card_trace`, 51k chars, 62 s | no |
| polish b | accepted, 1529 chars | accepted, 1530 chars, 10.8 s | yes |
| polish c | accepted, 1277 chars | accepted, 1264 chars, 8.0 s | yes |
| resolver: woolly mammoth | extinct, *Mammuthus primigenius* | same, 2.5 s | yes |
| resolver: pangolin | ambiguous, *Manis pentadactyla* + 4 alternatives | same pick, 3 of 4 alternatives same (*Smutsia gigantea* for *temminckii*), 5.7 s | yes |
| checklist b (4 items) | yes, yes, yes, yes | yes, yes, yes, yes | 4/4 |
| checklist c (5 items) | all yes | all yes | 5/5 |
| checklist d (6 items) | yes, yes, yes, **no**, yes, yes | yes, yes, yes, **no**, yes, yes | 6/6 |

- **Checklist:** 15 of 15 item answers agree. The forced choice, animals listed and creature count are also identical on all 3 images. Items were echoed in order and the JSON is schema-valid. Spark Open also caught d's only "no" (the wings drawn on top of the front legs).
- **Locked fields:** none of the plan answers could be parsed, so there is no locked-field comparison. In part 2, the one plan that finished (lion x goldfish) changed no locked field.

## Part 4: Muse Image (Meta)

| Render | Input | Time | Judge | Notes |
|---|---|---|---|---|
| portrait, axolotl | text only | 21 s | 4/4 checklist yes; SAM "animal" fill 0.22 | clean reference: gills, speckles, plain ground |
| portrait, Chinese pangolin | text only | 24 s | 4/4 yes; fill 0.22, 1 component | clean reference |
| axolotl x pangolin with both portraits as references | E4 compiled prompt + 2 images | 25 s | quality **0.975** (checklist 4/4, thumbnail 3/4) | same score as the text-only re-render (0.975); the references brought the axolotl's speckled pink skin and the engraving style into the patches, no anatomy change; open critic still "pangolin" |
| edit turn on the E4 beetle x bear | `previous_response_id` (a day-old response) + "remove the beetle bodies on the shoulders; keep everything else" | 20 s | quality 0.778 (was 0.845) | **edits the same creature**: 3.7% of pixels changed by more than 32 levels; pose, wings, tail and breathing openings identical; beetle bodies gone |

Why the edit's score dropped: the five beetle bodies were how the image model had drawn the planned "exoskeleton patches on the forequarters and neck". Removing them made that checklist item fail. The edit did exactly what it was told, so a fix instruction has to be phrased against the plan item ("turn the beetle bodies into flat exoskeleton plates"), not against the symptom.

## Part 5: SAM 3.1 part prompts (Meta)

| Image | Prompt | Expected | Objects | Fill | Result |
|---|---|---|---|---|---|
| lion x eagle | wings | present | 2 | 0.164 | **found**: exactly both wings |
| lion x eagle | eagle head | present | 1 | 0.030 | **found**: exactly the head, neck ruff excluded |
| lion x eagle | lion legs | present | 4 | 0.084 | **found**: exactly the four legs |
| axolotl re-render | external gills | absent | 0 | 0 | **correct miss** |
| beetle x bear (E4) | beetle | present (5 beetle bodies on the shoulders) | 0 | 0 | **false miss** |

Latency was 1.2 to 3.4 s. Overlays are in `live/s1/sam/*_overlay.png`. SAM finds named body parts with clear outlines very precisely. It does not report a beetle grown into fur as a "beetle", so an empty mask is not proof of absence.

## Verdicts

| Capability | Verdict | Why |
|---|---|---|
| Spark Open: short strict JSON (identify, audit, polish) | **use** | valid JSON, parity with Meta on identify and polish |
| Spark Open: image input (checklist, open critic, photo identify) | **use** | checklist 15/15 parity; recognized a griffin as mythic |
| Spark Open: tool calling | **use** | perfect 4-turn sequence with parallel calls and carried ids |
| Spark Open: refusals | **use** | 0 refusals in 8 real plan prompts (5 + 3) |
| Spark Open: plan writing (`evo_plan`) | **don't use** | 7 of 8 plan answers ran away inside `card_trace` to the output limit, about 60 s each |
| Spark Open: learn traits | **don't use** (for now) | one runaway (193 s) and one valid answer full of duplicate, wrong body plans |
| Spark Open: latency | **needs work** | about 2x Meta on vision (checklist 12.5 vs 6.8 s median); faster on polish (9.4 vs 15.6 s) and identify (3 to 4 vs 5.6 s) |
| Muse Image: reference images | **needs work** | style and skin carry over; anatomy does not; no score gain on this pair |
| Muse Image: edit turn (`previous_response_id`) | **use** for targeted fixes | edits the same creature, works on a day-old response; phrase the fix against the plan item and re-judge |
| SAM 3.1: part prompts | **use** to confirm a part is present | wings, head, legs exact; gills correctly absent |
| SAM 3.1: part absence | **don't use** as proof | the beetle bodies were missed |

## Recommended routing per call type (for step 3; not switched here)

| Call type | Route | Condition or fallback |
|---|---|---|
| first plan (`evo_plan`) | **Meta Spark** | Spark Open only after the model schema drops the code-owned arrays (`card_trace`, `processes`, `labels`) and the request sets `max_tokens` (about 6,000), then a new probe |
| prompt polish | Spark Open or Meta | parity 2/2; Spark Open is faster here |
| resolver identify (name or photo) | **Spark Open** | parity 2/2, faster; keep GBIF as the taxonomy authority |
| learn traits | **Meta Spark** | Spark Open needs bounded arrays (no duplicates) first |
| audit (`judge_functions`) | Meta Spark | Spark Open gave 1 good answer; too few samples to switch |
| checklist critic and thumbnail | either; Meta for latency | 15/15 agreement; Spark Open is a good independent second judge |
| open critic (logged) | Spark Open | a second model makes it a truly independent opinion |
| tool orchestration (resolve, audit, render loop) | **Spark Open** | the only provider probed for it; it worked |
| render | Muse Image, text first | add parent portraits only when a skin or style match matters |
| targeted fix after a failed structural checklist item | **Muse Image edit turn** | re-judge after the edit; the instruction names the plan item |
| part verification (limb slots, wings, head) | **SAM 3.1 with part names** | a mask confirms presence; an empty mask counts as "unclear", not "absent" |

The last two rows give a way to close E4's "next weakest point" (nothing acts on a failed structural checklist item):
- SAM confirms that a part named in the plan is present and in the right place.
- The edit turn makes one targeted fix without re-rolling the whole creature.
