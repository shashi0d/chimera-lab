# ENGINE CONTRACT. What is fixed and what adapts

Doc: docs/evolution/ENGINE_CONTRACT.md (task E4, Oct 31, 2026). Spec details: ALGORITHM.md v2.

Principle: the science rules are fixed; inputs, knowledge, routing data, judging and style adapt. No animal or
pair is named in engine logic. Pair knowledge lives in data files (`data/evo_known_pairs.json`, the
`chimera_data.json` hybrids table); animal knowledge lives in `data/chimera_data.json` and
`data/learned_animals.json`.

## Fixed (never bent, in any mode)

| Rule | Where enforced |
|---|---|
| Hard rule cards (17, `data/rule_cards.json`) | `checks.hard_violations` filters every plan before any render |
| Honest labels: a speculative or mythic creature is never presented as real or predicted; labels come from the RC-R9-01 vocabulary (hybrid, chimera, mythic composite) | routing labels, output card `kind` |
| Provenance: every fact shows where it came from; model-estimated facts are marked | resolver, output card `provenance` |
| Parent order (sire, dam) is stored and never sorted | RC-R2-01, cache keys |
| Believability floor (R9 3.3): parts attach to a structure that can carry them, weight rests on the ground, eyes and head visible, one creature, texture follows the body outline | prompt compiler, checklist critic; never licensable |

## Adapts

| Area | Behavior |
|---|---|
| Input | Common, scientific, misspelled or regional names, breeds, extinct species, photos. Order: chimera_data.json, then the learned cache, then the open-world path (Muse Spark identifies, GBIF confirms). |
| Ambiguity | A name with several species ("pangolin"): pick the most common species, state the choice, return the alternatives. A name GBIF cannot match exactly returns `needs_choice` with alternatives. Never guess. |
| Knowledge | Per-field provenance: taxonomy from `chimera_data.json` or GBIF (source `gbif`); body and life traits from chimera_data.json or Muse Spark (`model-estimated`). A breed takes its species' taxonomy and keeps its breed look as visible features. |
| Learning | Newly resolved animals are saved to `data/learned_animals.json` with provenance and a timestamp, reused on the next request, and never silently overwritten. |
| Routing | By taxonomy distance: known pair or documented cross (data files only) is a real hybrid; same genus is a hybrid candidate; everything else is a chimera, or a mythic composite in mythic mode. A model's claim of a cross is stored as an "unverified claim" and never counts as precedent. |
| Judging | A checklist critic generated from each plan (visible traits, licenses, compensations); hand-written pair checklists take priority. The open critic is kept as a logged second opinion. |
| Style | By mode: realistic (0 licenses), speculative (1), mythic (several), compare (realistic plus one other). Color, pattern strength, art style and pose are free. |
| Limits | Refused with a clear reason: not an animal, a plant, a human, a mythic creature as a parent (suggest mythic mode with real animals instead). |
| Failure | Graceful fallbacks: GBIF unreachable means taxonomy unknown, so the pair routes as a chimera with the speculative label; a failed model plan falls back to the code skeleton; a failed audit judgment is labeled, not hidden; budget caps stop the run with a clear error. |

## Calls per request (live)

| Step | Muse Spark | GBIF | Muse Image | SAM 3.1 |
|---|---|---|---|---|
| Resolve a name in the database or learned cache | 0 | 0 | 0 | 0 |
| Resolve a new animal (identify, fill traits) | 2 | 1 | 0 | 0 |
| Fuse one creature: first plan, polish, checklist (full, thumbnail), open critic | 5 | 0 | 1 | 1 |
| Function audit, only if a function has no covering card | at most 1 | 0 | 0 | 0 |
| Third-animal re-render (once at most) | +3 | 0 | +1 | +1 |
