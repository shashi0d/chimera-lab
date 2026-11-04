# S3b critic recalibration: every iteration

Set: `../gold_set_s3b.json` has 33 images and 18 failures / 15 goods. It holds the S3a gold set (11 images, chat-review labels) and the 22 S3a experiment images the owner reviewed (`../s3a_owner_review.md`).
- **Beetle-bear:** "best: none", so all 12 are failures.
- **Axolotl-pangolin:** "all V1 to V5 work", so the 10 images are goods. Axolotl V0 has no owner comment, so its 2 images are excluded.

Target, as in S3a: every failure caught; false alarms at most 1 in 5 (3 of 15).

Systems scored on the same raw answers:
- `s3a_pair`: the S3a protocol (the S3b questions removed), both critics, disagreement as a fail signal.
- `s3b_<critic>`: the full S3b protocol, one critic alone.
- `s3b_pair`: the full protocol under the S3a rule.
- `s3b_configured`: the rule in `data/evo_config.json` (`critic_decision`).

A folder name hashes the instructions, every question and every origin part.

| Iteration | Folder | What changed | Calls | s3a_pair | Spark Open alone | Meta alone | s3b_pair | configured |
|---|---|---|---|---|---|---|---|---|
| 1 | `cf77b9fe` | New items: follows the body or keeps a separate outline; plates sized to the body; legs covered and abrupt stop (armor only); parts connect; which animal each part came from. Placement beyond a bare plan-region extent is informational. | live, 132 | 18/18, 9/15 false alarms | 18/18, 9/15 | 18/18, 5/15 | 18/18, 9/15 | (pair) |
| 2 | `cf77b9fe` (`scores_iter2.json`) | Scoring only: a part listed with an empty or "none ..." description is absent (Spark Open lists "gills:" to say none); octopus "sucker-like spots" are suckers; "salamander" is a group word for the axolotl. | none | 18/18, 8/15 | 18/18, 8/15 | 18/18, 5/15 | 18/18, 9/15 | (pair) |
| 3 | `7aa37f22` | Wording: "laid on top ... with a raised rim or a gap at the edge" (the visible difference between pasted and grown); the conformity items apply only to protective coverings, like the S3a integration items. | live, 132 | 18/18, 11/15 | 18/18, 11/15 | **18/18, 3/15** | 18/18, 11/15 | 18/18, 3/15 |
| 4 | `7aa37f22_confirm` | No change: a fresh live run. | live, 132 | 18/18, 9/15 | 18/18, 9/15 | **18/18, 3/15** | 18/18, 9/15 | **18/18, 3/15** |

## Findings

1. **Every failure is caught by every system in every iteration (18/18).** The new items name the owner's reasons:
   - beetle-bear: "keeps the outline of a separate object" and "does not follow the body's shape" (pasted on); "stops abruptly with no visible reason" (legs bare);
   - V5: the origin question names a rhinoceros for the horn (the "rhinoceros x bear" complaint, caught in iteration 1 by Spark Open, uncertain in the pair).
2. **The false alarms come from Spark Open, not Meta.** Spark Open calls the pangolin scales on the axolotl "laid on top" in 8 to 10 of the 10 owner-good images, in every wording. Meta Spark alone meets the target in iterations 3 and 4 (3/15 both times).
3. **The S3a pair rule does not hold on this broader set.** S3a's own protocol scores 9 to 11 false alarms of 15 here. The S3a calibration (11 images, 0/5 false alarms) did not generalize to the owner-good axolotl images, as its report warned it might not.
4. **The configured rule is now "Meta decides" (`critic_decision: primary, meta_spark`).**
   - Spark Open still answers every image, and its disagreement is kept on each row as `pair_status`.
   - This departs from the S3a rule ("disagreement is a fail signal"), which the owner set. It is the configuration that meets the target on the owner's labels, and it is flagged for owner confirmation in DECISIONS (D-082).
   - Setting `mode` to `pair` restores the S3a rule.
5. **The remaining false alarms vary between runs**, except axolotl V2 r2 (Meta: the scales sit on top, plus head spots), which both runs flag.
   - Iteration 3 flagged V2 r2, V3 r2 and V5 r1 ("lizard" as a third animal).
   - Iteration 4 flagged V2 r2, V1 r1 and the e2c mule frame.
   - The owner's own V1 note preferred the second image, so V1 r1 is a borderline label.
6. **Iteration 1's answers cannot be re-scored under the iteration-3 wording:** the reworded question has no cached answer. That re-score was discarded.

Caveat: iterations 2 and 3 were adjusted after seeing these images; iteration 4 shows stability, not generality. The held-out pairs in the validation run (part 6) are the first images the S3b critic has not been tuned on.
