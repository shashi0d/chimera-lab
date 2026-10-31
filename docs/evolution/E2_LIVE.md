# E2-live: first live run of the evolution engine

Date: 2026-10-31. Branch: `evo`. The `evo` → `main` merge in step 0 was skipped, as the user asked.
Scope: the 4 worked examples only, `/fuse` code path, parents by name, seed 0, one image each. No evolve runs.
Outputs: `docs/evolution/live/e2/<example>/` contains `image.webp`, `plan.json`, `prompt_compiled.txt`,
`prompt_final.txt`, `critic.json` (critic answers, mask stats, scores), `sam_mask.png` and `calls.json`.
Totals are in `summary.json`. Key-free raw request/response pairs are in `raw/`.
Script: `scripts/e2_live_run.py`.

## The 4 images

| # | Image | Route | Host | Label | Quality | Critic (full image) | Critic (192 px thumbnail) |
|---|---|---|---|---|---|---|---|
| 1 | ![](live/e2/1_donkey_x_horse/image.webp) | hybrid, known pair `mule` | horse | real hybrid precedent | **0.45** | named **donkey, zebra**; **1 creature**. "A donkey-like animal with faint zebra stripes stands in profile." | donkey; 1 creature |
| 2 | ![](live/e2/2_lion_x_tiger/image.webp) | hybrid, known pair `liger` | lion | real hybrid precedent | **0.955** | named **lion, tiger**; **1 creature**. "A large tawny hybrid big cat with faint tiger stripes stands in profile." | lion, tiger; 1 creature |
| 3 | ![](live/e2/3_lion_x_eagle/image.webp) | chimera | lion | speculative chimera, no real-world precedent; non-flying wings: display or gliding only | **0.768** | named **lion, leopard, eagle**; **1 creature**. "A mythical winged creature with a lion head and spotted feline body rears up." | lion, leopard, bird; 1 creature |
| 4 | ![](live/e2/4_eagle_x_octopus/image.webp) | chimera | golden eagle | speculative chimera, no real-world precedent | **0.70** | named **eagle, octopus**; **1 creature**. "A large brown eagle with octopus tentacles growing from its lower body." | eagle, octopus; 1 creature |

Score parts (quality = 0.4 critic + 0.3 silhouette + 0.1 thumbnail + 0.2 (1 − soft penalty)):

| # | critic | silhouette | thumbnail | soft penalty | SAM prompt | SAM mask (fill, aspect, components) |
|---|---|---|---|---|---|---|
| 1 | 0.5 | **0.0** | 0.5 | 0.0 | "horse" | **empty** |
| 2 | 1.0 | 0.96 | 1.0 | 0.167 (RC-R1-11) | "lion" | 0.333, 1.16, 1 |
| 3 | 1.0 | 0.392 | 0.5 | 0.0 | "lion" | 0.364, 0.98, **2** |
| 4 | 1.0 | **0.0** | 1.0 | 0.0 | "golden eagle" | **empty** |

First plan from Muse Spark: accepted for examples 2, 3 and 4. For example 1 it was **rejected and the code skeleton was used**: the model edited a locked mule-override field (the `body` trait), which is blocked by RC-R2-03. Prompt polish changed the wording in all 4 prompts, and `accept_polish` kept all 4.

## My judgment: does each image match its plan?

1. **Donkey x horse (mule): no, only partly.** The donkey head and long ears are right, but the body reads as a donkey, not a horse-height horse frame. The "faint donkey pattern at 50 percent" came out as bold zebra-like stripes, so the critic named a zebra.
2. **Lion x tiger (liger): yes.** A large, long, tawny cat with faint stripes on the flanks and legs and almost no mane, as planned.
3. **Lion x eagle: partly.** Eagle wings in place of the forelegs, standing on the hind legs, with feather patches on the chest and neck, as planned. But it has a full lion mane, which the plan gated off, and leopard spots that come from the habitat cue ("more patterned, irregular coat markings").
4. **Eagle x octopus: yes.** A golden eagle frame with jointless tentacles in place of the tail, and octopus skin with suckers in patches on the flanks and thighs.

## Calls: predicted vs made

| | Spark | Image | SAM |
|---|---|---|---|
| Predicted per example (first plan, polish, critic, thumbnail critic / render / segment) | 4 | 1 | 1 |
| Predicted, 4 examples | 16 | 4 | 4 |
| Made in step 4, every attempt counted (`calls.json`, `LIVE_LOG.md`) | **16** | **4** | **4** |
| Retries | 0 | 0 | 0 |
| Step 3 SAM probe | 0 | 0 | 1 |
| **E2 total** | **16** | **4** | **5** |

No call failed, so the retry policy never fired. Latency per call: plan 14 to 34 s, polish 11 to 24 s, render 22 to 33 s, critic 4 to 10 s, SAM 1.1 to 4.4 s. Decoding each SAM mask locally adds a few seconds of pure-Python work.

## Budget counter (`docs/live/budget.json`, shared with L1)

| | image | spark | sam |
|---|---|---|---|
| Before E2 | 11 | 27 | 0 |
| After the step 3 probe | 11 | 27 | 1 |
| After step 4 | **15** | **43** | **5** |
| Caps for this run | 20 | 70 | 8 |

## Failures and what I did

- **No example failed**, so the "fail twice, skip" rule was never used.
- **Step 3, SAM mask format.** SAM 3.1 answered on the first call (`status: completed`, no `model_not_found` or auth error). Masks do not come back as an image. They come back as special-token text, `<|box;x1..y2;w;h|><|mask;x;y;data=H,W,~payload|>`. The payload is a box-local raster in base85, and `~` marks the "lossless" encoding, which is arithmetic-coded, so base85 plus zlib does not decode it. Meta publishes the decoder as `meta-sam-parser` (PyPI, author Meta Platforms, SAM License; the license forbids reverse engineering). Auto mode blocked the install, so I asked, and the user approved it. It is pinned at `meta-sam-parser==0.1.0` in `backend/requirements.txt`. `parse_sam_response` pastes every mask record into a full-frame binary PNG. Checked by eye: the probe mask covers the donkey exactly, including the ears, tail and legs. The recording is `backend/tests/fixtures/recorded/sam-01.json` (image `docs/live/fusions/horse_donkey.webp`, prompt "animal").
- **Empty SAM masks (examples 1 and 4).** The judge prompts SAM with the host's common name. "horse" on an image that reads as a donkey, and "golden eagle", both returned an empty message, so the silhouette score was 0. That cost 0.3 quality on both. The probe prompt "animal" worked. I did not change the judge or re-run anything: it would cost 2 more SAM calls, and the task says not to loop. **Suggested fix:** prompt SAM with "animal" (or "creature") and keep the host name only for the aspect band.
- **Silhouette calibration.** A correct standing donkey (the probe) has a mask aspect of 0.96, because the ears and neck are tall. That is below the quadruped band of 1.2 to 2.6, so it scores about 0.76. The lion x eagle mask splits into 2 components (wing tips and body), which halves its silhouette score although the critic saw 1 creature. Both are worth recalibrating before evolve relies on the silhouette score.
- **Contradictory model prose in a prompt (example 3).** The accepted model plan's trait notes say "limbs are four lion legs; no forelimb-to-wing substitution", while the limb plan says wings in place of the forelegs, and both reached the compiled prompt. The hard checks validate structure, not note text. The image followed the limb plan.
- **Habitat cue leaks into the coat.** "More patterned, irregular coat markings" (forest) became leopard spots in example 3, and the critic then named a leopard.

## Code changed in E2

- `route.py`: `LABEL_CLOSE` is now "speculative hybrid of close relatives, no documented cross".
- `chimera_data.json`: the guanaco is now *Lama guanicoe*. The cama override still resolves for both dams (D-055).
- `evolution/live.py`: live Muse Spark (first plan, polish, critic), SAM 3.1 (`sam-3.1`, Responses API, text plus data-URL image), and Muse Image through `call_with_retry`. All of them go through the existing `_MetaClient`: live budget guard before each attempt, a usage record after it, and key-free recordings.
- `adapters/usage.py`: new budget kind `sam` with cap `CHIMERA_LIVE_MAX_SAM`.
- `adapters/meta/client.py`: `raw=True` returns the HTTP body unparsed, and the upstream error body is now kept on errors.
- `engine.py`: in real mode the live adapters are built when `META_API_KEY` is set; without it, the engine still refuses before any call. If the first-plan call fails, the code skeleton is used (a budget error still stops the run).

Tests: backend 235 passed, 6 skipped (live, off by default). The 18 new tests include the SAM parser tested in mock mode against the recording.

---

# E2b: third-animal leakage fixed, examples 1 and 3 re-run live

Date: 2026-10-31. Branch: `evo` (not merged). Same caps: 20 images, 70 Spark and 8 SAM on the shared counter.
Outputs: `docs/evolution/live/e2b/`. Command: `scripts/e2_live_run.py e2b 1 3`.

## What changed (commit `679047a`)

1. **Prompt compiler.** A pattern is named only as "<donor>-type <type>" (for example "faint tiger-type stripes at about 20 percent strength on the flanks and legs"). The donor and type come from a new `coat_patterns` table in `data/evo_config.json`. If no parent carries a pattern, the prompt says "plain coat, no stripes or spots". The generic "Pattern lines ... follow the body outline" line now names the donor, or becomes "Coat texture flows along the body outline". Plan notes that mention patterns, or contradict the limb plan or mane, are left out of the prompt. That removes E2's "limbs are four lion legs; no forelimb-to-wing substitution".
2. **Mule and hinny.** Both overrides now carry an explicit plain `coat_pattern`. R2 documents no markings for either: RC-R2-03 covers coat *texture* only, and RC-R2-04 covers ears, mane, tail and size. The old donkey overlay came from the generic hybrid builder. That builder now overlays only a pattern a parent really has.
3. **Habitat step.** It now only scales the strength of an existing donor pattern: 0.1 fainter in open habitats, 0.1 bolder in closed ones. Its wording names the pattern ("fainter tiger-type stripes for an open habitat"). With no patterned parent it changes nothing, and it never adds markings. The old cue "more patterned, irregular coat markings" is gone; in E2 it produced example 3's leopard spots.
4. **Polish.** The polish is rejected if it adds an animal name that is not a parent (any of the 200 data animals, or their head word such as "leopard"). It is also rejected if it contradicts the limb plan or mane, or adds bare pattern wording. The compiled prompt is used instead, and the reason is stored in the creature's `polish` field.
5. **Critic.** If the full-image critic names an animal that is neither parent, the candidate is marked "third animal". Group words for a parent ("bird", "big cat") and the known pair's own name ("mule") do not count. It is then re-rendered once with the compiled prompt. If the third animal is still there, the creature is kept with a warning. The first image is kept as well.
6. **SAM scorer.** SAM is now prompted with "animal". A mask in 2 or more pieces is scored as one creature when the critic says one.
- **Also changed:**
  - `finish()` re-runs GATE, so a model plan cannot restore a mane that GATE removed. In E2 the accepted model plan put a lion mane back on a feathered neck.
  - The RC-R2-03 field-by-field check now ignores `None` values on both sides.
- **Tests:** 268 new tests in `tests/evolution/test_e2b_leakage.py`, including a 240-pair sweep. Backend total: 503 passed, 6 skipped.

## Before and after

| # | Image | Route | Host | Label | Quality | Critic (full image) | Critic (192 px thumbnail) |
|---|---|---|---|---|---|---|---|
| 1 before (E2) | ![](live/e2/1_donkey_x_horse/image.webp) | hybrid, known pair `mule` | horse | real hybrid precedent | 0.45 | named **donkey, zebra**; **1 creature** | donkey; 1 creature |
| 1 after (E2b) | ![](live/e2b/1_donkey_x_horse/image.webp) | hybrid, known pair `mule` | horse | real hybrid precedent | **0.67** | named **donkey**; **1 creature**. "A brown donkey stands in profile against a light background." | donkey; 1 creature |
| 3 before (E2) | ![](live/e2/3_lion_x_eagle/image.webp) | chimera | lion | speculative chimera, no real-world precedent; non-flying wings: display or gliding only | 0.768 | named **lion, leopard, eagle**; **1 creature** | lion, leopard, bird; 1 creature |
| 3 after (E2b) | ![](live/e2b/3_lion_x_eagle/image.webp) | chimera | lion | speculative chimera, no real-world precedent; non-flying wings: display or gliding only | **0.94** | named **lion, eagle**; **1 creature**. "A winged lion-like creature stands with outstretched feathered wings." | lion, eagle; 1 creature |

Score parts:

| # | critic | silhouette | thumbnail | soft penalty | SAM prompt | SAM mask (fill, aspect, components) | third animal | polish | re-render |
|---|---|---|---|---|---|---|---|---|---|
| 1 before | 0.5 | 0.0 | 0.5 | 0.0 | "horse" | empty | (not checked) | accepted | no |
| 1 after | 0.5 | 0.733 | 0.5 | 0.0 | "animal" | 0.284, 0.93, 1 | none | accepted | no |
| 3 before | 1.0 | 0.392 | 0.5 | 0.0 | "lion" | 0.364, 0.98, 2 (halved) | (not checked) | accepted | no |
| 3 after | 1.0 | 0.80 | 1.0 | 0.0 | "animal" | 0.354, 1.00, 2 (counted as one) | none | accepted | no |

The first plan for example 1 was again rejected under RC-R2-03, because the model edited the locked mule `body` field, so the code skeleton was used. Example 3's model plan was accepted. Its `coat_pattern` note ("eagle-pattern blocks") was left out of the prompt by fix 1.

## My judgment: does each image match its plan?

1. **Donkey x horse (mule): better, not yet.** The zebra stripes are gone (plain coat, as planned), and the critic sees no third animal. But the animal still reads as a plain donkey: long ears and donkey proportions, not the horse-height body and neck the plan asks for. So the critic names only one parent. The leakage is fixed; the mule frame is a separate problem, probably in how strongly the prompt carries the horse body.
2. **Lion x eagle: yes.** Eagle wings in place of the forelegs, standing on the hind legs, eagle feathers on the chest and neck, a plain lion coat elsewhere, and no mane, which matches GATE (feathered neck). No spots and no third animal.

## Calls: predicted vs made

| | Spark | Image | SAM |
|---|---|---|---|
| Predicted, 2 examples, no re-render | 8 | 2 | 2 |
| Extra if a re-render fires (per example) | +2 | +1 | +1 |
| Made, every attempt counted | **8** | **2** | **2** |
| Retries | 0 | 0 | 0 |
| Re-renders | 0 | 0 | 0 |

## Budget counter (`docs/live/budget.json`)

| | image | spark | sam |
|---|---|---|---|
| Before E2b | 15 | 43 | 5 |
| After E2b | **17** | **51** | **7** |
| Caps | 20 | 70 | 8 |

## Failures

None. Both examples succeeded on the first try. No re-render was needed, so the re-render path (tested in mock mode) did not run live. Remaining headroom on these caps is 3 images, 19 Spark and 1 SAM. That is not enough for another run with a possible re-render without raising the SAM cap.
