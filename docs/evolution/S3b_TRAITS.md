# S3b: trait transfer instead of part transfer

Branch `evo`, 2026-11-01. Not merged.
- **Live outputs:** `docs/evolution/live/s3b/validation/<run>/<repeat>/`. Each holds the image, the first pass, the exact plan (`plan.json`), the compiled and final prompts, the inspect and judge records, and `doc.json`.
- **Calibration:** `docs/evolution/benchmark/calibration_s3b/`.
- **Caps:** runaway guards only (cumulative counter: images 120, Meta Spark 900, SAM 200, Spark Open 900). Used over S3b: images 58→84, Meta Spark 284→483, Spark Open 244→507, SAM 45→80.

**Owner's direction** (`benchmark/s3a_owner_review.md`, verbatim): edit the animal, not the image; general fixes only, never patches for the two reviewed images.

**Result:**
- **Beetle × bear:** the engine now plans and words a donor covering as a trait that develops on the host (material, extent with a reason, host-scaled plates, joints), not as the donor's shape. In the validation images:
  - armor covers the legs, and plates follow the bear's segments and muscle masses;
  - the horn grows from a head covering that continues into the body, and in every image that has the planned horn, both critics say it came from a beetle (rhinoceros beetle; once "stag beetle");
  - growth by edit kept the horn on the crown in all three repeats.
- **Axolotl × pangolin:** stays good, with fuller coverage.
- **Held-out pairs:** integration improved almost as much as on the tuned pairs (92% vs 98% of integration answers passing).
  - The new failure mode is identity. A fully plated body reads as a "pill bug", "armadillo" or "woodlouse", and the crab's segmented tail reads as an isopod's.
  - Tortoise × goat exposed a host-choice consequence of the new hard card RC-R10-01 (below).
- **Critic:** recalibrated on 33 owner-labeled images, it catches 18/18 failures with 3/15 false alarms, confirmed live. That holds only under the configured rule (Meta Spark decides). The S3a pair rule gives 9–11/15 false alarms. **This departs from the owner's S3a rule and needs the owner's confirmation** (D-082).
- **Tests:** 900 passed, 6 skipped (30 new S3b tests).

## What changed

| Part | Change | Decision |
|---|---|---|
| 0 | The owner's files placed: R10 with RC-R10-01 to 14 (`research/`), `benchmark/s3a_owner_review.md`, `scripts/plan_evolution_sim.py`. RC-R10-01 is hard ("neither size nor mass decides which parent wins"), and `choose_host` broke ties by mass. The code now gives an equal-structure tie to the first-named parent (logged, switchable), with a hard-card test. | D-077 |
| 1 | RC-R10-15 (transfer traits, not shapes; source: UC Berkeley Understanding Evolution, homologies and analogies) and RC-R10-16 (an exoskeleton is a whole-body system with flexible cuticle at the joints; source: NC State General Entomology, arthropods). Both VERIFIED against the fetched page. RC-R10-13 carries `superseded_by: RC-R10-15`; the loader keeps it but never applies it. `rule_cards.json` has 125 cards (18 hard). | D-078 |
| 2 | Every donor feature gets a typed `Transfer`: class (material, homologous or non-homologous), anchor, extent with a reason, a scale rule, connections and positive identity cues. Code derives them in `finish()` from `data/transfer_rules.json`. A non-homologous back shape (elytra) folds into material. The covering's extent becomes a layer (RC-R10-06). Four validated plan operations: `set_transfer_class`, `set_extent`, `connect_features`, `set_identity_cues`. | D-079 |
| 3 | The compiler's default for a covering is the V2 replacement wording, built from the transfer: material, extent, "each plate sized to the host's own body segments and muscle masses", "joined by flexible cuticle at every joint", "conforms to the host's body". It has no donor-icon shapes (no elytra, shields or domes). Discrete parts are worded by class, anchor, connection and identity cues. The host keeps its own covering and pattern only on the zones the covering leaves. | D-080 |
| 4 | Growth by edit, for coverings only. The first pass is the host with its discrete parts (they are never grown by edit). One edit grows the covering. A drift check compares head, walking-leg and tail counts across the edit, and on drift falls back to the first-pass render of the full plan. | D-081 |
| 5 | New plan-blind critic items: follows the body vs keeps a separate outline; plates sized to this body; consistent coverage (armor: legs covered, no abrupt stop); parts connect; and which animal each part looks like it came from (an open answer scored by code). Recalibrated in 4 iterations; Meta Spark decides (configurable). | D-082 |
| 6 | Validation found three general bugs, all fixed with tests. A model plan's id-prefixed part ("european_rhinoceros_beetle head horn") got no transfer. A tail that became visible counted as drift although the plan has it. Turtles' beaks were not expected. The two affected runs were rerun (`r1_fix`) beside the originals. | D-083 |

### How "parts" became "traits" for the two reviewed complaints (general rules, not image patches)

| Owner's complaint (S3a) | General rule now | Where |
|---|---|---|
| Shell pasted on, not an extension | A covering is material grown from the host's skin over an extent, conforming to the host's body; critic: "follows the body" and "keeps a separate outline" | transfer, compiler, critic |
| Keeps the beetle's shape | A non-homologous shape (elytra) never transfers; only its material | RC-R10-15, `fold_shapes` |
| Armor should cover the legs too | An exoskeleton's default extent is the whole body, with flexible joints; a narrower extent needs a functional reason (`set_extent` rejects an unexplained gap) | RC-R10-16, `transfer_rules.json` |
| Insect scale ignored | Plates are sized to the host's own segments and muscle masses; critic: "sized to this body" | scale rule, critic |
| Horn disconnected | Parts of one donor system connect: a head part pulls the covering onto the head, and the horn grows out of it; critic: "grows out of the covering" | `connect`, compiler, critic |
| V5 moved the horn and read as a rhinoceros | Growth by edit never grows discrete parts (the horn is in the first pass, with identity cues); a drift check guards the edit; critic: "which animal did this part come from" ("rhinoceros" fails, "beetle" passes) | growth, critic |

## Critic recalibration (`benchmark/calibration_s3b/ITERATIONS.md`)

Labels come from the owner's S3a review: beetle-bear all 12 fail ("best: none"), axolotl V1–V5 all 10 good, axolotl V0 excluded (no comment). Together with the 11 S3a gold images: 18 failures, 15 goods.

| Iteration | Change | S3a protocol (pair) | Spark Open | Meta Spark | S3b pair | Configured |
|---|---|---|---|---|---|---|
| 1 (live) | new items | 18/18, 9/15 | 18/18, 9/15 | 18/18, 5/15 | 18/18, 9/15 | |
| 2 (re-score) | empty "gills:" slots are absent; sucker spots are suckers; "salamander" is the axolotl | 18/18, 8/15 | 18/18, 8/15 | 18/18, 5/15 | 18/18, 9/15 | |
| 3 (live) | "laid on top, with a raised rim or a gap at the edge"; conformity items for protective coverings only | 18/18, 11/15 | 18/18, 11/15 | 18/18, 3/15 | 18/18, 11/15 | 18/18, 3/15 |
| 4 (live, fresh) | none | 18/18, 9/15 | 18/18, 9/15 | 18/18, 3/15 | 18/18, 9/15 | **18/18, 3/15** |

What the iterations show:
- **Spark Open:** it calls the pangolin scales on the owner-good axolotls "laid on top" in nearly every image and wording. That alone breaks the S3a pair rule on this set. S3a's own protocol scores 9–11/15 here, so S3a's calibration (0/5 on 11 images) did not generalize, as its report warned.
- **Meta Spark:** alone, it meets the target twice.
- **Configured rule:** Meta Spark decides. Spark Open still answers every image, and its disagreement is kept on each row (`pair_status`). Setting `critic_decision.mode` to `pair` restores the S3a rule.

## Validation table (critic on the kept image; Meta decides)

P pass, F fail, U uncertain, "-" not asked. "Kept":
- `first`: the first render passed, or a repair edit did not improve on it.
- `edited`: the S2 repair edit was kept.
- `growth`: the grown image was kept.
- `first-pass`: growth drifted, and the full-plan render was used instead.

| Run | Set | Kept | follows body | separate outline | grows out | on top | continuous | scattered | sized | wrong scale | legs covered | abrupt stop | connects | part origin (Meta / Spark Open) | other signals |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| beetle bear r1 | tuned | edited | F | F | F | F | F | F | P | P | P | P | - | - (bug: no horn transfer) | none |
| beetle bear r2 | tuned | edited | P | P | P | P | P | P | P | P | P | P | P | rhinoceros beetle / rhinoceros beetle (P) | third animal F ("pill bug") |
| beetle bear r1_fix | tuned | first | P | P | P | P | F | P | P | P | P | P | F | rhinoceros beetle / stag beetle (P) | insect-leg pieces F, covering presence F, third animal F ("pill bug") |
| beetle bear growth r1 | tuned | first-pass | F | F | F | F | F | F | P | P | P | P | P | rhinoceros beetle / rhinoceros beetle (P) | whole animal, second head, extra limb pieces, insect legs, third animal F (the fallback render; false drift, bug) |
| beetle bear growth r2 | tuned | growth | P | P | P | P | P | P | P | P | P | P | P | rhinoceros beetle / rhinoceros beetle (P) | insect-leg pieces F |
| beetle bear growth r1_fix | tuned | growth | P | P | P | P | P | P | P | P | P | P | P | rhinoceros beetle / rhinoceros beetle (P) | third animal F ("pill bug") |
| axolotl pangolin r1 | tuned | first | P | P | P | P | P | P | P | P | - | - | - | - | none |
| axolotl pangolin r2 | tuned | edited | P | P | P | P | P | P | P | P | - | - | - | - | none |
| crab wolf r1 | held out | edited | P | P | F | F | P | P | P | P | P | F | P | armadillo / isopod (F) | third animal F |
| crab wolf r2 | held out | first | P | P | P | P | P | P | P | P | P | P | P | woodlouse / woodlouse (F) | extra limb pieces, antennae, third animal F |
| indian pangolin horse r1 | held out | first | P | P | P | P | P | P | P | P | - | - | - | - | none |
| indian pangolin horse r2 | held out | first | P | P | P | P | P | P | P | P | - | - | - | - | none |
| tortoise goat r1 | held out | edited | - | - | - | - | - | - | - | - | - | - | - | - | none |
| tortoise goat r2 | held out | edited | - | - | - | - | - | - | - | - | - | - | - | - | beak F (data gap, fixed after), stripes F, third animal F |

**Resolution notes:**
- "crab" resolved to *Cancer pagurus* and "tortoise" to *Testudo graeca*. The resolver chose the most common reading itself and listed the alternatives.
- Both were learned live with cited traits:
  - crab: 0/13 citations passed verification, so its traits are model-estimated;
  - Indian pangolin: 10/13 passed;
  - tortoise: 8/13 passed.
- "grey wolf", "wolf" and "goat" were added as aliases of database rows.

## My judgment per image

- **Beetle × bear default r1** (original): no horn in the plan, a bug (the model plan prefixed the part with the donor's id). Whole-body plated armor including the legs; the repair edit added a horn inside a helmet-like plate. It reads as a bear wearing armor. Not good.
- **Default r2:**
  - the plating covers body and legs in bear-sized segments;
  - the horn rises from a head plate that continues into the body plating, so the connection works;
  - the critics' "pill bug" is fair, since the regular transverse bands read as an isopod.
  - Clearly better than every S3a variant on the owner's points (legs, scale, connection); still more armor than skin.
- **Default r1_fix:** the horn is now in the first render. Coverage and scale are good. The critics see insect-leg pieces at the joints and a pill bug.
- **Growth r1** (original): the grown image (kept as `grown_discarded.webp`) looked good to me. It was thrown away by a false drift: the tail became visible, 0→1, and the plan has a tail. The fallback single-pass render is the worst bear of S3b (a beetle-like head plate the critics count as a second head).
- **Growth r2:** the best beetle × bear so far.
  - Smooth glossy plates conform to the bear's back, flanks and legs.
  - The horn stays on the crown of the head, where the first pass put it.
  - Bear face and ears remain.
  - Only insect-leg pieces at the joints flagged. It answers the owner's "if it formed on a bear, how would it look".
- **Growth r1_fix:** the drift fix let the grown image through. Similar to r2 with more segmented banding, hence "pill bug".
- **Axolotl × pangolin r1, r2:**
  - scales now cover crown, back, flanks, legs and tail, with the face, gills and pink belly kept, as on a pangolin;
  - both clean passes;
  - close to the owner's best (S3a V2), with the legs now scaled (the donor's own system).
- **Crab × wolf r1, r2 (held out):**
  - the plating covers body and legs with joints, sized to the wolf, and reads as one system;
  - the crab's planned part, a "segmented tail" from the Malacostraca class list (closer to a lobster than to a crab, which tucks its abdomen under), reads as an isopod or woodlouse tail;
  - r2's body twist is odd.
  - Integration good; donor identity weak: it does not say "crab".
- **Indian pangolin × horse r1, r2 (held out):** the most convincing images of S3b. Overlapping scales conform to the horse's neck, back, flanks and upper legs; the belly, lower legs and face stay horse. Both clean passes.
- **Tortoise × goat r1, r2 (held out):** the tortoise hosted, because RC-R10-01 now gives an equal-structure tie to the first-named parent, and the goat contributed only fur on the shell. A shaggy-shelled tortoise is coherent but a weak "goat". Before RC-R10-01, mass would have made the goat host. The critic's beak flag was a data gap, now fixed.

## Did the held-out pairs improve as much as the tuned pairs?

**On integration, nearly.**

| Final images | Integration answers passing | Clean (no signal) |
|---|---|---|
| Tuned, after fixes (beetle-bear default r2, r1_fix; growth r2, r1_fix; axolotl ×2) | 55/56 (98%) | 2/6 |
| Held out (crab-wolf ×2, Indian pangolin-horse ×2; tortoise-goat has a fur covering and no armor items) | 33/36 (92%) | 2/4 (both horses) |

The same rules (exoskeleton = whole body with joints; pangolin scales leave the belly and face; host-scaled plates) produced coherent, conforming coverings on a wolf and a horse that the critic was never tuned on.

**On donor identity, no.** Where the donor is recognizable by its covering alone (pangolin scales), held-out works as well as tuned. Where identity rests on a discrete part or on the covering's pattern, three things go wrong:
- the crab's tail and a fully plated body read as a woodlouse, pill bug or armadillo (2/2 crab images fail the origin question);
- the bear's full banded plating reads as a pill bug in 3 of 4 post-fix images;
- tortoise × goat shows the host rule can leave the second parent with only a surface trait.

### Is the remaining failure plan, wording or image model?

- **Plan:**
  - a crab needs a crab-identity part (a claw, as a non-homologous part on a forelimb anchor);
  - an exoskeleton covering needs a donor-specific plate pattern cue (beetle: smooth, glossy, few large plates; crab: knobbed carapace), so a whole-body exoskeleton does not default to isopod bands;
  - an equal-structure tie needs a real fitness rule (RC-R10-02, 03), not name order.
- **Wording:** none found this time. The covering wording conformed on every host.
- **Image model:** "armor worn on top" persists in some bear renders. Growth by edit (r2, r1_fix) reduces it most, which supports keeping it as an option.
