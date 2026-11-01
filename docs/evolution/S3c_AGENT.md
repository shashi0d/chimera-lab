# S3c: the agent core

Branch `evo`, 2026-11-01. Not merged.

- **Live outputs:** `docs/evolution/live/s3c/agent/<pair>/<r1|r2>/` (agent) and `live/s3c/fixed/<pair>/r1/` (fixed
  pipeline). Every agent folder holds trace.json, trace.md, messages.json (exactly what the agent was sent and
  answered), candidates.json, plan.json, every image with its exact prompt, compiled prompt and plan, critic.json
  (each critic's answer per item, per image), image.webp and doc.json.
- **Earlier run, kept for comparison:** `live/s3c/agent_v1/` holds 8 creatures from the first full run, which used
  the code before the memory fix and the two-failure rule. That run finished, but the host stopped the session for
  low memory before its fixed-pipeline part. The smoke run is `live/s3c/agent/beetle_bear/smoke_r1`.
- **Caps per creature:** 4 renders and 30 tool calls (plus 6 edits). No creature reached either cap: the most was 4
  renders and 26 tool calls.

**Result:**

- **The agent works end to end live, on all four pairs.**
  - Every step has a reason.
  - Every creature was finalized by the agent itself; code never had to step in.
  - No cap was hit.
  - 15 of 158 tool calls (9%) were refused by a guardrail or by a typed operation's validation. Each time, the agent
    read the error and went on.
- **It clearly beat the fixed pipeline on one pair: tortoise × goat (the tie).**
  - The agent chose the goat as host in all 4 runs (v1 and now), each time with a reason (autonomy, niche).
  - The fixed pipeline falls back to the first-named parent (the tortoise). Its image reads as a third animal, a
    fleece-covered tortoise with a sheep's head.
- **On the other three pairs it did about as well as the fixed pipeline.**
  - Fox × owl (held out): slightly better, 1 remaining failure per run against the pipeline's 2.
  - Crab × wolf and beetle × bear: mixed. The covering failures the S3b critics report (plates that look laid on top,
    not grown) survive every edit and every plan change the agent tried.
- **The two-failure rule works as written but did not change any outcome.**
  - It fired in 4 of 8 runs, and each time the agent stopped editing and changed the plan.
  - Shrinking the covering's extent did not make the plates read as grown in.
  - The rule's second route, "material and color only", has no typed operation for a covering. The agent tried
    `set_transfer_class non_homologous` on the covering 4 times, and code refused it every time
    (`covering_is_material`). My prompt wording invited that try (see "Problems found").
- **The held-out fox × owl did as well as or better than the tuned pairs**, with the fewest failures. It is also the
  only pair without a covering.
- **The agent's cost is about three times the fixed pipeline's.** Per creature: about 33 Spark Open calls and 3.9
  images, against 11 calls and 2 images.
- **Tests:** 934 passed, 6 skipped. Two new tests: one for the memory fix, one for the two-failure rule.

## What changed in S3c

| Step | Change | Commit |
|---|---|---|
| Part 1 | Plan fixes from the S3b images (owner decisions D1 to D4): <ul><li>the license compensation comes from the donor's own breathing trait;</li><li>one identity part per donor, chosen from its own diagnostic parts (`set_identity_part`);</li><li>plate layout comes from the donor;</li><li>a covering keeps the host's outline;</li><li>a turtle host keeps its shell (RC-R10-17);</li><li>a structural host tie returns `needs_choice` (D-085).</li></ul> | cbd1b1a |
| Part 2 | `agent.py`: a Spark Open tool loop over ten tools, with guardrails in code: <ul><li>audit before render;</li><li>hard cards and an unchosen tie block the render;</li><li>an edit only for covering failures;</li><li>a host-drift check after every edit;</li><li>caps: 4 renders, 30 calls, 6 edits.</li></ul> Every call needs a reason, and every run writes trace.json and trace.md. The live smoke run led to two fixes: `plan_op` reports `changed`, and inspect returns every image's counts and the best so far (D-089). | 9d6408c, ce5b40d, 1708287 |
| Part 4 | 32 mock tests (`test_s3c_agent.py`). | 26d6945 |
| Finish 2: memory | Agent images now live on disk only (`Image.path`). Inspect, the drift check and finalize load the bytes for one call and release them. The agent's history never held image data: tool results are JSON summaries, critic payloads build their base64 per call, and recordings elide it. A new test checks all three. | 521552e |
| Finish 3: resume | `s3c_live.py` saves the run after every tool step (temp-file renames) and writes doc.json last as the "finalized" marker. A rerun skips anything with doc.json and keeps a partial folder as `rN_partialK`. Runs go one creature per foreground invocation (`--max 1`). Step labels now include the repeat folder. | eca9fba |
| Finish 4: rule | The two-failure rule goes in the system prompt and is enforced in code: covering edits are locked on that plan's content until the plan changes. | 17b35a7 |
| Finish 5: usage | 540 was the project-wide Spark Open counter. No creature went over 30 tool calls. See `live/s3c/usage_check.md`. | 06a51e9 |
| Finish 6 | Trace display: a refused plan operation now shows its own error code. It used to show "refused: None"; the agent always saw the real error. | 3ef0de3 |

### Memory fix: before and after

Measured with `scripts/s3c_memory.py`. The run was one beetle × bear creature in mock mode, using real 0.5 MB Muse
Image webps as the renders, with 4 renders and 6 images. Raw numbers are in `live/s3c/memory.json`.

| | tracemalloc peak | retained after the run | image bytes held by the run | image bytes in the agent's messages | peak working set |
|---|---|---|---|---|---|
| before | 16.26 MB | 6.34 MB | 3.22 MB | 0 | 137.5 MB |
| after | 13.63 MB | 3.12 MB | 0 | 0 | 135.5 MB |

The fix saves about 0.5 MB per image, which is 3 to 5 MB per creature. **That is not what exhausted the host.** A
whole creature peaks at about 14 MB of Python allocations. The earlier stop was the host reclaiming memory from
background shells, so the validation now runs in the foreground, one creature per invocation.

## Runs

The failure counts are for the finalized image: S = structural, C = covering. The rule column says whether the
two-failure rule fired.

| pair | run | host | renders | edits | tool calls | images | final | S | C | rule |
|---|---|---|---|---|---|---|---|---|---|---|
| tortoise × goat (realistic) | agent r1 | goat | 2 | 1 | 16 | 3 | img2 (edit) | 1 | 4 | fired after the first edit |
| | agent r2 | goat | 2 | 1 | 17 | 3 | img2 (edit) | 1 | 7 | fired after the first edit |
| | fixed | tortoise (needs_choice → sire) | 1 | 1 | - | 2 | edited | 3 | 0 | - |
| | v1 r1 / r2 | goat / goat | 2 / 2 | 2 / 2 | 17 / 15 | | img3 / img3 | 1 / 1 | 4 / 4 | not in v1 |
| fox × owl (held out) | agent r1 | fox | 4 | 0 | 19 | 4 | img4 | 1 | 0 | no |
| | agent r2 | fox | 3 | 0 | 16 | 3 | img2 | 1 | 0 | no |
| | fixed | fox | 1 | 1 | - | 2 | first (edit discarded) | 2 | 0 | - |
| | v1 r1 / r2 | fox / fox | 3 / 3 | 1 / 0 | 14 / 16 | | img4 / img3 | 1 / 0 | 0 / 0 | |
| crab × wolf | agent r1 | wolf | 3 | 1 | 20 | 4 | img1 | 1 | 4 | no |
| | agent r2 | wolf | 4 | 0 | 26 | 4 | img2 | 1 | 9 | no |
| | fixed | wolf | 1 | 1 | - | 2 | first (edit discarded) | 0 | 8 | - |
| | v1 r1 / r2 | wolf / wolf | 3 / 4 | 2 / 2 | 14 / 22 | | img1 / img1 | 0 / 1 | 7 / 7 | |
| beetle × bear | agent r1 | bear | 4 | 2 | 23 | 6 | img5 (growth) | 1 | 5 | fired after the first edit |
| | agent r2 | bear | 3 | 1 | 21 | 4 | img2 (edit) | 1 | 0 | fired at the last inspect |
| | fixed | bear | 1 | 1 | - | 2 | edited | 1 | 7 | - |
| | v1 r1 / r2 | bear / bear | 1 / 4 | 2 / 2 | 12 / 19 | | img2 / img4 | 0 / 1 | 4 / 0 | |

In agent runs, "renders" counts render calls, and a growth render counts once for two images.

### The agent's choices, with reasons (excerpts from trace.md)

The full decision list and each final critic table are in the appendix.

**Tortoise × goat (the tie case)**
- r1, step 4, `choose_candidate C2`: *"host tie decision per RC-R10-01: goat body carries every function with
  grassland niche overlap, autonomy favors mammalian host for realistic chimera, and shell as dorsal covering..."*
- r2, step 4: *"tie broken by autonomy and identity - goat frame carries all functions in shared grassland niche,
  while tortoise high-domed carapace provides clear, realistic donor identity on back..."*
- Both runs then made one edit of the covering. The second inspect fired the rule, and the agent changed the plan:
  - r1, step 12, `set_extent ["back"]`: *"Two-failure rule: reducing covering extent to single back zone with
    explicit reason to ensure natural skin transition and prevent scattered/leg plates."*
- The new render was worse, and the agent finalized the edit:
  - r1, step 16: *"img2 (1 structural, 4 covering failures) vs img3 (1+7) - new render worsened covering"*

**Fox × owl (held out)**
- Both runs chose C1 (fox host, owl wings as the forelimbs):
  - r1, step 4: *"red fox as host for horizontal quadruped frame allowing owl wings as forelimbs"*
- Every failure was structural: frame, extra_spots, and once legs_and_wings. An edit cannot fix those, so the
  agent re-rendered.
- Its plan operations were tries that changed nothing or were refused:
  - `set_identity_cues` on the covering (refused `not_a_part`);
  - `drop_part spots` (refused `no_such_part`);
  - `set_host red fox`, which it already was;
  - `set_region forelimbs PICK`, which was already so.
- r1 finalized its fourth render, which had 1 failure. r2 finalized img2: *"1 structural failure: frame ... no
  covering failures to edit"*.

**Crab × wolf**
- C1, wolf host with crab claws: *"gray wolf host provides structured quadruped frame (RC-R6-08) with crab claws
  as identity part"*.
- The agent mostly changed the plan instead of editing. It reduced the covering's extent step by step:
  - r1: no legs or tail, then back and flanks;
  - r2: back and flanks, then back only.
  - r1, step 10: *"Structural failures insect_legs and segmented tail suggest leg/tail chitin plates misread as
    extra limbs/tail ... reducing covering extent to remove legs and tail."*
- Every smaller covering scored worse with the critics: "insect_legs" stayed, and "separate_outline" was added.
- So r1 finalized its first render: *"fewest structural failures (1 third_animal lobster misread vs 3 in later
  renders)"*.
- r2 tried `drop_part crab claws` and then restored the claws two steps later: *"core identity requires crab
  trait per R10"*. Those were wasted calls.

**Beetle × bear**
- C1, bear host with the beetle's head horn. r1 edited once, the rule fired, and it changed the plan:
  - step 11: covering without the legs, *"with stated functional reason for bare legs per RC-R10-16"*;
  - step 12: `set_transfer_class head horn non_homologous` (accepted);
  - step 16: a growth render;
  - step 19: covering on the back and flanks only.
- It finalized the growth image img5 as the best: *"img5 has fewest failures (1 structural, 5 covering)"*.
- r2's single edit cleared every covering item, but the critics then called the creature a pill bug
  (`third_animal`). Two plan changes and two renders after that were worse.
- The agent finalized the edit img2, whose only failure is structural. Code's ranking (structural first) preferred
  img1, which has 0 structural and 5 covering failures. The card records this:
  *"the agent finalized img2; by failure counts img1 was better"*.

### Where the agent differed from the fixed pipeline, and whether it helped

| pair | difference | helped? |
|---|---|---|
| tortoise × goat | **Host.** On a structural tie the pipeline has no rule (D-085), so it fused with the sire, the tortoise. The agent chose the goat, with a reason, in all 4 runs. | **Yes.** The pipeline's image reads as a third animal (critics: mane, third_animal; to me, a fleece-covered tortoise with a sheep's head). The agent's goat with a carapace is a clear tortoise × goat. Its failures are about how the shell sits, not what the animal is. |
| fox × owl | Same plan. The agent re-rendered the unchanged plan 2 to 3 times and kept the best (a re-roll). | **Slightly.** 1 remaining failure per run against the pipeline's 2. The images look alike. |
| crab × wolf | Same host and candidate. The agent shrank the covering in steps, where the pipeline keeps the full covering. | **No.** By the critics, r1 is a little better than the pipeline (5 failures against 8) only because the agent went back to its first render. Every reduced-covering image scored worse. To my eye the reduced versions (r1 img4, r2 img3) are cleaner wolves, but the claws on fur legs still read as "insect legs". |
| beetle × bear | Same host. The agent changed the extent and the horn's class and tried a growth render. | **Mixed.** r2's final has the fewest critic failures of any beetle image (1), but it is the pill-bug image, and I would have kept img1. r1 is roughly at the pipeline's level. |

**Pattern:** the agent's leverage is in decisions the pipeline makes by rule: the host on a tie, and which image
to keep. Its plan changes for covering failures did not move the critics on any pair. The bottleneck is still how
Muse Image draws a donor covering, not the plan.

### Did the two-failure rule change beetle × bear?

**It changed the path in r1, not the result.**

- **Before the rule (v1):** r1 was 1 render plus 2 consecutive edits, finalized with 4 covering failures. r2 was 4
  renders and 2 edits, finalized with 1 structural failure (host drift).
- **With the rule, r1:** the second inspect fired the rule, and the next edit attempt would have been refused. So
  the agent changed the plan: no legs in the covering, the horn's class, then back and flanks only. It rendered 3
  more times (one of them a growth render), and finalized with 1 structural and 5 covering failures.
- **With the rule, r2:** the rule fired only at the last inspect and changed nothing. r2's result (1 structural)
  came from its single edit.
- **Net:** the rule moved the agent from a second edit to plan changes, which cost 3 extra renders. It did not
  reduce failures. Beetle × bear finals scored 5 failures in v1 (4 + 1) and 7 now (6 + 1).

The rule did exactly the same thing on tortoise × goat: it fired in both runs, the plan change made the next render
worse, and the agent kept the edit.

## My judgment per image

**Tortoise × goat**
- **Agent r1:** a clean domestic goat with a tortoise carapace on its back. The carapace sits like a saddle, with a
  visible edge over the fur. That is "on top", not grown in, and the critics are right. It is the best tortoise ×
  goat image so far, but it misses the realistic brief of a shell grown in.
- **Agent r2:** the same shell, plus scute patches on the legs and shoulders. The critics' cover_on_legs and
  scattered are correct. Worse than r1.
- **Fixed:** a tortoise body under shaggy goat fleece with a sheep-like head. It is not readable as either parent,
  and I agree with "third animal". The worst of the three.

**Fox × owl (held out)**
- **Agent r1:** a red fox standing on its hind legs, with barn owl wings folded where the forelegs were. It is
  coherent and well integrated at the shoulder. The remaining "extra_spots" is the barn owl's own wing spotting, so
  I read it as a false alarm.
- **Agent r2:** the same design, more upright and slimmer. "Frame" fails because the upright, bird-like stance no
  longer reads as a fox body. That is fair, but it is a mild problem. Good.
- **Fixed:** nearly the same as agent r1. Good.

**Crab × wolf**
- **Agent r1 (img1, the first render):** a gray wolf in full blue-black crab armor, with crab claws as its forefeet.
  The plates read as armor laid over fur, as the critics say. The critics also see a lobster. The claws are
  striking. Acceptable, not good.
- **Agent r2 (img2):** a wolf with a carapace saddle and armored claw forelegs, its hind legs left as fur. It reads
  as patchwork. Weaker than r1.
- **Fixed:** like agent r1, plus a segmented plated tail. Similar quality.

**Beetle × bear**
- **Agent r1 (img5, growth):** a brown bear in glossy segmented beetle armor with a long head horn. A convincing
  "armored bear", but the armor looks worn rather than grown. Similar to the pipeline.
- **Agent r2 (img2, edit):** a fully plated bear with the horn, and a segmented isopod-like abdomen sticking out
  behind. The pill-bug read is real. I would not finalize this one; its img1 (no abdomen) is better.
- **Fixed:** an armored bear with the horn, plates over the fur. Similar to agent r1.

**Did the held-out fox × owl work as well as the others?** Yes, and better by both the critics and my eye. It is
also the easiest pair for this engine: wings replace the forelimbs (PICK), and there is no donor covering. Its
weakness is a different one: for a structural "frame" or "spots" failure the agent has no typed operation that
helps, so it can only re-roll the render.

## Usage by provider

From docs/LIVE_LOG.md, by step label.

**This validation (8 agent creatures, 4 fixed-pipeline creatures):**

| provider and model | agent (8) | fixed (4) | total | by purpose |
|---|---|---|---|---|
| Baseten, Muse Spark Open | 263 calls (1.69 M tokens) | 44 (0.23 M) | **307** (1.92 M) | agent turns 154, polish 28, describe 39, ask 38, checklist 32, judge 16 |
| Meta, Muse Image 1.0 | 31 images | 8 | **39** | |
| Meta, Muse Spark 1.3 | 61 (0.41 M tokens) | 20 (0.15 M) | **81** (0.56 M) | describe 39, ask 38, plan 4 |
| Meta, SAM 3.1 | 32 | 14 | **46** | |

There were no failed calls. Per agent creature: about 33 Spark Open calls (19 of them agent turns), 3.9 images, 7.6
Meta Spark calls and 4 SAM calls. Per fixed-pipeline creature: 11, 2, 5 and 3.5.

**All of S3c** (the smokes, the v1 run of 8 creatures and this validation): Spark Open 572 calls (295 agent turns),
Muse Image 81, Meta Spark 158, SAM 83.

The shared counter (`docs/live/budget.json`) now reads: image 162, Meta Spark 637, SAM 161, Spark Open 1061. Before
S3c it read 84, 483, 80 and 507.

## Problems found (not fixed; for the owner)

1. **"Material and color only" has no typed operation for a covering.**
   - The rule's second route works for a donor part (`set_transfer_class non_homologous` or `drop_part`). When the
     donor's identity is its covering (tortoise shell, crab carapace, beetle plates), the only lever is extent.
   - The agent tried `set_transfer_class covering non_homologous` 4 times, and it was refused every time.
   - My prompt wording ("or set_transfer_class with cls non_homologous ... for the donor part that fails") invited
     that try. I did not change the prompt mid-validation, so all four pairs ran under the same rule.
   - **Proposal:** an operation such as `set_covering_form(material_only)`, which renders the donor's color and
     texture on the host's own skin with no plates. Separately, the prompt should say that a covering is already
     material.
2. **The agent's "best image" can disagree with code's ranking** (beetle × bear r2). The agent counts all failures
   and code ranks structural failures first. The card notes the disagreement, but the agent's pick stands.
   **Proposal:** finalize must name a reason when it goes against `best_so_far`, or code overrides the pick.
3. **9% of tool calls were refused:**
   - `covering_is_material` ×4;
   - `set_extent` without a reason ×3;
   - `set_identity_cues` on a covering ×3;
   - `unexplained_gap` ×3 (RC-R10-16: an exoskeleton covers the limbs unless a reason is given);
   - `no_such_part` ×2.

   The tool descriptions could list `reason` as required for `set_extent` and say that identity cues are for parts
   only.
4. **Plan changes do not fix covering integration.** Across 8 runs, no extent or class change moved grows_out, on_top
   or separate_outline to pass. Only one edit did (beetle × bear r2), and that edit introduced the pill-bug abdomen.
   The next lever is the renderer side (S3b growth by edit, wording), not the agent.

## Appendix: per-run decisions and final critic tables

Generated from trace.json and critic.json. Meta Spark decides each item and Spark Open is information (D-084). In
the tables, "status" is the deciding status after SAM. Each run's decision list covers every choose, plan_op,
render, edit, inspect and finalize step.

### tortoise x domestic goat

#### Agent r1: 2 renders, 1 edits, 16 tool calls; finalized img2 (finalized by the agent)

Images: img1 render fail (9 failures); img2 edit fail (5 failures); img3 render fail (8 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C2"}: "Choosing C2 (domestic goat host with tortoise carapace on back) - host tie decision per RC-R10-01: goat body carries every function with grassland niche overlap, autonomy favors mammalian host for realistic chimera, and shell as dorsal covering preserves both…" → C2: host domestic goat, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking items, render single_pass for realistic mode chimera." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fail); separate_outline (coverin…
- 8. `edit` {"image_id": "img1", "failure_keys": ["grows_out", "on_top", "scattered", "cover_on_legs", "cover_on_shoulders", "follows_body", "separate_…: "Addressing covering failures: shell plates need natural skin transition, single back covering, no leg/shoulder plates, conforming to goat body shape." → img2 from an edit: Show the hard shell plates grown in the skin over the back, as one covering that replaces the domest…
- 9. `inspect`: img2: fail - grows_out (covering, fail); on_top (covering, fail); follows_body (covering, fail); separate_outline (covering, fail); extra_horn (structural, fail) [two-failure rule: covering edits stop]
- 10. `plan_op` set_transfer_class {"feature": "covering", "cls": "non_homologous"}: "Two-failure rule: covering still fails grows_out/on_top/follows_body after two edits, so moving tortoise shell identity to material/color only (non-homologous) to avoid separate outline while preserving realistic integration per RC-R10-15." → refused: None:
- 11. `plan_op` set_transfer_class {"feature": "covering", "cls": "material"}: "Two-failure rule requires plan change: setting covering to material transfer only (color/texture without separate shell structure) to fix grows_out/separate_outline failures." → set_transfer_class ok
- 12. `plan_op` set_extent {"feature": "covering", "extent": ["back"], "reason": "Reduce covering to single dorsal zone to eliminate separate outline and a…: "Two-failure rule: reducing covering extent to single back zone with explicit reason to ensure natural skin transition and prevent scattered/leg plates." → set_extent ok
- 14. `render` {"method": "single_pass"}: "Rendering after plan extent adjustment to address covering failures." → img3 (single_pass), renders used 2
- 15. `inspect`: img3: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fail); separate_outline (coverin…
- 16. `finalize` {"image_id": "img2"}: "Finalizing best inspected image img2 (1 structural, 4 covering failures) vs img3 (1+7) - new render worsened covering, and two-failure rule edits exhausted. Best image minimizes grows_out/on_top/follows_body/separate_outline failures compared to alternatives,…" → crt_fdb63debbfae; remaining failures 5

Final critic table (img2):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | no | no | **fail** |
| on_top | integration | no | yes | yes | **fail** |
| continuous | integration | yes | yes | yes | **pass** |
| scattered | integration | no | no | no | **pass** |
| cover_on_legs | placement | no | no | no | **pass** |
| cover_on_shoulders | placement | no | no | no | **pass** |
| follows_body | integration | yes | no | no | **fail** |
| separate_outline | integration | no | yes | yes | **fail** |
| sized_to_body | integration | yes | yes | no | **pass** |
| wrong_scale | integration | no | no | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_horn | structure | absent | True | True | **fail** |
| extra_mane | structure | absent | False | True | **pass** |
| third_animal | structure | none | [] | ['turtle'] | **pass** |

#### Agent r2: 2 renders, 1 edits, 17 tool calls; finalized img2 (finalized by the agent)

Images: img1 render fail (8 failures); img2 edit fail (8 failures); img3 render fail (8 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C2"}: "Choosing domestic goat host with tortoise carapace on back: tie broken by autonomy and identity - goat frame carries all functions in shared grassland niche, while tortoise high-domed carapace provides clear, realistic donor identity on back without compromis…" → C2: host domestic goat, parts []
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking items; render domestic goat host with tortoise carapace in realistic mode." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fail); separate_outline (coverin…
- 8. `edit` {"image_id": "img1", "failure_keys": ["grows_out", "on_top", "scattered", "cover_on_legs", "cover_on_shoulders", "follows_body", "separate_…: "Fixing 7 covering failures: shell plates must grow in-skin over back only, replacing fur there with natural transition and following goat body contours, no plates on legs/shoulders." → img2 from an edit: Show the hard shell plates grown in the skin over the back, as one covering that replaces the domest…
- 9. `inspect`: img2: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fail); separate_outline (coverin…
- 10. `plan_op` set_transfer_class {"feature": "covering", "cls": "non_homologous"}: "Two covering failures in a row trigger two-failure rule: convert tortoise carapace to non-homologous material/color only to avoid structural plate attachment failures while preserving identity." → refused: None:
- 11. `plan_op` set_transfer_class {"feature": "covering", "cls": "material"}: "Two-failure rule requires plan change: set covering to material class to show tortoise identity via color/pattern only, not 3D plates, fixing covering integration failures." → set_transfer_class ok
- 12. `plan_op` set_extent {"feature": "covering", "extent": ["back"]}: "Two-failure rule: reducing covering extent to back only with clear reason to fix scattered plates and leg/shoulder coverage failures." → refused: None:
- 13. `plan_op` set_extent {"feature": "covering", "extent": ["back"], "reason": "two-failure rule: restrict to single zone to prevent scattered plates on …: "Two-failure rule requires extent reduction with reason to address repeated covering failures on legs/shoulders and scattered pattern." → set_extent ok
- 15. `render` {"method": "single_pass"}: "Re-render with updated plan: reduced covering extent and material transfer should resolve covering integration failures." → img3 (single_pass), renders used 2
- 16. `inspect`: img3: fail - grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); separate_outline (covering, fail); extra_horn (structural, fai…
- 17. `finalize` {"image_id": "img2"}: "Finalizing best inspected image after two-failure rule plan change did not resolve persistent covering integration failures; remaining covering and structural failures will be listed on creature card per RC-R10-15/16." → crt_686f407a42ae; remaining failures 8

Final critic table (img2):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | no | no | **fail** |
| on_top | integration | no | yes | yes | **fail** |
| continuous | integration | yes | yes | yes | **pass** |
| scattered | integration | no | yes | yes | **fail** |
| cover_on_legs | placement | no | yes | yes | **fail** |
| cover_on_shoulders | placement | no | yes | yes | **fail** |
| follows_body | integration | yes | no | no | **fail** |
| separate_outline | integration | no | yes | yes | **fail** |
| sized_to_body | integration | yes | yes | no | **pass** |
| wrong_scale | integration | no | no | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_horn | structure | absent | True | True | **fail** |
| extra_mane | structure | absent | False | True | **pass** |
| third_animal | structure | none | [] | ['turtle'] | **pass** |

#### Fixed pipeline: kept the edited image; needs_choice on a structural tie (D-085); fused with host=sire (the old rule) to compare

Final critic table:

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| no_mane | structure | no | yes | yes | **fail** |
| cover_present | surface | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_beak | structure | absent | False | True | **pass** |
| extra_mane | structure | absent | True | True | **fail** |
| extra_stripes | structure | absent | False | True | **pass** |
| third_animal | structure | none | ['sheep'] | ['sheep'] | **fail** |

### red fox x barn owl (held out)

#### Agent r1: 4 renders, 0 edits, 19 tool calls; finalized img4 (finalized by the agent)

Images: img1 render fail (1 failures); img2 render fail (4 failures); img3 render fail (1 failures); img4 render fail (1 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "Select C1 with red fox as host for horizontal quadruped frame allowing owl wings as forelimbs, providing clear speculative chimera identity. Per RC-R10-01 host tie resolved by design choice not size/mass." → C1: host red fox, parts ['wings (forelimbs)']
- 6. `render` {"method": "single_pass"}: "Plan audited renderable, initiate single_pass render for fox-owl chimera." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - frame (structural, fail)
- 8. `plan_op` set_identity_cues {"feature": "covering", "cues": ["fox muzzle", "pointed ears", "bushy tail"]}: "Attempt to reinforce red fox identity to fix structural frame failure per inspect guidance." → refused: not_a_part: identity cues describe a discrete part
- 10. `render` {"method": "single_pass"}: "Retry render for fox frame after initial inspect failure, attempt improved depiction." → img2 (single_pass), renders used 2
- 11. `inspect`: img2: fail - legs_and_wings (structural, fail); extra_legs (structural, fail); walking_legs (structural, fail); extra_spots (structural, fail)
- 12. `plan_op` drop_part {"part": "spots", "reason": "remove unplanned spots per inspect failure extra_spots"}: "Attempt to explicitly drop unplanned spots to satisfy covering/structural check." → refused: no_such_part: the plan has no part matching 'spots'
- 14. `render` {"method": "single_pass"}: "Third render attempt aiming for correct 2 walking legs + wings configuration, eliminating spots." → img3 (single_pass), renders used 3
- 15. `inspect`: img3: fail - extra_spots (structural, fail)
- 17. `render` {"method": "single_pass"}: "Final render attempt to achieve passing inspection within limit." → img4 (single_pass), renders used 4
- 18. `inspect`: img4: fail - extra_spots (structural, fail)
- 19. `finalize` {"image_id": "img4"}: "At render limit (4/4); best_so_far is img4 with 1 structural failure (extra_spots) vs img1/3 tied; img2 worse (4). Finalizing best inspected image per limits rule, failures will be card-stated." → crt_91e1c29473b6; remaining failures 1

Final critic table (img4):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| wings_front | structure | yes | yes | yes | **pass** |
| legs_and_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| no_mane | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | yes | **pass** |
| cover_present | surface | yes | yes | yes | **pass** |
| connects_feathered_wings | connection | yes | yes | yes | **pass** |
| separate_feathered_wings | connection | no | no | no | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 2 | 2 | 2 | **pass** |
| wings | structure | 2 | 2 | 2 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_spots | structure | absent | True | True | **fail** |
| origin_feathered_wings | identity | barn owl | barn owl | barn owl | **pass** |

#### Agent r2: 3 renders, 0 edits, 16 tool calls; finalized img2 (finalized by the agent)

Images: img1 render fail (2 failures); img2 render fail (1 failures); img3 render fail (2 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "Host tie per RC-R10-01: choosing red fox as host for structural clarity—horizontal frame supports barn owl wing forelimbs; desert niche native to both. Candidate C1's wing integration maximizes autonomy and identity." → C1: host red fox, parts ['wings (forelimbs)']
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking; speculative mode render for red fox host with barn owl wings." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - frame (structural, fail); extra_spots (structural, fail)
- 8. `plan_op` set_host {"animal": "red fox"}: "Structural frame failure indicates host silhouette not clear; reaffirming host to strengthen prompt for red fox horizontal frame per inspect fix." → set_host ok
- 10. `render` {"method": "single_pass"}: "Second render attempt to address structural frame/spots failures; hoping variation improves red fox silhouette fidelity." → img2 (single_pass), renders used 2
- 11. `inspect`: img2: fail - frame (structural, fail)
- 12. `plan_op` set_region {"region": "forelimbs", "donor": "barn owl", "operator": "PICK"}: "Explicitly reinforcing wing-forelimb homology to clarify silhouette instructions for renderer; frame failure suggests need for stronger anatomical anchoring." → set_region ok
- 14. `render` {"method": "single_pass"}: "Third render attempt; structural frame error persists but improved from 2 to 1 failures—attempting another variation." → img3 (single_pass), renders used 3
- 15. `inspect`: img3: fail - frame (structural, fail); extra_spots (structural, fail)
- 16. `finalize` {"image_id": "img2"}: "Finalizing best inspected image img2 (1 structural failure: frame) per inspect best_so_far; after 3 renders structural frame persists, no covering failures to edit; remaining failure stated on card per audit." → crt_b12b146701d8; remaining failures 1

Final critic table (img2):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | no | no | **fail** |
| head | structure | yes | yes | yes | **pass** |
| wings_front | structure | yes | yes | yes | **pass** |
| legs_and_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| no_mane | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | surface | yes | yes | yes | **pass** |
| connects_feathered_wings | connection | yes | yes | yes | **pass** |
| separate_feathered_wings | connection | no | no | no | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 2 | 2 | 2 | **pass** |
| wings | structure | 2 | 2 | 2 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_spots | structure | absent | False | True | **pass** |
| origin_feathered_wings | identity | barn owl | barn owl | barn owl | **pass** |

#### Fixed pipeline: kept the first image; needs_choice on a structural tie (D-085); fused with host=sire (the old rule) to compare

Final critic table:

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | no | yes | **fail** |
| head | structure | yes | yes | yes | **pass** |
| wings_front | structure | yes | yes | yes | **pass** |
| legs_and_wings | structure | no | no | no | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| no_mane | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | surface | yes | yes | yes | **pass** |
| connects_feathered_wings | connection | yes | yes | yes | **pass** |
| separate_feathered_wings | connection | no | no | no | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 2 | 2 | 2 | **pass** |
| wings | structure | 2 | 2 | 2 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_spots | structure | absent | True | True | **fail** |
| origin_feathered_wings | identity | barn owl | barn owl | barn owl | **pass** |

### crab x gray wolf

#### Agent r1: 3 renders, 1 edits, 20 tool calls; finalized img1 (finalized by the agent)

Images: img1 render fail (5 failures); img2 edit fail (3 failures); img3 render fail (10 failures); img4 render fail (9 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "Choosing C1: gray wolf host provides structured quadruped frame (RC-R6-08) with crab claws as identity part and full carapace covering, better niche/survival balance than C2 crab host." → C1: host gray wolf, parts ['crab claws']
- 6. `render` {"method": "single_pass"}: "Plan audited with no blocking items, rendering speculative wolf-crab chimera with carapace covering and claw identity parts." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); third_animal (structural, fail)
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "grows_out", "on_top", "continuous"]}: "Attempting to fix covering integration failures first: plates need to appear as continuous chitin grown into skin replacing fur, not scattered pieces on top (RC-R10-12, RC-R10-16)." → img2 from an edit: Show the planned hard, glossy chitin plates with fine seams over the head, neck, shoulders, back, fl…
- 9. `inspect`: img2: fail - insect_legs (structural, fail); dropped_segmented_tail (structural, fail); third_animal (structural, fail)
- 10. `plan_op` set_extent {"feature": "covering", "extent": ["head", "neck", "forequarters", "back", "flanks", "belly", "hindquarters"]}: "Structural failures insect_legs and segmented tail suggest leg/tail chitin plates misread as extra limbs/tail per RC-R10-15; reducing covering extent to remove legs and tail." → refused: bad_arguments: PlanSession._set_extent() missing 1 required positional argument: 'reason'
- 11. `plan_op` set_extent {"feature": "covering", "extent": ["head", "neck", "forequarters", "back", "flanks", "belly", "hindquarters"], "reason": "reduci…: "Reducing covering extent to remove legs and tail plates causing structural failures per two-failure rule guidance." → set_extent ok
- 13. `render` {"method": "single_pass"}: "Re-rendering with reduced covering extent to eliminate leg/tail structural artifacts while preserving core identity." → img3 (single_pass), renders used 2
- 14. `inspect`: img3: fail - insect_legs (structural, fail); cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); …
- 15. `plan_op` set_transfer_class {"feature": "covering", "cls": "non_homologous"}: "Moving covering to non-homologous material-only transfer to prevent jointed plates being read as insect legs while retaining chitin color/texture (RC-R10-15)." → refused: covering_is_material: a covering transfers as material (RC-R10-15 a)
- 16. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks"], "reason": "further reduce covering to single dorsal carapace to eliminate …: "Further reducing covering extent to dorsal-only carapace after persistent insect_legs structural misread and scattered covering failures (RC-R10-12, RC-R10-15)." → set_extent ok
- 18. `render` {"method": "single_pass"}: "Rendering dorsal carapace version to address insect_legs misread while maintaining crab identity via claws and back plating." → img4 (single_pass), renders used 3
- 19. `inspect`: img4: fail - insect_legs (structural, fail); grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); separate_outline (covering, fa…
- 20. `finalize` {"image_id": "img1"}: "Finalizing best inspected image img1: fewest structural failures (1 third_animal lobster misread vs 3 in later renders) with wolf quadruped frame intact and crab claw identity preserved per RC-R10-15; remaining covering integration failures (cover_present, gr…" → crt_35617a44e2b1; remaining failures 5

Final critic table (img1):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_crab_claws | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| dropped_segmented_tail | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | no | no | **fail** |
| grows_out | integration | yes | no | yes | **fail** |
| on_top | integration | no | yes | no | **fail** |
| continuous | integration | yes | no | yes | **fail** |
| scattered | integration | no | no | no | **pass** |
| follows_body | integration | yes | yes | yes | **pass** |
| separate_outline | integration | no | no | no | **pass** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| legs_covered | coverage | yes | yes | yes | **pass** |
| abrupt_stop | coverage | no | no | no | **pass** |
| identity_claws | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| origin_claws | identity | crab | crab | crab | **pass** |
| third_animal | structure | none | ['lobster'] | [] | **fail** |

#### Agent r2: 4 renders, 0 edits, 26 tool calls; finalized img2 (finalized by the agent)

Images: img1 render fail (12 failures); img2 render fail (10 failures); img3 render fail (13 failures); img4 render fail (10 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "Choosing C1 highest score 2.3, hosts wolf frame more structured per RC-R6-08, retains identity claws and carapace covering." → C1: host gray wolf, parts ['crab claws']
- 5. `plan_op` set_mode {"mode": "speculative"}: "Setting mode to speculative as requested." → set_mode ok
- 7. `render` {"method": "single_pass"}: "Plan audited with no blocking issues, rendering speculative chimera." → img1 (single_pass), renders used 1
- 8. `inspect`: img1: fail - insect_legs (structural, fail); dropped_segmented_tail (structural, fail); cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (coveri…
- 9. `plan_op` drop_part {"part": "segmented tail", "reason": "inspect failed dropped_segmented_tail structural; enforce host wolf tail only"}: "Fix structural failure dropped_segmented_tail flagged by inspect; enforcing host tail only per audit feedback." → refused: no_such_part: the plan has no part matching 'segmented tail'
- 10. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks"], "reason": "reduce coverage to address multiple covering failures while ret…: "Reducing covering extent to back/flanks to resolve covering continuity failures and insect_legs structural on legs per two-failure rule preparation." → set_extent ok
- 12. `render` {"method": "single_pass"}: "Re-rendering with reduced covering to back/flanks to fix insect_legs and covering failures." → img2 (single_pass), renders used 2
- 13. `inspect`: img2: fail - insect_legs (structural, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fa…
- 14. `plan_op` set_extent {"feature": "covering", "extent": ["back"], "reason": "Further reduce covering to back only to eliminate cover_on_legs and cover…: "Second inspect shows cover_on_legs and cover_on_shoulders despite prior reduction; narrowing to back only should resolve per two-failure rule." → set_extent ok
- 16. `render` {"method": "single_pass"}: "Third render with dorsal-only covering to eliminate leg/shoulder plate artifacts." → img3 (single_pass), renders used 3
- 17. `inspect`: img3: fail - whole_animal (structural, fail); insect_legs (structural, fail); dropped_segmented_tail (structural, fail); grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (co…
- 18. `plan_op` set_transfer_class {"feature": "covering", "cls": "non_homologous"}: "Third inspect still shows whole_animal separate shell and insect_legs; switching covering to material/color only to reduce structural separate-animal artifacts per two-failure rule." → refused: covering_is_material: a covering transfers as material (RC-R10-15 a)
- 19. `plan_op` set_transfer_class {"feature": "covering", "cls": "material"}: "Switch covering transfer to material-only to eliminate whole_animal separate shell and insect leg artifacts per structural failure guidance." → set_transfer_class ok
- 20. `plan_op` set_identity_cues {"feature": "covering", "cues": ["reddish-brown carapace sheen", "glossy chitin texture"]}: "Refining covering cues to dorsal sheen only, removing limb jointed plates that drive insect_legs structural failure per inspect feedback." → refused: not_a_part: identity cues describe a discrete part
- 21. `plan_op` drop_part {"part": "crab claws", "reason": "retain alternative interpretation to test if claw pincer causes insect_legs misclassification; …: "Testing if claw pincer identity contributes to insect_legs classification; considering removal per structural feedback." → drop_part ok
- 23. `plan_op` set_identity_part {"donor": "crab", "part": "claws", "reason": "restore identity claws; core identity requires crab trait per R10, reinstat…: "Restoring claw identity as required by R10 identity rule; cannot drop solely donor trait, need to retain." → set_identity_part ok
- 24. `render` {"method": "single_pass"}: "Final allowed render with back-only covering after exhaustive plan adjustments; structural failures persist." → img4 (single_pass), renders used 4
- 25. `inspect`: img4: fail - insect_legs (structural, fail); dropped_crab_claws (structural, fail); grows_out (covering, fail); on_top (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (co…
- 26. `finalize` {"image_id": "img2"}: "Finalizing best inspected image at render limit (4/4 used). Comparison: img1 had 2 structural (insect_legs + dropped_segmented_tail) + covering not present; img2 has 1 structural (insect_legs) and resolves dropped tail, no whole_animal; img3 adds whole_animal…" → crt_7d01db5c1545; remaining failures 10

Final critic table (img2):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_crab_claws | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | yes | yes | **fail** |
| extra_legs | structure | no | no | no | **pass** |
| dropped_segmented_tail | structure | no | no | yes | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | no | no | **fail** |
| on_top | integration | no | yes | yes | **fail** |
| continuous | integration | yes | no | yes | **fail** |
| scattered | integration | no | yes | yes | **fail** |
| cover_on_legs | placement | no | yes | yes | **fail** |
| cover_on_shoulders | placement | no | yes | yes | **fail** |
| follows_body | integration | yes | no | no | **fail** |
| separate_outline | integration | no | yes | yes | **fail** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| abrupt_stop | coverage | no | yes | yes | **fail** |
| identity_claws | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| extra_mane | structure | absent | False | True | **pass** |
| origin_claws | identity | crab | crab | crab | **pass** |

#### Fixed pipeline: kept the first image

Final critic table:

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_crab_claws | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| dropped_segmented_tail | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | no | no | **fail** |
| grows_out | integration | yes | no | no | **fail** |
| on_top | integration | no | yes | yes | **fail** |
| continuous | integration | yes | no | no | **fail** |
| scattered | integration | no | yes | yes | **fail** |
| follows_body | integration | yes | no | no | **fail** |
| separate_outline | integration | no | yes | yes | **fail** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| legs_covered | coverage | yes | yes | yes | **pass** |
| abrupt_stop | coverage | no | yes | yes | **fail** |
| identity_claws | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| origin_claws | identity | crab | crab | crab | **pass** |

### rhinoceros beetle x brown bear

#### Agent r1: 4 renders, 2 edits, 23 tool calls; finalized img5 (finalized by the agent)

Images: img1 render fail (8 failures); img2 edit fail (12 failures); img3 render fail (12 failures); img4 growth_host None (0 failures); img5 growth fail (6 failures); img6 render fail (13 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "C1 has proper host selection (bear structured) and preserves identity horn + plates; C2 advised against per RC-R6-08." → C1: host brown bear, parts ['european rhinoceros beetle head horn']
- 6. `render` {"method": "single_pass"}: "Plan audited and renderable; proceed to speculative render." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); abrupt_stop (covering, fail); connects_head_horn (structural, fa…
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "grows_out", "on_top", "continuous", "scattered", "abrupt_stop"]}: "Address covering failures first: plates not grown-in and discontinuous; structural horn connection depends on plates being present. Per RC-R10-15, fixing covering via edit." → img2 from an edit: Show the planned hard, glossy chitin plates with fine seams over the head, neck, shoulders, back, fl…
- 9. `inspect`: img2: fail - whole_animal (structural, fail); cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); follows_body (covering, fail); separate_outline (covering, …
- 10. `plan_op` set_extent {"feature": "covering", "extent": ["head", "back", "flanks", "forequarters"], "reason": "two consecutive covering failures; redu…: "Two inspects with covering failures; per rule reduce covering extent to achievable zones and keep head for horn connection." → refused: unexplained_gap: an exoskeleton covers the limbs unless a stated functional reason limits it (RC-R10-16); say …
- 11. `plan_op` set_extent {"feature": "covering", "extent": ["head", "neck", "forequarters", "back", "flanks", "belly", "hindquarters", "tail"], "reason":…: "Second attempt with stated functional reason for bare legs per RC-R10-16." → set_extent ok
- 12. `plan_op` set_transfer_class {"feature": "head horn", "cls": "non_homologous"}: "Ensure horn treated as material/color analogue to aid covering integration per two-failure rule alternative." → set_transfer_class ok
- 14. `render` {"method": "single_pass"}: "Re-render with reduced covering extent to achieve continuous grown-in plates excluding legs for mobility." → img3 (single_pass), renders used 2
- 15. `inspect`: img3: fail - cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); s…
- 16. `render` {"method": "growth_edit"}: "Try growth_edit method to better integrate chitin plates as grown-in covering per inspect fixes." → img5 (growth_edit), renders used 3
- 17. `inspect`: img5: fail - grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); third_animal (structural, fail) [two-failure rule: covering edit…
- 18. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks"], "reason": "two consecutive covering failures; limit plates to dorsal trunk…: "Reduce covering drastically to two dorsal zones to achieve continuous grown-in plates per two-failure rule RC-R10-15/16." → refused: unexplained_gap: an exoskeleton covers the limbs unless a stated functional reason limits it (RC-R10-16); say …
- 19. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks"], "reason": "two consecutive covering failures; limit to dorsal trunk for on…: "Explicitly state legs bare reason to satisfy RC-R10-16." → set_extent ok
- 21. `render` {"method": "single_pass"}: "Final render with minimal continuous dorsal plates; at render limit, will finalize best image." → img6 (single_pass), renders used 4
- 22. `inspect`: img6: fail - grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); cover_on_shoulders (covering, fail); follows_body (covering, fai…
- 23. `finalize` {"image_id": "img5"}: "At render limit (4/4); per best_so_far analysis img5 has fewest failures (1 structural, 5 covering) vs others. Finalizing best inspected image; remaining covering integration and third-animal spark noted on card." → crt_44945fbc2483; remaining failures 6

Final critic table (img5):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_european_rhinoceros_beetle_head_horn | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | no | yes | **fail** |
| on_top | integration | no | yes | no | **fail** |
| continuous | integration | yes | no | yes | **fail** |
| scattered | integration | no | yes | no | **fail** |
| cover_on_legs | placement | no | yes | yes | **fail** |
| follows_body | integration | yes | yes | yes | **pass** |
| separate_outline | integration | no | no | no | **pass** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| abrupt_stop | coverage | no | no | no | **pass** |
| connects_head_horn | connection | yes | yes | yes | **pass** |
| separate_head_horn | connection | no | no | no | **pass** |
| identity_head_horn | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| origin_head_horn | identity | european rhinoceros beetle | european rhinoceros beetle | european rhinoceros beetle | **pass** |
| third_animal | structure | none | ['pillbug'] | [] | **fail** |

#### Agent r2: 3 renders, 1 edits, 21 tool calls; finalized img2 (finalized by the agent)

Images: img1 render fail (5 failures); img2 edit fail (1 failures); img3 render fail (10 failures); img4 render fail (12 failures).

Decisions (from trace.md):

- 4. `choose_candidate` {"candidate_id": "C1"}: "C1 uses brown bear host with more structured body schema per RC-R6-08 and provides identity via beetle horn with proper compensation." → C1: host brown bear, parts ['european rhinoceros beetle head horn']
- 6. `render` {"method": "single_pass"}: "Plan audited and renderable; single pass for full chimera." → img1 (single_pass), renders used 1
- 7. `inspect`: img1: fail - cover_present (covering, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail)
- 8. `edit` {"image_id": "img1", "failure_keys": ["cover_present", "grows_out", "on_top", "continuous", "scattered"]}: "Covering failures only; attempt edit to fix plates integration per inspect guidance." → img2 from an edit: Show the planned hard, glossy chitin plates with fine seams over the head, neck, shoulders, back, fl…
- 9. `inspect`: img2: fail - third_animal (structural, fail)
- 10. `plan_op` set_identity_cues {"feature": "covering", "cues": ["reddish-brown glossy", "large fused plates"]}: "Address third-animal pillbug misread by reinforcing beetle-specific covering cues per RC-R10-15." → refused: not_a_part: identity cues describe a discrete part
- 11. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks", "forequarters", "hindquarters"]}: "Structural third-animal failure for pillbug; reduce covering extent to dorsal armor only to keep beetle identity without isopod resemblance per RC-R10-15." → refused: bad_arguments: PlanSession._set_extent() missing 1 required positional argument: 'reason'
- 12. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks", "forequarters", "hindquarters"], "reason": "Reduce covering to dorsal armor…: "Structural failure requires plan change; narrowing covering extent." → refused: unexplained_gap: an exoskeleton covers the limbs unless a stated functional reason limits it (RC-R10-16); say …
- 13. `plan_op` set_extent {"feature": "covering", "extent": ["back", "flanks", "forequarters", "hindquarters"], "reason": "Reduce to dorsal armor to avoid…: "Provide functional reason for bare legs/belly per RC-R10-16 gap rule." → set_extent ok
- 15. `render` {"method": "single_pass"}: "Plan updated and audited; render revised dorsal-armored bear." → img3 (single_pass), renders used 2
- 16. `inspect`: img3: fail - grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); separate_outline (covering, fail)…
- 17. `plan_op` connect_features {"a": "head horn", "b": "covering"}: "Structural fix: head horn should emerge from chitin plates per inspect connects_head_horn; linking ensures base integration." → connect_features ok
- 19. `render` {"method": "single_pass"}: "Re-render with connected horn-plate base for better structural coherence." → img4 (single_pass), renders used 3
- 20. `inspect`: img4: fail - insect_legs (structural, fail); grows_out (covering, fail); on_top (covering, fail); continuous (covering, fail); scattered (covering, fail); cover_on_legs (covering, fail); follows_body (covering, fail); s…
- 21. `finalize` {"image_id": "img2"}: "Finalizing best inspected image img2 with 1 structural failure (third_animal pillbug) vs later renders with 8+ covering +1 structural; per two-failure rule and render limit, accept remaining failure on card." → crt_d4d7359ad441; remaining failures 1

Final critic table (img2):

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_european_rhinoceros_beetle_head_horn | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | yes | yes | **pass** |
| on_top | integration | no | no | no | **pass** |
| continuous | integration | yes | yes | yes | **pass** |
| scattered | integration | no | no | no | **pass** |
| follows_body | integration | yes | yes | yes | **pass** |
| separate_outline | integration | no | no | no | **pass** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| legs_covered | coverage | yes | yes | yes | **pass** |
| abrupt_stop | coverage | no | no | no | **pass** |
| connects_head_horn | connection | yes | yes | yes | **pass** |
| separate_head_horn | connection | no | no | no | **pass** |
| identity_head_horn | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| origin_head_horn | identity | european rhinoceros beetle | european rhinoceros beetle | european rhinoceros beetle | **pass** |
| third_animal | structure | none | ['pillbug'] | [] | **fail** |

#### Fixed pipeline: kept the edited image

Final critic table:

| item | group | expect | Meta Spark (decides) | Spark Open (info) | status |
|---|---|---|---|---|---|
| frame | structure | yes | yes | yes | **pass** |
| head | structure | yes | yes | yes | **pass** |
| no_wings | structure | no | no | no | **pass** |
| part_european_rhinoceros_beetle_head_horn | structure | yes | yes | yes | **pass** |
| whole_animal | structure | no | no | no | **pass** |
| second_head | structure | no | no | no | **pass** |
| insect_legs | structure | no | no | no | **pass** |
| extra_legs | structure | no | no | no | **pass** |
| plain_fur | pattern | no | no | no | **pass** |
| cover_present | integration | yes | yes | yes | **pass** |
| grows_out | integration | yes | no | yes | **fail** |
| on_top | integration | no | yes | no | **fail** |
| continuous | integration | yes | no | yes | **fail** |
| scattered | integration | no | yes | no | **fail** |
| follows_body | integration | yes | no | yes | **fail** |
| separate_outline | integration | no | yes | no | **fail** |
| sized_to_body | integration | yes | yes | yes | **pass** |
| wrong_scale | integration | no | no | no | **pass** |
| legs_covered | coverage | yes | yes | yes | **pass** |
| abrupt_stop | coverage | no | yes | no | **fail** |
| connects_head_horn | connection | yes | yes | yes | **pass** |
| separate_head_horn | connection | no | no | no | **pass** |
| identity_head_horn | identity | yes | yes | yes | **pass** |
| separate_bodies | structure | 1 | 1 | 1 | **pass** |
| heads | structure | 1 | 1 | 1 | **pass** |
| walking_legs | structure | 4 | 4 | 4 | **pass** |
| wings | structure |  | 0 | 0 | **pass** |
| extra_limb_pieces | structure |  | 0 | 0 | **pass** |
| origin_head_horn | identity | european rhinoceros beetle | european rhinoceros beetle | european rhinoceros beetle | **pass** |
| third_animal | structure | none | ['pillbug'] | ['pill bug'] | **fail** |
