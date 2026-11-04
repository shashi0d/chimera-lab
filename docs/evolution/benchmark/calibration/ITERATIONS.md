# S3a critic calibration: every iteration

Gold set: `../gold_set.json` (11 existing images: 6 known failures, 5 known goods; owner labels via chat review).
Target: every known failure caught by at least one signal; false alarms at most 1 in 5.
A folder name is a hash of the critic instructions plus every gold question, so a wording change is a new folder.
`old/` is the S2 inspect (the plan-worded checklist on Spark Open, creature count, third animals, SAM presence), run once on the same images.
Each folder holds the raw answers per image (`<id>.json`), the exact wording (`wording.json`), the calls (`calls.json`) and the printed result at run time (`scores_at_run.txt`).

| Iteration | Folder | What changed | Calls | Old | Spark Open alone | Meta Spark alone | Pair |
|---|---|---|---|---|---|---|---|
| 1 | `2471b600` | First protocol: describe first plus counts, balanced checklist with copied item text, integration questions for every donor surface | live, 22 per critic set + 11 old | 3/6 caught, 0/5 false alarms | 6/6, 4/5 | 6/6, 2/5 | 6/6, 4/5 |
| 2 | `00027e99` | Answers as a bare ordered list (Spark Open ran to its 8000-token cap on 4 of 11 asks when it copied the question text); one retry on an unreadable answer; negated clauses dropped from descriptions ("no distinct spots or stripes"); wing cases are not wings; a feather ruff is not a mane; integration questions only for protective coverings (RC-R10-12 scope); real hybrids get a "mixing both parents" frame question instead of "a horse body shape" | live, 44 | 3/6, 0/5 | 6/6, 1/5 | 6/6, 1/5 | 6/6, 2/5 |
| 3 | `00027e99` (`scores_iter3_rescore.json`) | Scoring only, same raw answers as iteration 2: one dorsal or eel stripe is not a striped coat (mule false alarm); presence of a soft surface patch (skin, feathers) is informational, like the S2 surface item (eagle x octopus false alarm) | none | 3/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 |
| 4 | `00027e99_confirm` | No change: a fresh live run of the final protocol, because iteration 3 was tuned on iteration 2's answers | live, 44 | 3/6, 0/5 | 6/6, 0/5 | 6/6, 0/5 | **6/6, 0/5** |

Iteration 1's `scores.json` was overwritten by an early re-score with iteration-2 rules; its run-time result is kept verbatim in `2471b600/scores_at_run.txt`, and `2471b600/rescore_iter2_rules.json` shows those answers under the iteration-2 rules (6/6, 2/5 for the pair).

Caveat: 11 images is a small set, and iterations 2 and 3 were adjusted after seeing these images. Iteration 4 shows the result is stable across fresh calls, not that it generalizes. The experiment images (part 8) and the owner's ratings are the first out-of-sample check.
