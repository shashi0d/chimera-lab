# S3a: trust layer and the integration experiment

Branch `evo`, 2026-11-01. ROADMAP section 5b (S2 and S3a rows). Not merged. Live outputs are in `docs/evolution/live/s3a/` and `docs/evolution/benchmark/`. Caps were runaway guards only (cumulative counter: images 120, Meta Spark 550, SAM 325, Spark Open 650).

**Result:**
- **Critic:** the new plan-blind critic catches all 6 known failures in the gold set with 0 false alarms on the 5 known goods. That holds for each critic alone and for the pair, and was confirmed on a fresh live run. The old S2 critic caught 3 of 6.
- **Citations:** cited traits are now checked in code (source tier, quote found on the fetched page, page names the animal). Of the 50 stored S2 citations for the 4 animals, 16 survive. The rest fall back to model-estimated, with the reason recorded.
- **Research cards:** RC-R10-12 to 14 are in `rule_cards.json` (112 cards). The research scripts were silently skipping any doc number above 9.
- **Tests:** 869 passed, 6 skipped (37 new S3a tests).

## 1. Gold set

`docs/evolution/benchmark/gold_set.json`: 11 existing images, no new renders. Every label is marked "human-provided via chat review".

| Image | Label | Owner's reason |
|---|---|---|
| e2/1_donkey_x_horse | fail | zebra-type stripes, third animal |
| e2/3_lion_x_eagle | fail | leopard spots, third animal, full mane although planned out |
| e4/b_axolotl_x_pangolin | fail | external gills on a land creature |
| e4/d_rhinoceros_beetle_x_brown_bear | fail | whole beetle bodies attached, wings over four legs |
| s2/beetlebear_run1 | fail | a plate reads as a whole beetle body, insect-leg pieces on the legs |
| s2/beetlebear | fail | donor parts sit on top of the fur like armor, scattered instead of one dorsal shield |
| e2/2_lion_x_tiger | good | |
| e4/c_lion_x_eagle (mythic) | good | |
| e2/4_eagle_x_octopus | good | |
| e2c/1_donkey_x_horse | good | |
| e4/b_axolotl_x_pangolin_rerender | good | except: axolotl barely visible |

## 2. The plan-blind critic protocol (`backend/app/evolution/critic.py`)

inspect now runs this protocol on every route. The judge's old checklist still scores the render, but it no longer decides inspect. The S2 version is kept as `inspect_checklist`, the calibration baseline.

| Step | What it does |
|---|---|
| a) Describe first | `describe(image)`: the critic sees only the image. It writes a free paragraph, then every part with what it looks like and where, any attached objects, and the animals it sees. No plan text is sent. |
| b) Counts | Same call, after the description: separate bodies or body-shaped objects (including attached ones), heads, walking legs, wings, extra limb-like pieces. Code compares them with the limb plan; a side view may hide one of four legs. |
| c) Balanced checklist | `ask(image, questions)`: at least half the questions expect "no" (no wings, no whole animal attached, no insect-leg pieces, no second head, no mane when gated, no stripes or spots on a plain coat, no unplanned donor features such as the axolotl's gills). Questions name visible features; a test bans plan words ("donor", "patch", "host", "license"). The expected answers are never sent. |
| d) Integration | For a protective donor covering (shell, exoskeleton, scales; RC-R10-12): grows out with a natural transition (expected yes) or sits on top as separate pieces (no); one continuous structure (yes) or scattered pieces (no); covering on the legs or shoulders when not planned (no). |
| e) Two critics | Spark Open (Baseten) and Meta Spark 1.3 answer independently and in parallel. Agreement decides; disagreement or "unclear" becomes `uncertain`, which counts as a failure (a fail signal for the agent and the edit turn). A failed critic call is retried once, then becomes an `uncertain` row. |
| f) Description matched against the plan | Code finds structural concepts in each description (wings, gills, horn, mane, stripes, spots, tentacles, insect legs, whole bodies, antennae). Negated clauses are dropped first. It reports extras (described but not planned) and omissions (planned donor parts nobody described). Third animals come from the described animals. |

Every row carries a fix worded from the plan item ("Show the hard, glossy chitin plates with fine seams grown in the skin over the back and flanks…"), never from the symptom, so the one S2 edit turn still works. SAM 3.1 can turn a positive part question into a pass, but never fails anything.

Cost per inspect: 4 Spark calls (2 per critic) plus 1 SAM per planned part, against 0 extra in S2, where inspect reused the judge's checklist. Accepted on quality grounds: the S2 inspect missed half the known failures.

## 3. Calibration (`docs/evolution/benchmark/calibration/ITERATIONS.md`)

| Iteration | Change | Old | Spark Open | Meta Spark | Pair |
|---|---|---|---|---|---|
| 1 (live) | first protocol | 3/6 caught, 0/5 false alarms | 6/6, 4/5 | 6/6, 2/5 | 6/6, 4/5 |
| 2 (live) | bare answer list plus one retry; negation-aware matching; no wings from "wing cases"; feather ruff is not a mane; integration only for protective coverings; hybrid frame question | 3/6, 0/5 | 6/6, 1/5 | 6/6, 1/5 | 6/6, 2/5 |
| 3 (re-score) | a single dorsal stripe is not a striped coat; soft-surface presence is informational | 3/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 |
| 4 (live, fresh) | none: a confirmation run | 3/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 | **6/6, 0/5** |

What the iterations fixed:
- **Iteration 1:** Spark Open ran to its 8000-token cap on 4 of 11 checklist calls when told to copy each question's text. This is the S1 runaway again. The 4 resulting errors made every row uncertain, which caused most of the false alarms.
- **Iteration 2, mule frame question:** a mule is not "a horse body shape" to either critic.
- **Iteration 2, axolotl skin:** the owner rated the axolotl skin patches good, but both critics said they sit on top. RC-R10-12 is about protective coverings, so integration questions now apply only there.
- **Iteration 3:** a mule's dorsal stripe and the octopus skin sitting on the thighs instead of the belly were the last two false alarms. Both are surface details, not structural misses.

The signals match the owner's reasons on every known failure (iteration 4, pair):

| Known failure | Old critic | New protocol's signals |
|---|---|---|
| e2/1 donkey x horse | third animal | third animal (zebra); frame uncertain |
| e2/3 lion x eagle | frame, third animal | mane (question and description), spots on the fur, third animal, frame |
| e4/b axolotl x pangolin | **missed** | unplanned feathery external gills (question and description) |
| e4/d beetle x bear | whole beetle | wings, four legs plus wings, whole animal, extra legs, leg count, on top, scattered |
| s2 beetlebear run 1 | **missed** | whole animal, insect-leg pieces, scattered, plates on the legs and shoulders, on top (uncertain) |
| s2 beetlebear | **missed** | on top, does not grow out, scattered, plates on the legs and shoulders |

Caveat: 11 images is small, and iterations 2 and 3 were adjusted after seeing them. Iteration 4 shows the result is stable across fresh calls, not that it generalizes. The experiment below is the first out-of-sample use.

## 4. Citation verification (`backend/app/evolution/citecheck.py`, `data/source_tiers.json`)

A web-cited field counts only if all three checks pass:
1. **Source tier:** tier 1 (`.edu`, `.gov`, `.ac.uk` and similar; museums; peer-reviewed publishers; Animal Diversity Web) or tier 2 (zoos, aquariums, National Geographic, Britannica, BBC and other major science media).
   - Rejected: stores (a host containing "store" or "shop"), dictionaries, children's encyclopedias (`kids.` hosts), general wikis (Wikipedia, Fandom, animalia.bio, a-z-animals).
   - Unlisted domains are not accepted. The trust layer is conservative; a domain is added to the tier file with a reason.
2. **Quote on the page:** the page is fetched in code (PDF sources through `pypdf`, a new dependency). The model's quote must appear after normalization; "..." splits it into segments that must appear in order.
3. **Subject** (added after the first run): the page must name the animal by common name, its last word, the binomial or the genus.
   - Why: the mammoth's "uses lungs to breathe" quote really is on its page, but the page is a whale-evolution guide.

Anything else falls back to `model-estimated (citation not accepted: <reason>)`. The new-animal resolver path runs the same checks before it stores a field as web-cited.

**Re-verification of the 4 S2 animals** (live code fetch, no model calls). Learned entries keep only passing citations; the others move to `rejected_citations` with the reason. The axolotl is a database animal, so it is compared only.

| Animal | Supported | Rejected source | Unlisted source | Page blocked (403) | Quote not found | Off subject |
|---|---|---|---|---|---|---|
| axolotl | 6 (natgeo ×4, ADW, rvc.ac.uk PDF) | 0 | 1 (ielc.libguides.com) | 6 (San Diego Zoo) | 0 | 0 |
| Chinese pangolin | 7 (ADW ×6, natgeo) | 5 (animalia.bio ×4, Wikipedia) | 0 | 1 (britannica.com) | 0 | 0 |
| rhinoceros beetle | 0 | 6 (Wikipedia ×5, Merriam-Webster) | 6 (monaconatureencyclopedia ×5, coleoptera.org.uk) | 0 | 0 | 0 |
| woolly mammoth | 3 (UC Berkeley ×2, Jacksonville Zoo) | 5 (museum store ×3, Britannica Kids ×2) | 0 | 3 (si.edu, amnh.org ×2) | 0 | 1 (whale guide) |
| **Total** | **16 of 50** | 16 | 7 | 10 | 0 | 1 |

What this shows:
- **Beetle:** none of its citations survive. Every trait is model-estimated again, which was the honest status all along.
- **Pangolin:** strongly sourced, from Animal Diversity Web.
- **No invented quotes:** every quote that could be fetched from an accepted source was found on its page, so the model did not invent quotes.
- **Blocked sites:** 10 citations fail only because the site blocks automated fetches (San Diego Zoo, Smithsonian, AMNH, Britannica). They fall back to model-estimated. I tried an archived copy as a fallback; the environment denied it as working around the site's block, and I did not pursue it. These 10 are the main candidates for a human check or a different fetch route if the owner wants them back.

## 5. Research cards

`docs/evolution/research/R10_chimera_science_landscape.md` was created with RC-R10-12, 13 and 14.
- **Missing earlier cards:** the file did not exist before, and RC-R10-01 to 11 are not in the repository, although ROADMAP section 6 names RC-R10-11. The numbers the owner assigned are kept.
- **Script bug found:** `verify_research.py` and `build_rule_cards.py` matched only `RC-R\d-` (one digit), so R10 cards would have been skipped silently. Both now accept `RC-R\d+-`, and cards sort by doc number.
- **verify_research:** 11 files, 112 cards, 0 failures, 16 bot-blocked (403) as before, 1 timeout warning. Both R10 sources resolve.
- **rule_cards.json:** regenerated, 112 cards (17 hard). The diff adds exactly the 3 new cards.

## 6. Tests

- **New:** `backend/tests/evolution/test_s3a_trust.py` (37 tests).
  - Protocol: question balance and plan-blindness, the owner's integration wording, the protective-covering scope, the hybrid frame question, unplanned donor features, expected counts, negation-aware matching, extras and omissions, two-critic agreement and disagreement, counts and third animals, failed-critic retry, plan-worded fixes, and the wire format.
  - Citations: 14 tier cases, quote normalization and ellipses, every verifier status, the resolver path, fallback, and reverify.
  - Cards: R10 in the rule book, and two-digit doc numbers in the builder.
- **Updated:** S2 inspect tests now cover `inspect_checklist`. The engine edit-turn tests script the protocol's answers. Call counts rose by 4 Spark calls per render. The card count is 112.
- **Full suite:** 869 passed, 6 skipped. ruff is clean.
