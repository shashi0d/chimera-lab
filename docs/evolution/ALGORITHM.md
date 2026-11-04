# ALGORITHM. Chimera Lab evolution engine

Doc: docs/evolution/ALGORITHM.md
Status: spec v2 (Oct 31, 2026), built from docs/evolution/research/R1 to R9 and RESEARCH_SUMMARY.md. v2 (task E4) adds
open-world parents, the function audit (4.5b), the fiction budget (4.5c), design modes and the R9 label vocabulary.
The engine's fixed and adaptable parts are listed in docs/evolution/ENGINE_CONTRACT.md.
Scope: backend engine and API only (no app UI). Build the engine, verify it, then strengthen sources.

## 1. What the engine does

Input: two animals (from images or names), parent order (sire, dam), a design mode (section 3.1), optional user
settings. Names are resolved open-world: chimera_data.json first, then the learned-animal cache, then Muse Spark
plus a GBIF exact match (ENGINE_CONTRACT.md). Every fact about a parent carries its provenance.
Output: one or more creatures, each with a trait plan (genome), a rendered image, an honest label, the real processes it illustrates, and a trace of the rule cards that shaped it.

Design stance: models make the creative decisions; rule cards are guardrails. Hard cards filter. Soft cards add score penalties. Nothing is a silent deterministic override except the hard cards and the documented known-pair overrides.

Meta models used:
- Muse Spark: identify parents, write the first plan, act as crossover and mutation operator, act as the readability critic.
- Muse Image: render each plan.
- SAM 3.1: segment the rendered creature for the silhouette check.

## 2. Rule cards as data

A loader parses every `### RC-...` block in docs/evolution/research/*.md into `data/rule_cards.json`:

```json
{
  "id": "RC-R2-03",
  "doc": "R2_real_hybrids.md",
  "rule": "Donkey sire x horse dam must render as the documented mule ...",
  "applies_to": ["body", "head", "ears", "mane", "limbs", "feet", "tail", "coat_texture"],
  "strength": "hard",
  "status": "VERIFIED",
  "source": "https://..."
}
```

Weights for soft cards: VERIFIED = 1.0, UNVERIFIED = 0.5. Hard cards are always VERIFIED (enforced by verify_research.py).

The loader is the single source of truth. Prompts quote cards by id and text; they never paraphrase them from memory.

## 3. The genome (creature plan)

Every creature is a JSON document. Variation acts on this document; the image is always re-rendered from it (RC-R8-01).

```json
{
  "id": "crt_...",
  "parents": {"sire": "lion", "dam": "tiger"},
  "lineage": {"parent_ids": [], "generation": 0},
  "mode": "hybrid",
  "host": "lion",
  "identity_balance": 0.7,
  "habitat": {"name": "riverine forest", "source": "bridging"},
  "size": {"mass_kg": 210, "flags": []},
  "silhouette": "large cat frame, long body, heavy forequarters, tail with no tuft",
  "traits": {
    "body":         {"op": "BLEND",   "donor": ["lion", "tiger"], "value": 0.5},
    "coat_color":   {"op": "BLEND",   "donor": ["lion", "tiger"], "value": 0.35},
    "coat_pattern": {"op": "OVERLAY", "donor": "tiger", "strength": 0.3, "region": ["flanks", "legs"]},
    "mane":         {"op": "PICK",    "donor": "lion",  "strength": 0.3},
    "tail":         {"op": "PICK",    "donor": "tiger"}
  },
  "labels": ["real hybrid precedent"],
  "processes": ["in-between blend as in real hybrids", "diluted pattern from a non-body donor"],
  "card_trace": ["RC-R1-01", "RC-R2-01", "RC-R2-05", "RC-R2-08"],
  "scores": {}
}
```

Field rules:
- `mode`: `hybrid`, `chimera` or `mythic`. Chosen by routing (section 4.1), never by the model alone.
- `identity_balance`: 0 to 1, share of the creature that reads as the host. Used as an archive axis.
- `traits`: one entry per tag from the shared vocabulary (size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior). Each entry names an operator from section 4.3.
- `card_trace`: every card that changed or blocked something. Shown to the user as "why it looks like this".
- `design_mode`: `realistic`, `speculative` or `mythic` (section 3.1). Set by the user, never by the model.
- `audit`: one entry per function from the function audit (4.5b). Code-owned.
- `licenses`: declared fiction licenses with their compensations (4.5c). Code-owned.

### 3.1 Design modes

| Mode | Fiction budget (RC-R9-10, RC-R9-11) | Route effect | Style |
|---|---|---|---|
| realistic | 0 licenses: every failed check is repaired; anything not repairable is labeled speculative; jobless donor parts are dropped (RC-R9-12) | as routed | natural history illustration |
| speculative (default) | 1 license | as routed | natural history illustration |
| mythic | several (3, a product decision) | a distant pair routes to `mythic` | myth-style part swaps allowed (RC-R7-02) |
| compare | realistic plus one other mode | two creatures, rendered as a pair | each in its own mode |

Every mode adds the prosaic-detail line to the render prompt (RC-R9-15). Color, pattern strength, art style and pose
are free style choices and need no license (R9 3.4).

## 4. The pipeline

### 4.1 Route the pair

```
if (sire, dam) in KNOWN_PAIRS:          mode = hybrid, apply override (section 6)
elif documented cross in chimera_data:  mode = hybrid (real hybrid precedent)
elif same_genus(sire, dam):             mode = hybrid (hybrid candidate, labeled speculative)
elif design_mode == mythic:             mode = mythic
else:                                   mode = chimera
```

Cards: RC-R2-16 (hard), RC-R1-14 (hard), RC-R5-10 (hard), RC-R2-11 (hard).
Genus and the other ranks come from chimera_data.json or, for learned animals, from GBIF only. Routing works for
any pair by taxonomy distance (same genus, family, order, class, phylum); no animal or pair is named in code.
A documented cross comes only from the chimera_data.json hybrids table or data/evo_known_pairs.json. A model's
claim that two animals cross is stored as an "unverified claim" and never counts as precedent.
Parent order is stored and never sorted (RC-R2-01, hard).

### 4.2 Choose the host and silhouette

- Hybrid path: no single host. Use the known-pair override if one exists; otherwise the body frame is a BLEND and region donors are chosen as coherent groups (RC-R2-06).
- Chimera path: the host is the parent with the more structured body schema (four-legged mammal or bird over soft-bodied animals) unless the user picks (RC-R6-08, RC-R6-09, RC-R5-02). The host owns silhouette, size class and limb plan.
- Mythic path: host chosen like the chimera path; part swaps allowed.
- Write the intended silhouette into the plan as one sentence (RC-R7-06).

### 4.3 Assign an operator per trait (R1)

| Trait kind | Hybrid path | Chimera path |
|---|---|---|
| Measurements (size, limb, neck, tail, ear, snout length) | BLEND near midpoint, modest spread; size on log scale (geometric mean) | host value; donor parts keep their own proportions scaled to host size |
| Present-or-absent features (horns, mane, crest, tuft) | PICK one parent or absent | PICK, only if that region is a donor region |
| Base color, contrast | BLEND | host color outside donor patches |
| Pattern over a base | OVERLAY at reduced strength when the pattern donor does not own the body | PATCH: donor color at full strength inside few, large patches whose layout follows the host's body regions |
| Coat texture | PICK or BLEND by region | PATCH by region |
| Linked group: face, ears, pigment | PACKAGE preference: same donor or same direction (soft) | same |
| Behavior | may follow one parent | follows the head donor |

Rules applied here: RC-R1-01 to RC-R1-13, RC-R2-02, RC-R2-07, RC-R5-01 (hard), RC-R5-03 to RC-R5-07, RC-R6-02, RC-R6-05.

Extremes: at most about one trait in four may land outside both parents, and each one gets a `size.flags` or trait flag "beyond both parents" (RC-R1-13, RC-R2-02). Size above both parents is only allowed for a documented direction-specific case (RC-R2-05).

GATE runs before the traits it controls: a fur pattern only shows on furred regions, a mane only where there is hair (RC-R1-07, RC-R1-08).

Chimera donor share is drawn per run, not fixed at 50 percent (RC-R5-03).

### 4.4 Habitat step (R4)

1. Pick habitat: shared by both parents, a bridging niche, or the user's choice (RC-R4-09).
2. Adjust plastic traits only:
   - pattern strength and complexity: closed or forest habitats more patterned, open habitats plainer (RC-R4-01, RC-R4-02)
   - countershading: dark back, light belly by default, stronger in open sunny habitats (RC-R4-05)
   - extremities: larger in hot habitats, shorter in cold ones; body size nudged up in cold (RC-R4-03, RC-R4-04)
   - eyes: larger for night or dusk activity with a bird or reptile head (RC-R4-07)
   - streamlined body and crescent tail only for a fast open-water lifestyle (RC-R4-06)
3. Never change limb count or body-plan class (RC-R4-10).
4. At least one habitat trait must be visible in the image (RC-R4-11).

### 4.5 Physical checks (R3), fixed order

1. Body-plan class of the host (vertebrate, arthropod, soft-bodied).
2. Limb budget: a wing donor on a vertebrate host takes the forelimb slot (RC-R3-01, hard). Four legs plus wings only in mythic or speculative mode with a label (RC-R3-02, hard).
3. Size ceilings: winged creatures above about 40 kg become gliders or flightless, 26 to 75 kg flagged borderline (RC-R3-05); arthropod parts never at large mammal size unless labeled speculative with the reason (RC-R3-09, hard).
4. Flight anatomy: a flyer gets a deep keel or heavy chest, otherwise the wings are labeled non-flying (RC-R3-03, RC-R3-04).
5. Posture: scaled well above the leg donor, straighten and thicken legs; cat legs may stay crouched with heavier muscle (RC-R3-06 to RC-R3-08).
6. Part rendering: tentacles and trunks jointless, longer means thinner (RC-R3-10); tentacle legs on a heavy land animal are speculative (RC-R3-11).

A failed check either repairs the plan or adds a visible label. It never passes silently (RC-R3-12).

### 4.5b Function audit (R9 section 2)

Runs after the physical checks and before the render, so it costs no images (RC-R9-02, hard). Functions:
breathing, feeding, support, movement, heat and senses. Reproduction is not audited: fertility cannot be seen in
an image, and a mule is a real, generally sterile animal.

Each function ends as `pass`, `repaired`, `labeled` or `licensed`, with the cards used. Where an R3, R4, R6 or R9
card covers the case, code decides and cites the card. Otherwise Muse Spark judges, and the entry is marked
"model-judged": at most one Spark call per creature, covering every uncovered function together.

| Function | Code rule | Cards |
|---|---|---|
| breathing | gills on a land or flying creature need an air-breathing system or a wet habitat; donor gills on a lung-breathing land body have no job in air | RC-R9-03, RC-R9-12 |
| breathing at size | a large creature built from small-animal parts shows breathing compensation | RC-R9-07 |
| feeding | diet follows the head donor's mouthparts; mammal teeth must agree with diet; a beak is never a reason to reject | RC-R9-04, RC-R9-05 |
| support | scaled well above the leg donor: thicker or straighter legs; insect parts up to about 70 cm need no license | RC-R3-06 to RC-R3-08, RC-R9-06, RC-R9-08 |
| movement | anatomy matches ability (flight chest, digging forelimbs); every donor part has a job, jobless parts dropped in realistic mode | RC-R3-03, RC-R3-04, RC-R9-12, RC-R9-13 |
| heat | habitat step adjusted extremities and coat | RC-R4-03, RC-R4-04, RC-R4-11 |
| senses | head and eyes visible | RC-R6-03, RC-R6-04 |

The engine never states high oxygen as the settled reason giant insects existed (RC-R9-09, hard).

### 4.5c Fiction budget (R9 section 3)

A license is a declared exception to a named card that R9 section 3.2 lists as bendable. It always carries a
compensation that is written into the plan and the render prompt.

| License | Card bent | Compensation shown |
|---|---|---|
| arthropod parts at large size | RC-R3-09 | thick supporting legs and visible breathing openings or a deep chest |
| six limbs (four legs plus wings) | RC-R3-02 | wings attached with a shoulder structure that can carry them |
| flight above about 40 kg | RC-R3-05 | huge chest and wing muscles |
| gills on a land creature | RC-R9-03 | a wet habitat or a second, air-breathing system |
| tentacles carrying a heavy land body | RC-R3-11 | many thick tentacles, short and low to the ground |

Budget: realistic 0, speculative 1, mythic 3 (RC-R9-10, RC-R9-11). If a plan needs more licenses than its mode
allows, it is repaired down to the budget and anything left is labeled. Licenses go first to needs that cannot be
repaired. A mythic design with licenses carries a label that believability drops with each extra license.

Never licensable, in any mode (R9 3.3): the honesty rules (honest labels, provenance; RC-R1-14, RC-R2-16,
RC-R5-10, RC-R9-01, RC-R9-09) and the believability floor (parts attach to a structure that can carry them,
weight rests on the ground, eyes and head visible, one creature, texture follows the body outline).

### 4.6 Compile the render prompt

The prompt is generated from the plan by code, then lightly polished by Muse Spark. It must include:
- the silhouette sentence and host frame first (RC-R6-01, RC-R7-06)
- head fully visible, clear eyes (RC-R6-03, RC-R6-04)
- donor contribution as surface, patches and signature parts, at the strengths in the plan (RC-R6-02, RC-R6-05)
- pattern flow following the body outline (RC-R7-07)
- bilateral symmetry and recognizable limbs unless the user asked for alien (RC-R6-07)
- the visible habitat trait (RC-R4-11)
- one creature, full body, plain background
- the compensation of every declared license (4.5c)
- the prosaic-detail line, in every mode: natural lighting, ground contact and shadow, normal wear on feet and
  claws (RC-R9-15)

It must never include a franchise character name (RC-R7-10).

### 4.7 Render

Muse Image renders the prompt. One image per plan per round. The plan id and prompt are stored with the image.

### 4.8 Judge

Three checks, each producing a score from 0 to 1:
1. Checklist critic (Muse Spark, image plus a checklist, no plan shown): yes, no or unclear on 4 to 6 visible
   features, generated from the genome (visible traits, licenses and compensations) for every route. A
   hand-written checklist in data/evo_known_pairs.json takes priority. Score = fraction yes, unclear 0.5. The
   same call returns the creature count, the animals the critic sees (for the third-animal check) and a logged
   forced choice. The open critic (name the animals) runs once more as a logged second opinion only (RC-R6-11).
2. Silhouette check: SAM 3.1 mask of the creature, compared with the planned silhouette and host by the critic or a simple shape comparison. This guards against texture bias in model critics (RC-R6-10).
3. Thumbnail check: repeat the critic on a small version of the image (RC-R6-06).

Rule score: each soft card the plan or image violates subtracts its weight (1.0 or 0.5) times a severity from 0 to 1. Hard card violations remove the candidate before rendering where possible.

Total score (design default, tune in tests):

```
quality = 0.4 * critic + 0.3 * silhouette + 0.1 * thumbnail + 0.2 * (1 - normalized_soft_penalty)
```

Periodic human spot checks of critic scores are part of testing (RC-R8-06).

### 4.9 Evolve (R8)

```
seed  = plan from 4.1 to 4.5
loop for R rounds:
    offspring = Muse Spark crossover or mutation of elites (parent plans + relevant cards in prompt)   # RC-R8-02
    offspring = [p for p in offspring if schema_ok(p) and hard_cards_ok(p)]                          # RC-R8-03, RC-R8-10
    offspring = physical_checks(offspring)                                                            # 4.5
    render, judge (4.6 to 4.8)
    place in archive cell by (identity_balance bucket, mode or habitat); keep best per cell           # RC-R8-04, RC-R8-05
show user a few elites from different cells
```

Archive axes (default): identity_balance in 5 buckets x mode or habitat. User actions per round: pick, edit one gene, or branch from any saved creature. Sessions are a few short rounds with small grids (RC-R8-07). Every creature stores parent ids (RC-R8-08).

Batch size and round count are set after a cost test against the Meta API budget. Starting point for that test: 4 offspring per round, 3 rounds.

### 4.10 Output card

Each creature ships with:
- kind, from the RC-R9-01 vocabulary only: `hybrid`, `chimera` or `mythic composite`. The unqualified word hybrid
  is used only on the real-hybrid route; a same-genus pair with no documented cross is a "speculative hybrid".
- label: "real hybrid precedent", "speculative hybrid of close relatives, no documented cross", "speculative chimera, no real-world precedent", or "mythic composite", plus any check labels (six limbs, borderline flight, arthropod size)
- "Can it live?": each audited function, its result and the cards (or "model-judged") behind it
- licenses: each bent rule with its compensation
- provenance per fact: for each parent, where every field came from (chimera_data.json, GBIF, model-estimated)
- processes it illustrates, in plain words (RC-R7-01)
- resemblances: "resembles X (culture)", tagged unverified (RC-R7-10)
- why it looks like this: the card trace with links to sources
- lineage: parents and generation
- the domestication-syndrome idea, if mentioned, is described as a hypothesis (RC-R1-12); fossil-origin stories for myths are described as contested (RC-R7-03); distant-pair chimeras are never called healthy or viable (RC-R5-09)

## 5. API (FastAPI on Modal)

| Method | Path | Does |
|---|---|---|
| POST | /fuse | Two parents (image or name) and order in, routing plus one seed creature out (sections 4.1 to 4.8) |
| POST | /evolve | Creature id and rounds in, archive cells out (4.9) |
| POST | /creature/{id}/edit | Change one gene, re-check, re-render |
| GET | /creature/{id} | Plan, image, label, card trace, lineage |
| GET | /cards | The parsed rule cards |

All plans are validated by code on every endpoint that accepts or produces one.

## 6. Known-pair overrides (hybrid path)

| Sire x dam | Result | Key points | Cards |
|---|---|---|---|
| donkey x horse | mule | horse height, neck and body; donkey short thick head, long ears, short mane, coarse coat, thin limbs, small hooves; tail short-haired at base, longer below | RC-R2-03 (hard) |
| horse x donkey | hinny | close to mule, smaller and more horse-like, shorter horse-shaped ears, fuller mane and tail | RC-R2-04 |
| lion x tiger | liger | size may exceed both parents; tawny coat, faint stripes, reduced or no mane | RC-R2-05, RC-R2-08 (unverified) |
| tiger x lion | tigon | near parent size; same coat logic as liger | RC-R2-05 |
| zebra x horse or donkey | zebroid | non-zebra body and base color, partial stripes on legs, neck and body | RC-R2-07, RC-R2-09 (unverified) |
| polar bear x grizzly (either order) | hybrid bear | long neck, visible tail, small hump, partly furred soles, mostly pale coat | RC-R2-10 (unverified), RC-R2-11 (hard) |
| dromedary x guanaco or llama | cama | intermediate look, no hump guaranteed | RC-R2-13, RC-R2-14 (unverified) |

Note: in the mule row, the donkey is the sire (male donkey x female horse).

## 7. Worked examples (expected behavior)

1. Donkey (sire) x horse (dam). Route: known pair, hybrid. Output: the documented mule. Label: real hybrid precedent. Processes: region mosaic as in mules.
2. Lion (sire) x tiger (dam). Route: known pair. Output: larger than both, tawny, faint stripes on flanks and legs, small or no mane. Never full mane plus full stripes.
3. Lion x eagle. Route: chimera (different classes). Host: lion. Wings replace forelimbs by default; a four-legs-plus-wings version only in mythic mode with a six-limb label. Blended mass far above 40 kg, so wings are display or gliding. Eagle feathers as large patches over the forequarters following the lion's body regions. Label: speculative chimera.
4. Eagle x octopus. Route: chimera. Host: eagle (more structured schema). Octopus contributes skin patches and possibly tentacle-type parts, rendered jointless. Head stays eagle and fully visible. Label: speculative chimera.

## 8. Acceptance tests

Each hard card gets at least one automated test:
- RC-R1-01: no plan field assigns dominance to a whole parent.
- RC-R1-14, RC-R2-16, RC-R5-10: a distant pair always routes to chimera or mythic and carries the speculative label.
- RC-R2-01: A x B and B x A produce different cache keys and can differ.
- RC-R2-03: donkey x horse plan matches the mule override field by field.
- RC-R2-11: polar bear x grizzly routes to hybrid.
- RC-R3-01, RC-R3-02: a vertebrate host with wings has no forelegs unless mode is mythic with the label.
- RC-R3-09: arthropod parts above a size threshold force the speculative label with a reason.
- RC-R5-01: chimera plans contain no BLEND inside a PATCH region.
- RC-R9-01: the card kind is one of hybrid, chimera, mythic composite, and the plain word hybrid appears only on
  the real-hybrid route.
- RC-R9-02: every plan has an audit entry for each of the six functions, none silently failed.
- RC-R9-03: a land creature with gill-only breathing is repaired, licensed or labeled.
- RC-R9-09: no output states high oxygen as the settled reason for giant insects.
- RC-R9-10: license count never exceeds the mode's budget; honesty and floor rules are never licensable.

Resolver tests (mock GBIF fixtures): in database, learned cache, exact match, misspelling, breed, extinct,
ambiguous, not an animal, human, plant, mythic parent, GBIF down. Routing for unknown pairs. Checklist
generation and the output card's "Can it live?" panel.

Plus quality tests on the four worked examples, scored by the critic and checked by a person.

## 9. Not settled yet

- Live tests for the open questions in RESEARCH_SUMMARY.md (Muse Spark as crossover, model texture bias, SAM silhouette check, budget, archive axes).
- Exact weights in the quality formula.
- Threshold for "arthropod part at large mammal size" (the sources give a beetle limit, not a general number).
- Webbed feet and other semi-aquatic traits (no sources yet).
- Unverified cards stay at half weight until a better source or a live test supports them.
