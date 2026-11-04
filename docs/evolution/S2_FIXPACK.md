# S2: fix pack and agent preparation

Branch `evo`, 2026-11-01. ROADMAP sections 4, 5 and 5b. Decisions D-063 to D-071. Live outputs are in `docs/evolution/live/s2/`. Caps were runaway guards only (images 80, Spark 250, SAM 80, Spark Open 600); none came close.

**Result:**
- **Beetle x bear:** fixed live. Four bear legs, no wings, a chitin horn on the brow, chitin plates as patches, the size license's breathing openings visible, and the model plan accepted.
- **Cited traits:** the 4 animals now have them (12 or 13 of 13 fields each, every URL checked against a page the model opened).
- **Agent tools:** the plan is now six typed operations with errors the agent can act on.
- **Tests:** 834 passed, 6 skipped (134 new S2 tests).

## What changed

| Part | Change | Decision |
|---|---|---|
| 1a | RC-R3-01/02 apply to vertebrate wing donors only. Insect wings sit on a dorsal mount (bendable `insect_wings`, card RC-R3-09, compensation "raised, plated mount between the shoulder blades, with all four legs kept"); over budget they are dropped. | D-063 |
| 1b | `data/class_parts.json` ("model-estimated, reviewed") covers 11 classes: allowed body plans, coverings, mouthparts and breathing, plus visible parts with slot, shape and job, and a `never` list. Every donor part (seed and model plans) and every saved trait is checked; an invalid part is replaced by the donor's most recognizable valid part. The learned beetle's body plan was corrected from `multi_legged, winged` to `multi_legged`, logged in the entry. Its "jointed tail segments" became its head horn. | D-064 |
| 1c | Hosted prompts have one grouped donor clause ("from the <donor>, as parts and materials on the <host>'s own body: …") with parts and surfaces as materials and shapes. | D-065 |
| 1d | The silhouette is recomputed last and `silhouette_issues` must find no disagreement with the limb plan. | D-065 |
| 2 | The prompt is compiled only from structured fields plus code-owned `render_details`; notes never reach it. The forced choice is removed everywhere. | D-066 |
| 3 | `ops.PlanSession` provides `set_host`, `set_region`, `set_habitat`, `set_mode`, `add_license` and `drop_part`, each validated on its own with structured errors; code fills `card_trace` and every derived list. `labels`, `processes` and `card_trace` left the model plan schema. | D-067 |
| 4 | Web-cited traits: Meta Spark 1.3 with `web_search` and a citation per field, verified against the pages it opened. This is the new resolver step for animals not in the database. `Resolver.cite` re-resolves and reports matched, corrected or uncited. | D-068 |
| 5 | Routing per call type in `evo_config.json`: Spark Open (with output caps) for identify, checklist, thumbnail, polish and the open critic; Meta for plans, traits, cited traits, the audit and vary. Fallback to Meta is logged; the provider is on every call record and on the card. | D-069 |
| 6 | `inspect`: SAM presence for planned parts plus the checklist critic for absences, third animals and separate bodies. One plan-worded Muse Image edit turn (`previous_response_id`), then inspect again; a remaining miss is kept with a warning. Replaces the E2b re-render. | D-070 |
| 8 | Live fix: code-owned labels are checked on the finished plan only (a model plan for a large-arthropod pair was always rejected). | D-071 |

## Cited traits (live, 4 Meta Spark calls, 40 to 72 s each)

Status per field, with the host of the cited page. The axolotl is in `chimera_data.json`, so it is compared only (the database stays the source of truth). The other three are learned entries: they now hold the cited values, with old values kept in `corrections`.

| Field | axolotl | Chinese pangolin | rhinoceros beetle | woolly mammoth |
|---|---|---|---|---|
| body_plan | matched (animals.sandiegozoo.org) | matched (animaldiversity.org) | matched (monaconatureencyclopedia.com) | matched (museumstore.hmns.org) |
| primary_locomotor_part | matched (animals.sandiegozoo.org) | matched (animaldiversity.org) | matched (monaconatureencyclopedia.com) | matched (museumstore.hmns.org) |
| covering | matched (nationalgeographic.com) | matched (animaldiversity.org) | matched (monaconatureencyclopedia.com) | matched (kids.britannica.com) |
| movement | matched (ielc.libguides.com) | corrected (animalia.bio) | matched (monaconatureencyclopedia.com) | matched (museumstore.hmns.org) |
| habitat | corrected (animals.sandiegozoo.org) | corrected (animalia.bio) | corrected (monaconatureencyclopedia.com) | matched (si.edu) |
| climate | corrected (animals.sandiegozoo.org) | matched (animaldiversity.org) | matched (en.wikipedia.org) | corrected (jacksonvillezoo.org) |
| diet | matched (nationalgeographic.com) | matched (nationalgeographic.com) | matched (en.wikipedia.org) | matched (amnh.org) |
| active_time | corrected (nationalgeographic.com) | matched (animaldiversity.org) | corrected (en.wikipedia.org) | matched (ucmp.berkeley.edu) |
| body_mass_kg | matched (nationalgeographic.com) | matched (animalia.bio) | uncited | matched (ucmp.berkeley.edu) |
| body_length_m | corrected (animaldiversity.org) | matched (en.wikipedia.org) | matched (en.wikipedia.org) | uncited |
| visible_features | corrected (animals.sandiegozoo.org) | corrected (animalia.bio) | corrected (en.wikipedia.org) | corrected (kids.britannica.com) |
| mouthparts | matched (rvc.ac.uk) | matched (animaldiversity.org) | matched (coleoptera.org.uk) | matched (amnh.org) |
| breathing | matched (animals.sandiegozoo.org) | matched (britannica.com) | matched (merriam-webster.com) | matched (naturalhistory.si.edu) |
| **Totals** | 8 matched, 5 corrected | 10 matched, 3 corrected | 9 matched, 3 corrected, 1 uncited | 10 matched, 2 corrected, 1 uncited |

Real corrections:
- **Axolotl:** active time `diurnal, nocturnal` → `nocturnal`; habitat adds `wetland`; length 20 to 30 cm added (the database had none); climate `temperate` added.
- **Pangolin:** movement adds `swim`; habitat drops `mountain`.
- **Beetle:** habitat drops `grassland`; active time adds `crepuscular` ("flying at dusk and by night").
- **Mammoth:** climate drops `temperate`.

My assessment:
- **Sources:** most are good (Animal Diversity Web, San Diego Zoo, National Geographic, Smithsonian, AMNH, UC Berkeley, Wikipedia). Some are weak: a museum store page (the mammoth's body plan), Merriam-Webster (beetle breathing, from the definition of "spiracle"), Britannica Kids, animalia.bio, and an Italian-language encyclopedia page.
- **Weak support:** a few quotes support their value only loosely. The axolotl's "temperate" climate rests on a sentence about breeding-season water temperatures. The beetle's "forest" habitat rests on larvae developing in decaying wood.
- **Arguable corrections:** "Chinese pangolin: no mountain habitat" and "woolly mammoth: polar only" are both debatable.
- **What verification proves:** a verified URL shows the page was opened, not that the quote supports the value. Quote checking is the next step for this tool.
- **`visible_features`:** its "corrected" results are mostly rewordings of the same features. The comparator treats any different text as a correction, which overstates the changes for that field.

## Rhinoceros beetle x brown bear, speculative (live, full fix pack)

**Plan (run 2, model plan accepted):**
- **Frame and limbs:** brown bear host, four legs, no wings. The beetle is a flier, so it brought insect wings on a dorsal mount, but they were dropped over budget: the one speculative license went to arthropod parts at 340 kg (RC-R3-09).
- **Beetle parts:** its head horn on the brow (class part replacing "jointed tail segments"), and chitin-plate patches on the back and flanks.
- **Rest of the plan:** forest habitat; audit breathing pass, feeding pass, support licensed, movement repaired (wings dropped), heat pass, senses pass.
- **Silhouette:** "four-legged brown bear frame".

**Cited traits used:** the beetle entry now carries 12 web-cited fields; only body mass is uncited. It still has `multi_legged` and the head horn first among its features, so the class check and the donor part are unchanged.

**Prompt (compiled, then polished by Spark Open and accepted):** the donor is named once: "from the european rhinoceros beetle, as parts and materials on the brown bear's own body: a single curved horn of hard, glossy chitin rising from the brow; hard, glossy chitin plates with fine seams in its own colors, in a few large patches over the back and flanks…". It ends with "Declared fiction: arthropod parts at large size, shown with thick supporting legs and visible breathing openings along the flanks."

**Inspect (one checklist call, reused from the judge, plus SAM for the horn):**

| Item | Kind | Critic | SAM | Result |
|---|---|---|---|---|
| a brown bear body shape | frame | yes | | pass |
| a brown bear head with visible eyes | head | yes | | pass |
| thick supporting legs and visible breathing openings along the flanks | compensation | yes | | pass |
| no wings | absent | yes | (never SAM-tested) | pass |
| a single curved horn of hard, glossy chitin rising from the brow | part | yes | found, fill 0.0064 | pass |
| only parts and materials of the european rhinoceros beetle, no whole beetle animals on the body | one body | yes | | pass |
| hard, glossy chitin plates with fine seams patches on the back and flanks | surface | yes | | info |

The critic counted 1 creature and named the brown bear and the European rhinoceros beetle, with no third animal. No structural item failed, so no edit turn was made: "after the edit" equals "before".

**Scores (run 2):** critic 1.0, silhouette 0.891, thumbnail 1.0, soft penalty 0, quality **0.967**. The open critic (logged) said "a brown bear's body covered in glossy dark beetle-like armor plates and a large curved horn on its forehead".

**My judgment:** fixed.
- **Compared with E4:** E4 had beetle wings on top of four legs and five whole beetle bodies on the shoulders. Run 2 shows one bear with four legs and its own head, a single chitin horn rising from the brow, glossy segmented chitin plates and a row of breathing openings along the flank. There are no wings and no whole beetles.
- **Remaining flaw:** plates also sit on the shoulders and upper legs, beyond the planned back and flanks. The checklist cannot see that, because its surface item is informational.

**Run 1 (the honest first attempt, `live/s2/beetlebear_run1/`):**
- **Model plan rejected:** the plan was rejected by my part-3 bug (D-071), so the code skeleton was used.
- **What the image got right:** four legs, no wings, the horn, breathing openings.
- **What it got wrong:** one flank plate reads as a whole beetle body (wing cases plus pronotum), and jointed insect-leg pieces wrap the bear's legs.
- **Missed by the judge:** the Spark Open checklist answered yes to "no whole beetle animals", so inspect did not trigger an edit. One lenient critic answer means an obvious structural miss goes unrepaired. This is the main open weakness (see below).

## Calls by provider (S2, live)

| Provider | Call | Calls | Failed | Latency |
|---|---|---|---|---|
| Meta Spark 1.3 | web-search probe | 1 | 0 | 12.8 s |
| Meta Spark 1.3 | cited traits (`evo_cite_traits`) | 4 | 0 | 40 to 72 s |
| Meta Spark 1.3 | first plan (`evo_plan`) | 2 | 0 | 16 to 17 s |
| Spark Open (Baseten) | checklist and thumbnail (`evo_checklist`) | 4 | 0 | 7 to 14 s |
| Spark Open (Baseten) | polish | 2 | 0 | 8 to 9 s |
| Spark Open (Baseten) | open critic | 2 | 0 | 10 to 11 s |
| Meta Muse Image | render | 2 | 0 | 33 to 44 s |
| Meta SAM 3.1 | silhouette ("animal") and part presence ("head horn") | 4 | 0 | 1.5 to 4.5 s |

There were no Baseten fallbacks and no retries. Each beetle x bear run made exactly the predicted 1 Meta Spark, 4 Spark Open, 1 image and 2 SAM calls. The cited-trait calls were made before part 5 added the provider column, so `LIVE_LOG.md` shows them without the `meta/` prefix.

| Budget counter | image | spark | sam | spark_baseten |
|---|---|---|---|---|
| Before S2 | 26 | 97 | 21 | 44 |
| After S2 | 28 | 104 | 25 | 52 |

## What step 3 (the agent core) needs to know

1. **Plan tools exist:**
   - **The session:** `engine.plan_session(sire, dam, mode)` returns a `PlanSession`. `apply(op, args)` returns `OpResult.public()`: ok, errors with code, field, hint and valid values, warnings, and a summary with parts, patches, licenses and budget, audit, dropped parts, and a checklist preview.
   - **Errors are tool feedback:** feed them back to the model verbatim.
   - **Rendering:** render a session plan with `engine.realize(session.plan, session.route, refs)`.
   - **No plan writing:** the agent never writes a plan, and the legacy `write_plan` stays only for the step-5 comparison.
2. **Map the roadmap tools onto code:**

   | Roadmap tool | Code |
   |---|---|
   | `resolve_animal` | `engine.resolve` (database, learned, GBIF, cited traits) and `resolver.cite` |
   | `audit_plan` | the session summary plus `engine._check` (hard cards come back as `hard_card` errors) |
   | `render`, `inspect`, `edit` | already chained inside `realize`; expose them separately if the agent should decide the edit itself |
   | `finalize` | `output_card`, which now carries `providers` and citation URLs |

3. **Call budget per creature (measured):** 1 Meta plan (none on the ops path), 4 Spark Open, 1 image and 1 SAM plus 1 per planned part. An edit adds 1 image, 3 Spark Open and the same SAM again.
4. **Spark Open as brain:** S1 showed correct tool use. S2 routes only bounded calls to it, with output caps. Keep tool arguments small; the ops were designed for that.
5. **The critic is the weakest link:** Spark Open's checklist answered yes to everything on both runs, including run 1's whole-beetle plate. Options:
   - a plan-blind second critic for the structural items;
   - SAM with the donor name to localize, plus a crop critic;
   - asking for counts ("how many beetle-shaped objects?") instead of yes/no.

   An agent that trusts inspect blindly will accept run-1-style images. This is the ROADMAP step-4 work, and the next weakest point after S2.
6. **Patch regions are not inspected:** the surface item is informational, so plates spreading beyond the planned regions pass.
7. **Cited traits verify that a URL was opened, not that the quote supports the value.** Some sources are weak (a store page, a dictionary).
8. **The edit loop has not yet triggered live in S2:** neither run needed it, so the plan-worded instruction is tested in mock mode and against the S1 recording only. The first live trigger should be reviewed by eye.
9. **Not done here:** reference portraits (off by default per 5b), a Baseten fallback seen live, and live `PlanSession` use.
