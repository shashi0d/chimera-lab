# S5: benchmark, agent against the fixed pipeline, and the anatomy map

Branch `evo`, 2026-11-01. Not merged. **After this task the engine is frozen for the demo:** no further quality
tuning.

- **Benchmark:** `data/evo_benchmark.json` (11 cases, frozen; a test checks its hash). Scores are computed in code
  (`app/evolution/benchmark.py`) from the saved results and stored in `live/s5/scores.json`.
- **Live outputs:** `docs/evolution/live/s5/<case>/<agent|fixed>/`. Each folder holds:
  - the final image and the anatomy map (png and json);
  - plan.json and the exact prompts;
  - critic.json (each critic's answer per item) and inspect_final.json (the final image's full inspect, including
    both critics' descriptions);
  - meta.json (wall time, renders, edits, tool calls, calls per provider and purpose);
  - for the agent, also trace.json, trace.md, messages.json and every image with its prompt and plan.
- **Owner review sheet:** `docs/evolution/benchmark/s5_review.html`. Labels are hidden and the order is random. The
  key is in `s5_review_key.json`; open it only after rating.
- **The run:** 22 creatures, one per foreground invocation, committed and pushed after each case.
  - 700 calls, none failed.
  - No partial run or rerun, and no code fix during the run.
  - The engine code was not touched between the first and the last creature.

**Result: on the critics' scores the agent and the fixed pipeline are about even.**

| | agent | fixed pipeline |
|---|---|---|
| full matches | 5 of 11 | 6 of 11 |
| average critic failures | 1.82 | 1.91 |
| both parents named by the deciding critic | 7 of 11 | 5 of 11 |

- **The agent makes fewer structural failures (0.55 against 0.91) and more integration failures (1.27 against 1.0).**
- **It wins where the pipeline has no rule.** On a structural host tie (7 of the 11 cases) the pipeline falls back to
  the first-named parent. The agent chose the horse for pangolin × horse, the goat for tortoise × goat and the
  cheetah for penguin × cheetah, each with a reason. Its images name both parents more often.
- **It loses where it re-rolls on critic misreads:** octopus × horse spent 4 renders on a "toad" misread.
- **Cost:** about 1.6 times the calls of the pipeline (39 against 24 per creature) and 27% more wall time.
- **The S5 fixes:**
  - D1, material only, gave the two-failure rule a working second route. It was used in 4 cases, but its new critic
    items failed every time. They are uncalibrated.
  - D2, a reason against the code's ranking, never triggered: the agent's pick matched the code's in all 11 cases.
  - D3, typed schemas: no tool call was refused in the whole benchmark run, against 15 refusals in S3c.

## Part 1: the fixes the benchmark depends on

| | Change | Test |
|---|---|---|
| D1 (D-092) | A new typed operation, `set_covering_material_only(plan_reason)`. The host keeps its own covering, and the donor gives only its color, gloss, texture and pattern on it; identity parts stay. It brings its own compiler wording (no plate nouns) and critic items (`material_look`, `host_cover_kept`, `donor_pieces`). It is the two-failure rule's second route. | `test_d1_*` (2) |
| D2 (D-093) | Finalizing an image the code ranks lower needs `why_not_best`. The card's `final_choice` keeps both picks (image, stored key, rank, counts, reason), the agent's first. | `test_d2_*` (2) |
| D3 (D-094) | One tool per typed plan operation, each with its own schema, checked in code before the call runs. The plan's own parts and features are enums. All 15 refused S3c calls are replayed: 12 now fail the schema up front, and 3 (`unexplained_gap`) are explained in the tool description. The full table is in D-094. | `test_d3_*` (16) |

## Part 2: the anatomy map

`app/evolution/anatomy.py` works on the finalized image:
- it segments each planned part by name with SAM;
- it colors each found mask by its source parent (host blue, donor orange, a blend in a real hybrid purple);
- it saves an overlay with a legend, plus a JSON of part, SAM label, parent, role, color, mask area and found or not
  located;
- a mask under the presence threshold, or a failed SAM call, is listed as "not located", is never drawn and never
  gets a color.

`finalize` puts the map on the card. The runner made the same map for the pipeline's images. Over the 22 benchmark
images:

| part | found by SAM |
|---|---|
| head | 22 / 22 |
| legs (or hind legs) | 22 / 22 |
| tail | 22 / 22 |
| wings | 5 / 5 |
| named donor parts (horn, claws) | 4 / 4 |
| hybrid ears and mane | 4 / 4 |
| body ("torso") | 3 / 22 |
| donor covering (by its material noun, e.g. "glossy chitin plates") | 5 / 20 |

The map is honest about what SAM cannot find, but it is thin on the two largest regions. The colors follow the
plan's parent, not what is drawn: in b03 the head SAM found is an eagle's head on a lion host, and the map colors it
as the host's (see the known limits).

## Part 3 and 4: scores per case

All scores come from `live/s5/scores.json`.

- **Failures:** the critic rows that fail or are uncertain on the final image (Meta Spark decides).
- **Parents named:** whether the deciding critic's free "which animals do you see" answer names each parent.
- **Calls:** Meta includes images and SAM, and SAM includes the anatomy map (about 6 calls per creature).
- **Pipeline host:** "tie, fell back to the sire" marks a structural host tie, where the pipeline has no rule (D-085)
  and fused with the first-named parent to compare.

| case | system | host | full match | failures (structure / identity / integration) | parents named (sire, dam) | renders | edits | tool calls | calls Baseten / Meta | wall s |
|---|---|---|---|---|---|---|---|---|---|---|
| **b01** axolotl × Chinese pangolin (realistic) | agent | axolotl | **yes** | 0 (0 / 0 / 0) | yes, yes | 2 | 0 | 10 | 19 / 12 | 236 |
|  | fixed | axolotl (tie, fell back to the sire) | **yes** | 0 (0 / 0 / 0) | yes, yes | 1 | 0 | - | 6 / 10 | 152 |
| **b02** rhinoceros beetle × brown bear (speculative) | agent | bear | no | 7 (0 / 0 / 7) | yes, yes | 3 | 1 | 18 | 32 / 24 | 474 |
|  | fixed | bear | no | 7 (2 / 0 / 5) | yes, yes | 1 | 1 | - | 11 / 17 | 275 |
| **b03** lion × golden eagle (mythic) | agent | lion | **yes** | 0 (0 / 0 / 0) | yes, yes | 1 | 0 | 8 | 14 / 12 | 171 |
|  | fixed | lion (tie, fell back to the sire) | **yes** | 0 (0 / 0 / 0) | yes, yes | 1 | 1 | - | 11 / 19 | 289 |
| **b04** lion × golden eagle (realistic) | agent | eagle | **yes** | 0 (0 / 0 / 0) | no, yes | 1 | 0 | 8 | 14 / 10 | 170 |
|  | fixed | lion (tie, fell back to the sire) | **yes** | 0 (0 / 0 / 0) | yes, no | 1 | 1 | - | 11 / 17 | 259 |
| **b05** donkey × horse (realistic) | agent | horse | **yes** | 0 (0 / 0 / 0) | yes, no | 1 | 0 | 8 | 14 / 11 | 141 |
|  | fixed | horse | **yes** | 0 (0 / 0 / 0) | yes, no | 1 | 0 | - | 6 / 12 | 150 |
| **b06** common octopus × horse (realistic) | agent | horse | no | 1 (1 / 0 / 0) | no, yes | 4 | 0 | 18 | 33 / 18 | 351 |
|  | fixed | horse | **yes** | 0 (0 / 0 / 0) | no, yes | 1 | 1 | - | 11 / 14 | 236 |
| **b07** emperor penguin × cheetah (realistic) | agent | cheetah | no | 3 (2 / 0 / 1) | no, yes | 3 | 2 | 18 | 34 / 21 | 464 |
|  | fixed | penguin (tie, fell back to the sire) | no | 3 (3 / 0 / 0) | yes, no | 1 | 1 | - | 11 / 14 | 250 |
| **b08** red fox × barn owl (speculative) | agent | fox | no | 1 (1 / 0 / 0) | yes, yes | 2 | 0 | 10 | 19 / 15 | 222 |
|  | fixed | fox (tie, fell back to the sire) | no | 2 (2 / 0 / 0) | yes, yes | 1 | 1 | - | 11 / 17 | 251 |
| **b09** Indian pangolin × horse (realistic) | agent | horse | **yes** | 0 (0 / 0 / 0) | yes, yes | 1 | 1 | 10 | 17 / 12 | 213 |
|  | fixed | pangolin (tie, fell back to the sire) | **yes** | 0 (0 / 0 / 0) | yes, no | 1 | 0 | - | 6 / 11 | 173 |
| **b10** tortoise × domestic goat (realistic) | agent | goat | no | 5 (1 / 0 / 4) | yes, yes | 2 | 2 | 16 | 29 / 18 | 382 |
|  | fixed | tortoise (tie, fell back to the sire) | no | 2 (2 / 0 / 0) | yes, no | 1 | 1 | - | 11 / 14 | 244 |
| **b11** crab × gray wolf (speculative) | agent | wolf | no | 3 (1 / 0 / 2) | yes, yes | 3 | 1 | 18 | 31 / 23 | 424 |
|  | fixed | wolf | no | 7 (1 / 0 / 6) | yes, yes | 1 | 1 | - | 11 / 17 | 284 |

| | agent | fixed pipeline |
|---|---|---|
| full matches (of 11) | 5 | 6 |
| both parents named (of 11) | 7 | 5 |
| average critic failures | 1.82 | 1.91 |
| average structure failures | 0.55 | 0.91 |
| average identity failures | 0.0 | 0.0 |
| average integration failures | 1.27 | 1.0 |
| renders per creature | 2.09 | 1.0 (plus an edit turn in 8 of 11) |
| tool calls per creature | 12.91 | - |
| calls per creature (Baseten / Meta) | 39.27 (23.27 / 16.0) | 24.36 (9.64 / 14.73) |
| wall time per creature | 295.3 s | 233.1 s |

**Usage over the whole benchmark run** (22 creatures):

| Provider and model | Calls | By purpose |
|---|---|---|
| Baseten, Muse Spark Open | 362 | agent turns 139, checklist 60, describe 50, ask 49, judge 30, polish 34 |
| Meta, Muse Image 1.0 | 49 images | agent: 23 renders and 7 edits; pipeline: 11 renders and 8 edits |
| Meta, Muse Spark 1.3 | 110 | describe 49, ask 49, plan 11, audit 1 |
| Meta, SAM 3.1 | 179 | about 130 of them for the anatomy maps |

The shared counter (`docs/live/budget.json`) went from image 162, Meta Spark 637, SAM 161 and Spark Open 1061 to
211, 747, 340 and 1423.

## Where the agent's choices made the difference

**The host on a structural tie** (7 of 11 cases tie: b01, b03, b04, b07, b08, b09 and b10; the pipeline falls back to the first-named parent).

- **b09, Indian pangolin × horse: helped.**
  - The agent, step 4, `choose_candidate C2`: *"Chosen horse as host for realistic mode - horse body carries
    autonomous function, grassland niche shared, and full scale covering provides clear pangolin identity"*. It then
    made one edit of the covering (*"show continuous large overlapping keratin scales sized to horse body"*), and the
    image passed.
  - The result is a horse fully covered in pangolin scales. The deciding critic names a horse and a pangolin.
  - The pipeline's pangolin host also passes every item, but the deciding critic sees only a pangolin.
- **b10, tortoise × domestic goat: helped.**
  - The agent: *"choose domestic goat as host because its cursorial quadruped frame provides complete autonomy for
    grassland niche"*.
  - The pipeline's tortoise host draws a tortoise with fleece legs and a beak (extra_beak, extra_stripes), and the
    goat is not named. The agent's goat is named with the tortoise.
- **b07, emperor penguin × cheetah: mixed.**
  - The agent: *"Choosing cheetah host for realistic mode: quadruped mammalian frame provides better autonomy and
    survival"*.
  - The cheetah with a penguin's black cape and yellow collar reads as a cheetah. The pipeline's penguin host reads
    as a penguin with stray wing parts (3 structural failures). Each names only its host.
- **b04, lion × golden eagle (realistic): hurt, by my eye.**
  - The agent: *"Choose golden eagle host from tie; upright biped frame preserves flight/feeding autonomy"*.
  - Both systems pass every item. But the agent's image is a golden eagle with lion-toned plumage, and the critic
    names only "eagle". The pipeline's lion standing on its hind legs, with eagle wings in place of the forelegs,
    shows both parents.
- **b01, b03, b08:** the agent picked the same host as the pipeline's fallback.

**Choosing and re-rolling images.**

- **b01: helped.** The first render failed on extra_spots. The agent: *"Structural extra_spots is unplanned feature
  not in plan parts; ... re-rendering may remove artifact without plan change"*. The second render passed. The
  pipeline also passed, with its first render.
- **b08: no change in failures.** A re-render made things worse (legs_and_wings, extra_legs). The agent: *"re-render
  increased failures, so img1 is optimal"*. It finalized img1 with 1 failure, against the pipeline's 2.
- **b06, common octopus × horse: hurt.**
  - All four renders were flagged third_animal (the mottled octopus skin read as a toad). Each time the agent
    re-rendered the unchanged plan: *"Additional render attempt to achieve accurate depiction; inspect misreads
    consistent"*. It ended at the render cap with 1 failure.
  - The pipeline's single edit turn passed every item. Its image, though, is a nearly plain grey horse.

**The two-failure rule and material only (D1).**

- **b11, crab × gray wolf: helped by the critics' count.** Two covering failures fired the rule. The agent reduced
  the extent (*"Dorsal carapace shields back and flanks only while legs stay bare..."*), then went material only
  (*"Reddish-brown carapace color and gloss show on wolf fur dorsally without heavy chitin plates"*). It finalized a
  wolf with crab claws and a subtle gloss: 3 failures, against the pipeline's armored wolf with 7.
- **b02, rhinoceros beetle × brown bear: no gain.** The material-only render was worse (whole_animal,
  extra_limb_pieces). The agent finalized its edited armor image instead, which has 7 integration failures, the same
  as the pipeline (5 integration and 2 structural).
- **b10 and b07:** material only gave tortoise-patterned and penguin-colored fur, but the new items failed on both.

## Known limits

1. **A hard covering over fur reads as worn, not grown.** The evidence, step by step:
   - S2: the owner judged the beetle plates "armor pieces sitting on the fur".
   - S3a: the owner review said the shell is pasted on.
   - S3b: the integration rules helped the critics' integration answers, not this look.
   - S3c: all 8 covering runs failed grows_out and on_top, and extent changes did not help.
   - S5: b02 failed for both systems (7 and 5 integration failures), as did b11's pipeline image (6). Keratin scales
     over skin or hide pass (b01 axolotl, b09 horse). It is plates and shells over fur that do not.
   - Muse Image draws them as armor. Material only (D1) avoids the armor look, but by giving up the covering's form.
2. **The material-only critic items are uncalibrated.** They failed in all 4 uses (b02, b07, b10, b11), including
   images where the donor's color is plainly visible on the fur (b10, b11). They have no gold labels yet. Until the
   owner rates such images, their failures are not reliable.
3. **The critics misread a donor's own pattern or texture.** Owl or cheetah spotting is called extra_spots or
   extra_stripes (b01 img1, b07, b08 in both systems). Textured skin is called a third animal ("toad" in b06,
   "pillbug" in b02 and b11 pipeline). The agent cannot fix a misread with a plan operation, so it re-rolls, and in
   b06 it spent all 4 renders.
4. **The image model's archetypes override the plan.** Lion × eagle (mythic) is drawn as the classic griffin with an
   eagle's head, although the plan keeps the lion's head. Both critics passed it in both systems (b03). In the
   realistic b04, the agent's eagle host left the lion as color only.
5. **The anatomy map finds the body and coverings poorly** (torso 3/22, coverings 5/20). It colors by the plan's
   parent, not by what is drawn.
6. **The pipeline has no host on a tie** (D-085). It needs the agent, or a user choice, to pick one.
7. **D2 never triggered in the benchmark.** It is tested in mock only.

## Proposed showcase (pending the owner's ratings in s5_review.html)

| # | Creature | Image | Why |
|---|---|---|---|
| 1 | b09 Indian pangolin × horse | agent | A horse fully scaled like a pangolin. Full match, both parents named, and the agent's host choice made it. |
| 2 | b01 axolotl × Chinese pangolin | agent (the pipeline's is near-identical) | Full match, both named. The axolotl's gills and face under pangolin scales are the clearest integration in the set. |
| 3 | b03 lion × golden eagle, mythic | agent | A clean griffin, full match. Caveat: an eagle head (limit 4). |
| 4 | b08 red fox × barn owl | agent | Owl wings as the fox's forelimbs. Its only failure is the owl's own spotting (limit 3), and it was held out in S3c. |
| 5 | b11 crab × gray wolf | agent | A wolf with crab claws and carapace-colored fur: the two-failure rule's route shown working. |
| 6 | b05 donkey × horse | either | The real-hybrid baseline: a realistic mule, full match. |

Alternates: b04's pipeline image (an upright lion with eagle wings as forelimbs) as the realistic lion × eagle, and
b07's agent image (a cheetah in penguin colors).

## Appendix: per-case agent decisions

From each `live/s5/<case>/agent/trace.md`: the choice, plan operations, renders, edits, inspects and finalize, with
reasons cut to fit.

**b01 axolotl × Chinese pangolin (realistic)**: 2 renders, 0 edits, 10 tool calls, 236 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "Select axolotl host per R10 autonomy: axolotl body carries every function without dropped parts, and host tie choice justified by intact breathing and bridging river-forest niche." → C1: host axolotl, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking items; rendering in realistic mode to inspect covering integration." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - extra_spots (structural, fail)
- 8. `render` {"method": "single_pass"}: "Structural extra_spots is unplanned feature not in plan parts; per RC-R10-15 re-rendering may remove artifact without plan change." → img2 (single_pass), renders used 2
- 9. `inspect`: img2: pass
- 10. `finalize` {"image_id": "img2"}: "Second render passes all inspections; achieving clean pangolin scale covering on axolotl host in realistic river-forest setting." → crt_5816c9e8a21c; remaining failures 0

**b02 rhinoceros beetle × brown bear (speculative)**: 3 renders, 1 edits, 18 tool calls, 474 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "C1 has proper identity part (head horn) and covering from beetle gloss, host brown bear provides quadruped frame; higher R10 score and correct speculative handling of arthropod size." → C1: host brown bear, parts ['european rhinoceros beetle head horn']
- 6. `render` {"method": "single_pass"}: "Audited plan pass with licensed arthropod large support; rendering brown bear frame with beetle horn and glossy plates." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); follows_body (covering, fail); separate_outl…
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "grows_out", "on_top", "continuous", "scattered", "follows_body"…: "Covering failures dominate inspect: plates not grown from skin, scattered, not following bear contours; editing to integrate glossy chitin plates as continuous covering per RC-R10-15 identity." → img2 from an edit: Show the planned hard, glossy chitin plates with fine seams over the head, neck,…
- 9. `inspect`: img2: fail - grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); follows_body (covering, fail); separate_outline (covering, fail); abrupt_sto…
- 10. `set_extent` {"extent": ["forequarters", "back", "flanks", "hindquarters"], "plan_reason": "Dorsal armor protects spine while legs s…: "Two consecutive covering failures trigger two-failure rule; reducing extent from 9 zones to 4 dorsal zones keeps plates continuous and explains bare legs per RC-R10-16." → set_extent ok
- 12. `render` {"method": "single_pass"}: "Re-rendering with dorsal-only chitin plates for better continuity and structural plausibility." → img3 (single_pass), renders used 2
- 13. `inspect`: img3: fail - grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); separate_outl…
- 14. `set_covering_material_only` {"plan_reason": "Dorsal gloss shows beetle iridescence through bear fur for camouflage while retaining fur insulation"}: "Persisting covering integration failures after extent reduction; switching to material-only display retains beetle gloss color without separate chitin plates, per two-failure rule second route." → set_covering_material_only ok
- 16. `render` {"method": "single_pass"}: "Final speculative render with material-only beetle gloss on bear fur plus discrete horn, audited and licensed." → img4 (single_pass), renders used 3
- 17. `inspect`: img4: fail - whole_animal (structural, fail); material_look (covering, fail); host_cover_kept (covering, fail); donor_pieces (covering, fail); extra_limb_pieces (structural, fail)
- 18. `finalize` {"image_id": "img2"}: "Finalizing best inspected image per inspect comparison (img2 structural 0 vs later structural separate-animal failures); remaining covering failures accepted on card as integration limits under speculative license." → crt_581a4148c23c; remaining failures 7

**b03 lion × golden eagle (mythic)**: 1 renders, 0 edits, 8 tool calls, 171 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "Choosing C1 lion host as classic mythic griffin archetype: lion body frame carries eagle wings, best identity for sire/dam in mythic mode. Host tie resolved by narrative fit per RC-R10-01." → C1: host lion, parts ['wings (extra pair)']
- 6. `render` {"method": "single_pass"}: "Plan audited and renderable, proceeding to single_pass render." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: pass
- 8. `finalize` {"image_id": "img1"}: "Inspect passed with zero structural/covering failures; best-so-far image ready for mythic finalize." → crt_46a3684ebd3e; remaining failures 0

**b04 lion × golden eagle (realistic)**: 1 renders, 0 edits, 8 tool calls, 170 s.

- 4. `choose_candidate` {"candidate_id": "C2"}: "Choose golden eagle host from tie; upright biped frame preserves flight/feeding autonomy vs lion bipedal reorganization, better realistic viability (RC-R10-01 not by mass, RC-R10-15 niche)." → C2: host golden eagle, parts []
- 6. `render` {"method": "single_pass"}: "Audited plan renderable; realistic single pass." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: pass
- 8. `finalize` {"image_id": "img1"}: "Inspect passed with no failures; realistic golden eagle-host chimera validated." → crt_e67565bc4797; remaining failures 0

**b05 donkey × horse (realistic)**: 1 renders, 0 edits, 8 tool calls, 141 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "Single realistic candidate: horse host provides body frame (RC-R6-08), donkey traits blended - appropriate for equid hybrid (hinny/mule) in realistic mode." → C1: host horse, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited clean with no blocking; ready to render realistic horse-donkey hybrid." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: pass
- 8. `finalize` {"image_id": "img1"}: "Inspection passed with 1 body, 1 head, 4 walking legs, no extra parts; realistic equid hybrid successfully rendered." → crt_21e0b6d5287f; remaining failures 0

**b06 common octopus × horse (realistic)**: 4 renders, 0 edits, 18 tool calls, 351 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "Horse host provides structured quadruped frame per RC-R6-08; C1 highest score, no licenses needed, suitable for realistic mode." → C1: host horse, parts []
- 5. `set_mode` {"mode": "realistic"}: "Requested realistic mode; ensure plan mode matches." → set_mode ok
- 7. `render` {"method": "single_pass"}: "Plan audited and renderable, proceed to render horse host with octopus covering." → img1 (single_pass), renders used 1
- 8. `inspect`: img1: fail - extra_spots (structural, fail); third_animal (structural, fail)
- 10. `render` {"method": "single_pass"}: "Unplanned features are not plan parts; re-render to clarify covering as horse skin with octopus texture, RC-R10-15." → img2 (single_pass), renders used 2
- 11. `inspect`: img2: fail - extra_spots (structural, fail); third_animal (structural, fail)
- 13. `render` {"method": "single_pass"}: "Additional render attempt to achieve accurate depiction; inspect misreads consistent, need best image." → img3 (single_pass), renders used 3
- 14. `inspect`: img3: fail - third_animal (structural, fail)
- 16. `render` {"method": "single_pass"}: "Final render allowance to attempt clean structural pass." → img4 (single_pass), renders used 4
- 17. `inspect`: img4: fail - third_animal (structural, fail)
- 18. `finalize` {"image_id": "img4"}: "4 renders exhausted, best image img4 has single structural misread (mottled octopus skin texture interpreted as fish/toad) but correct horse frame 4 legs 1 head 1 body; realistic mode with horse host and octopus skin co…" → crt_de93741c3122; remaining failures 1

**b07 emperor penguin × cheetah (realistic)**: 3 renders, 2 edits, 18 tool calls, 464 s.

- 4. `choose_candidate` {"candidate_id": "C2"}: "Choosing cheetah host for realistic mode: quadruped mammalian frame provides better autonomy and survival in alpine meadow bridging habitat per RC-R10-01 tie-break not by mass." → C2: host cheetah, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking issues and heat function repaired; ready for single-pass render in realistic mode." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - plain_fur (covering, fail); wings (structural, fail); extra_spots (structural, fail); extra_wings (structural, fail)
- 8. `edit` {"image_id": "img1", "failure_keys": ["plain_fur"]}: "Fixing covering failure plain_fur per critics: show plain coat with no stripes/spots as planned, structural extra_* will be addressed via re-render if needed per RC-R10-15/16." → img2 from an edit: Show a plain coat with no stripes or spots, as planned; keep everything else the…
- 9. `inspect`: img2: fail - wings (structural, fail); extra_stripes (structural, fail); extra_wings (structural, fail)
- 10. `render` {"method": "single_pass"}: "Structural failures are extra hallucinated features (extra_stripes, extra_wings) per RC-R10-12/15/16; re-rendering same audited plan to clear unplanned features as advised." → img3 (single_pass), renders used 2
- 11. `inspect`: img3: fail - plain_fur (covering, fail); extra_spots (structural, fail); extra_stripes (structural, fail)
- 12. `edit` {"image_id": "img3", "failure_keys": ["plain_fur"]}: "Second covering fix for plain_fur on latest render; structural extra_spots/stripes are hallucinations to be resolved via re-render comparison per two-failure rule." → img4 from an edit: Show a plain coat with no stripes or spots, as planned; keep everything else the…
- 13. `inspect`: img4: fail - plain_fur (covering, fail); extra_spots (structural, fail); extra_stripes (structural, fail) [two-failure rule: covering edits stop]
- 14. `set_covering_material_only` {"plan_reason": "Host retains fur while penguin shows through color only for heat retention in alpine meadow"}: "Two-failure rule triggered after two covering fails; switching to material-only to keep cheetah fur with penguin color per RC-R10-15/16, reducing covering edits." → set_covering_material_only ok
- 16. `render` {"method": "single_pass"}: "Plan audited with material-only covering; rendering to resolve persistent plain_fur hallucinations in alpine meadow habitat." → img5 (single_pass), renders used 3
- 17. `inspect`: img5: fail - plain_fur (covering, fail); material_look (covering, fail); host_cover_kept (covering, fail); extra_spots (structural, fail); omitted_feathers (structural, fail)
- 18. `finalize` {"image_id": "img4"}: "Finalizing best inspected image img4 (2 structural +1 covering =3 total, lowest covering among recent renders). Remaining plain_fur and extra_spots/stripes are critic hallucinations of unplanned features per RC-R10-12/1…" → crt_22c96fe40787; remaining failures 3

**b08 red fox × barn owl (speculative)**: 2 renders, 0 edits, 10 tool calls, 222 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "Choosing red fox host with barn owl wings: maintains mammalian quadruped frame adapted for forest niche, preserves movement autonomy via wing-modified forelimbs; tie broken by functional narrative not size/mass per RC-R…" → C1: host red fox, parts ['wings (forelimbs)']
- 6. `render` {"method": "single_pass"}: "Plan audited and renderable; proceed to render speculative chimera." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - extra_spots (structural, fail)
- 8. `render` {"method": "single_pass"}: "Structural extra_spots is unplanned feature not in plan; re-rendering to remove spots per RC-R10-15 without plan change." → img2 (single_pass), renders used 2
- 9. `inspect`: img2: fail - legs_and_wings (structural, fail); extra_legs (structural, fail); walking_legs (structural, fail); extra_spots (structural, fail)
- 10. `finalize` {"image_id": "img1"}: "Finalizing best inspected image img1 with 1 structural unplanned feature (extra_spots) noted on card; re-render increased failures, so img1 is optimal per RC-R10-15." → crt_cfb3d03489eb; remaining failures 1

**b09 Indian pangolin × horse (realistic)**: 1 renders, 1 edits, 10 tool calls, 213 s.

- 4. `choose_candidate` {"candidate_id": "C2"}: "Chosen horse as host for realistic mode - horse body carries autonomous function, grassland niche shared, and full scale covering provides clear pangolin identity per RC-R10" → C2: host horse, parts []
- 6. `render` {"method": "single_pass"}: "Plan passes audit; rendering horse host with pangolin scale covering" → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - cover_present (covering, fail); continuous (covering, fail); sized_to_body (covering, fail); wrong_scale (covering, fail)
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "continuous", "sized_to_body", "wrong_scale"]}: "Covering failures require edit to show continuous large overlapping keratin scales sized to horse body per RC-R10" → img2 from an edit: Show the planned large overlapping keratin scales over the head, neck, shoulders…
- 9. `inspect`: img2: pass
- 10. `finalize` {"image_id": "img2"}: "Image passes inspection with horse host and continuous pangolin scale covering correctly rendered" → crt_b5948c4c441f; remaining failures 0

**b10 tortoise × domestic goat (realistic)**: 2 renders, 2 edits, 16 tool calls, 382 s.

- 4. `choose_candidate` {"candidate_id": "C2"}: "Host tie per RC-R10-01; choose domestic goat as host because its cursorial quadruped frame provides complete autonomy for grassland niche and can carry tortoise dorsal armor without skeletal rearrangement, favoring surv…" → C2: host domestic goat, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited and renderable with tortoise carapace on goat back; realistic mode within budget." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fail); separ…
- 8. `edit` {"image_id": "img1", "failure_keys": ["grows_out", "on_top", "scattered", "cover_on_legs", "cover_on_shoulders", "follo…: "Covering failures: plates must grow from skin over back only, replacing fur there, conform to goat body shape and segment sizing, not on limbs." → img2 from an edit: Show the hard shell plates grown in the skin over the back, as one covering that…
- 9. `inspect`: img2: fail - grows_out (covering, fail); on_top (covering, fail); follows_body (covering, fail); separate_outline (covering, fail); sized_to_body (covering, fail); wrong_scale (covering, fail); extra…
- 10. `set_covering_material_only` {"plan_reason": "Host retains insulating fur while displaying tortoise carapace coloration for camouflage"}: "Two covering failures in a row per rule; switch to material-only to keep goat fur and show tortoise brown-yellow pattern by color/texture, improving realism and thermoregulation." → set_covering_material_only ok
- 12. `render` {"method": "single_pass"}: "Audited material-only plan ready to render: goat fur with tortoise carapace color pattern." → img3 (single_pass), renders used 2
- 13. `inspect`: img3: fail - plain_fur (covering, fail); material_look (covering, fail); host_cover_kept (covering, fail); donor_pieces (covering, fail); extra_horn (structural, fail)
- 14. `edit` {"image_id": "img3", "failure_keys": ["material_look", "host_cover_kept", "donor_pieces", "plain_fur"]}: "Covering material-only failures: need goat fur everywhere with tortoise brown-yellow color/gloss on back only, no hard plates, plain coat per plan." → img4 from an edit: Keep the domestic goat's own fur everywhere; over the back it takes only the tor…
- 15. `inspect`: img4: fail - plain_fur (covering, fail); material_look (covering, fail); host_cover_kept (covering, fail); donor_pieces (covering, fail); extra_horn (structural, fail) [two-failure rule: covering edi…
- 16. `finalize` {"image_id": "img4"}: "Best inspected image despite persistent covering critiques; material-only tortoise coloration on goat fur is subtle and critics misread host goat horns as extra; structural counts correct, no third animal per Meta Spark…" → crt_92feafbff025; remaining failures 5

**b11 crab × gray wolf (speculative)**: 3 renders, 1 edits, 18 tool calls, 424 s.

- 4. `choose_candidate` {"candidate_id": "C1"}: "C1 is best ranked: wolf host retains functional autonomy, crab claws as identity part, bridging rocky coast habitat, speculative mode fits arthropod license." → C1: host gray wolf, parts ['crab claws']
- 6. `render` {"method": "single_pass"}: "Plan passes audit, render speculative chimera." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - dropped_segmented_tail (structural, fail); cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); separate_outline (covering, f…
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "grows_out", "on_top", "continuous", "separate_outline"]}: "Covering failures dominate first inspect; editing to grow hard glossy chitin plates as continuous skin-integrated covering per RC-R10-15." → img2 from an edit: Show the planned hard, glossy chitin plates with fine seams over the head, neck,…
- 9. `inspect`: img2: fail - dropped_segmented_tail (structural, fail); cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); f…
- 10. `set_extent` {"extent": ["back", "flanks"], "plan_reason": "Dorsal carapace shields back and flanks only while legs stay bare for ru…: "Second consecutive covering failure per RC-R10-12/15, so reducing extent from full-body to dorsal-only to make continuous plates more renderable while keeping legs free." → set_extent ok
- 12. `render` {"method": "single_pass"}: "Reduced dorsal carapace plan audited, rendering again." → img3 (single_pass), renders used 2
- 13. `inspect`: img3: fail - whole_animal (structural, fail); insect_legs (structural, fail); extra_legs (structural, fail); dropped_segmented_tail (structural, fail); grows_out (covering, fail); on_top (covering, f…
- 14. `set_covering_material_only` {"plan_reason": "Reddish-brown carapace color and gloss show on wolf fur dorsally without heavy chitin plates for mobil…: "After repeated covering failures RC-R10-12/15, switching to material-only lets donor show through color/gloss on wolf fur while keeping identity claws." → set_covering_material_only ok
- 16. `render` {"method": "single_pass"}: "Material-only plan most likely to pass critics while retaining wolf frame and crab claw identity." → img4 (single_pass), renders used 3
- 17. `inspect`: img4: fail - material_look (covering, fail); donor_pieces (covering, fail); extra_spots (structural, fail)
- 18. `finalize` {"image_id": "img4"}: "Speculative wolf-host chimera best achievable after two covering failures and extent reduction then material-only; img4 is best_so_far with 1 structural 2 covering fails, retaining wolf frame, crab claw pincers, dorsal …" → crt_20286d65d31d; remaining failures 3
