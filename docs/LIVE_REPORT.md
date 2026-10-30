# Live report (L1)

Date: 2026-10-30 · API: `https://api.meta.ai/v1` · Models: `muse-spark-1.3` (identify, plan), `muse-image-1.0` (generate, Responses API) · Data: **the real `data/chimera_data.json`** (L1-08) · Inputs: the six AI-generated fixture photos in `backend/tests/fixtures/live/` (not real photographs).

Raw evidence:
- every call: [`docs/LIVE_LOG.md`](LIVE_LOG.md)
- identification table: [`docs/live/identify.json`](live/identify.json)
- per-fusion run JSON and the generated images: [`docs/live/fusions/`](live/fusions/)
- key-free recorded responses: `backend/tests/fixtures/recorded/`

## Budget

| | Limit | Used | Notes |
|---|---|---|---|
| Image generations (`muse-image-1.0`) | 15 | **11** | 6 fixtures + 5 fusions; no retries were needed |
| Muse Spark calls (`muse-spark-1.3`) | 60 | **27** | 1 probe + 6 identify + 5 × 3 per fusion + 2 timed-out plan attempts (run 1 of the pinned fusion) + 1 timed-out and 1 successful plan attempt (run 2) |
| Tokens (logged) | n/a | **367,116** | images 253,665 (234,829 in / 18,836 out), Spark 113,451 (79,065 in / 34,386 out). The 2 unlogged timeouts returned no usage. |
| Cost | n/a | **unknown** | No pricing page is reachable from this environment (`api.meta.ai/pricing` 404, `developer.meta.ai` and `llama.com` blocked), and responses carry token counts but no price. |

The hard budget counter (`docs/live/budget.json`, enforced in `backend/app/adapters/usage.py`) counts every attempt and refused nothing. The log has 25 Spark rows against the counter's 27: the two plan attempts in the first pinned run were cancelled by the per-step timeout before the adapter could record them. That gap is fixed (cancelled attempts are now recorded), but the fix was not exercised live.

## Latency (from LIVE_LOG.md)

| Call | n | Min | Max | Timeout set (L1-05) |
|---|---|---|---|---|
| identify (`describe`) | 19 | 3.6 s | 9.0 s | 20 s |
| plan | 6 ok | 9.5 s | 24.1 s | 60 s (two pinned attempts exceeded 30 s; see problem 1) |
| generate (2 references) | 5 | 12.8 s | 37.1 s | 80 s |
| text-to-image (fixtures) | 6 | 8.4 s | 23.7 s | (covered by generate) |

A full fusion took 29 s to 67 s end to end. Generation cost rose with prompt length: 637 to 736-character prompts used 15.6k to 27.2k tokens, while the two longest (865 and 897 characters, both padded with habitat notes) used 41.4k and 41.9k and were the slowest. That's five samples, so treat it as a pattern to check, not a measurement.

## Identification (6 fixtures, L1-07)

All six matched the right animal in the real data, every one by scientific name.

| Fixture | Read as | Binomial | Confidence | Body plan | Matched |
|---|---|---|---|---|---|
| lion | Lion | *Panthera leo* | 0.99 | quadruped | lion ✓ |
| tiger | Tiger | *Panthera tigris* | 0.99 | quadruped | tiger ✓ |
| horse | Horse | *Equus caballus* | 0.99 | quadruped | horse ✓ |
| donkey | Donkey | *Equus asinus* | 0.99 | quadruped | donkey ✓ |
| bald_eagle | Bald Eagle | *Haliaeetus leucocephalus* | 0.99 | winged | bald_eagle ✓ |
| common_octopus | Common Octopus | *Octopus vulgaris* | 0.85 | multi_legged | common_octopus ✓ |

## Fusions

### 1. lion + tiger: expect a real hybrid (tigon) ✓

| | |
|---|---|
| Identified | Lion *Panthera leo* 1.00 · Tiger *Panthera tigris* 0.99 |
| Real hybrids | **liger** (father: lion × mother: tiger) and **tigon** (father: *Panthera tigris* × mother: *Panthera leo*), both `captive_only` |
| Mythology | navagunjara (a nine-animal composite, weak resemblance) |
| Rules | 44/130 mapped, 44 run; 0 warnings, 5 notes (R-A3-07 real-hybrid direction, R-A5-08, R-A5-10/25 wetland, R-A4-18) |
| Plan | "**Maned Striped Panther**", quadruped; head A, body B, limbs B, covering B, tail A |
| Steps (tokens) | identify 8,673 · plan 4,327 · generate 15,641 · total 28,641 in 29 s |
| Image | [`lion_tiger.webp`](live/fusions/lion_tiger.webp) |

**Judgment: follows the plan.** The lion head and full mane sit on a tiger torso with stripes and tiger legs. The tail carries a lion's dark tuft but keeps tiger stripes, so the tail donor was half followed. Anatomy is clean and the image is photoreal.

### 2. horse + donkey: expect mule ✓

| | |
|---|---|
| Identified | Horse *Equus caballus* 0.99 · Donkey *Equus asinus* 0.99 |
| Real hybrids | **hinny** (father horse × mother donkey) and **mule** (father *Equus asinus* × mother *Equus caballus*) |
| Mythology | none |
| Rules | 3 warnings: R-A5-01 / R-A8-03 "no shared habitat: horse forest/grassland/tundra/wetland; donkey desert/mountain", R-A5-02 "no shared climate: horse polar/temperate; donkey arid" (+ 4 notes) |
| Plan | "**Grey Ridge Courser**", quadruped; head B, body A, limbs A, covering B, tail A |
| Steps (tokens) | identify 8,629 · plan 6,172 · generate 41,373 · total 56,174 |
| Image | [`horse_donkey.webp`](live/fusions/horse_donkey.webp) |

**Judgment: plausible, but hard to verify.** It shows a donkey head and ears, a grey coat and a dark, horse-like tail. The body proportions sit between the two parents, so "body from horse" is not clearly visible. The result is visually close to a real mule; the "Generated fusion" label carries the honesty here. The habitat and climate warnings are technically correct for the data, but odd for a pair whose real hybrid is common (problem 6).

### 3. bald eagle + lion: expect a griffin-style mythology match ✓

| | |
|---|---|
| Identified | Bald Eagle *Haliaeetus leucocephalus* 0.99 · Lion *Panthera leo* 1.00 |
| Real hybrids | none |
| Mythology | **griffin** (Greek; matched "eagle" and "lion" by name), then anzu, sharabha, sphinx (matched through "bird"). All are "line-checked by Muse (not re-checked by Claude)" and none is presented as verified. |
| Rules | 1 warning: R-A8-02 body-plan conflict (no detail; see problem 3), + 5 notes |
| Plan | "**White-crowned Savanna Hunter**", quadruped; head A, everything else B |
| Steps (tokens) | identify 8,876 · plan 6,411 · generate 15,891 · total 31,178 |
| Image | [`bald_eagle_lion.webp`](live/fusions/bald_eagle_lion.webp) |

**Judgment: follows the plan exactly.** An eagle head on a lion body with lion legs and a tufted tail. It is **not a griffin**: there are no wings, because the plan has no wings slot and the planner gave limbs to the lion (problem 2).

### 4. lion + octopus: expect rule warnings ✓

| | |
|---|---|
| Identified | Lion *Panthera leo* 0.99 · Common Octopus *Octopus vulgaris* 0.88 |
| Real hybrids / mythology | none / none |
| Rules | 4 warnings: R-A5-01 / R-A8-03 "no shared habitat: lion forest/grassland/mountain; common octopus marine", R-A5-03 "common octopus lives only in the sea; lion only on land", R-A8-02 body-plan conflict (+ 3 notes, incl. R-A4-P04 unrecorded active time adds nothing) |
| Plan | "**Maned Reef Prowler**", quadruped; lion for everything except the tail (B) |
| Steps (tokens) | identify 9,654 · plan 5,863 · generate 41,866 · total 57,383 |
| Image | [`lion_octopus.webp`](live/fusions/lion_octopus.webp) |

**Judgment: follows the plan exactly.** A lion with a curled octopus-arm tail with suckers. The planner kept the octopus to one part, which is a sensible answer to the realm warning.

### 5. lion + bald eagle with pins (head A, limbs B): pins honoured ✓ (second attempt)

| | |
|---|---|
| Identified | Lion 1.00 · Bald Eagle 0.99 |
| Mythology | griffin first, as in fusion 3 |
| Plan | "**Maned Wetland Strider**", **biped**; head A (**you**), body B, limbs B (**you**), covering B, tail A |
| Steps (tokens) | identify 8,727 · plan 6,336 (2 attempts) · generate 27,241 · total 42,304 in 67 s |
| Image | [`lion_eagle_pinned.webp`](live/fusions/lion_eagle_pinned.webp) |
| Run 1 | **failed**: both plan attempts timed out at 30 s (`UPSTREAM_TIMEOUT`); run JSON kept as `lion_eagle_pinned.attempt1-timeout.json` |

**Judgment: follows the plan and both pins.** A lion head and mane on an eagle's feathered body standing on eagle talons, with folded wings and a lion's tufted tail. This is the most convincing chimera of the set. The planner chose a biped body plan to fit eagle legs, a reasonable call.

## Pass / fail summary

| Live test | Result |
|---|---|
| identify all 6 fixtures | **pass** |
| lion + tiger → tigon with direction | **pass** |
| horse + donkey → mule | **pass** |
| bald eagle + lion → griffin | **pass** |
| lion + octopus → rule warnings | **pass** |
| lion + eagle pinned | **pass** on the second run; the first run failed with a plan timeout (problem 1) |

## Problems found (most severe first)

1. **The Spark client's HTTP timeout was the identify timeout, so plan calls were cut off.** `services.py` built the single Muse Spark client with `identify_timeout_seconds` (30 s, later 20 s). Pinned plans can take over 30 s, so the first pinned run failed twice, and the second run lost one attempt at exactly 20.0 s before succeeding. Fixed after the runs: the client now uses `max(identify, plan)` (60 s). **That fix has not been exercised live.**
2. **There is no "wings" part.** The donor slots are head, body, limbs, covering and tail. Bird × mammal fusions either drop the wings (eagle + lion gives an eagle-headed lion, not a griffin) or fold them away as vestigial (fusion 5). The griffin, hippogriff and pegasus resemblances the data offers can't be produced on purpose. This affects the most demo-friendly pairs.
3. **Analytic notes leak into image prompts.** The prompt receives up to 3 warnings verbatim, and none of them is a visual instruction:
   - When a warning has no specific detail (R-A8-02 `body_plan_mismatch`), its full rule text goes in: "A fusion with a body_plan conflict (e.g. finned x quadruped with no amphibious design note) must be flagged…". That happened in 3 of 5 prompts.
   - Otherwise the data note goes in ("no shared habitat: horse forest/grassland/tundra/wetland; donkey desert/mountain").

   Two related faults:
   - The hybrid line names only the first documented hybrid: horse + donkey was told to "stay close to the documented hinny", although the mule is the better-known cross.
   - The two longest prompts were also the two heaviest generations (41k tokens against 15k to 27k).

   **Fix:** translate each warning into a short visual instruction, or leave it out of the image prompt.
4. **Planner rationales are long and parrot the rule notes** (e.g. "without inheriting captive liger fertility", "temperate-to-tropical thermal range excluding tundra extremes"). They are accurate, but too verbose for the "How this was made" panel.
5. **Cost is unknown and token use is high.** Each fusion uses 29k to 57k tokens; generation with two 1600 px references is 15k to 42k of that, mostly input tokens (partly cached). Without published pricing, the spend guard can cap calls and tokens but cannot cap money.
6. **The habitat and climate rules contradict documented hybrids.** Horse + donkey gets three warnings (no shared habitat or climate) although the mule is common. The data's per-species habitats are narrow for domestic animals. Consider downgrading R-A5-01/02 to notes when a documented real hybrid exists.
7. **Mythology matches through broad words are noisy.** Lion + tiger "resembles navagunjara" (a nine-animal composite) through the "tiger" and "lion" components. Matching is correct but weak. Rank or cut composites with many components.
8. **No mythology row is verified.** All 254 rows say "line-checked by Muse" or "URL loads only". The API passes this through verbatim (`verified: false`); the UI must show it.
9. **The fixtures are generated, not photographed.** Identification at 0.85 to 1.00 on clean AI images is likely optimistic for real phone photos (clutter, partial animals, people in frame).
