# E1-offline: evolution engine built against mocks

Date: 2026-10-31. Branch: `evo`. Spec: `docs/evolution/ALGORITHM.md` (v1).
No live API call was made in this session. Every Spark, image and SAM call below ran on a mock.

## What was built

| Step | Result | Commit |
|---|---|---|
| 0. Docs and verification | `scripts/verify_research.py` written (stdlib only). Gate passed on run 4 after 3 authorized source fixes. See `VERIFY_REPORT.md`. | 98d4d8c, 813f05c, 3acc4de |
| 1. Reading | Only ALGORITHM.md, the adapter base, mocks, usage, config, and a script over the taxonomy fields. R docs read only through the loader output. | (no files changed) |
| 2. Engine | `backend/app/evolution/` (14 modules), `scripts/build_rule_cards.py` producing `data/rule_cards.json` (94 cards, 11 hard), overrides and tables as data (`data/evo_known_pairs.json`, `data/evo_config.json`), 5 endpoints under `/evo`. | 23ccc42 |
| 3. Tests | 85 new tests in `backend/tests/evolution/`. | 5b3ee73 |

Module map, in pipeline order: `data.py` (cards, taxonomy, tables), `genome.py` (section 3), `route.py` (4.1, 4.2), `traits.py` (4.3 with GATE), `habitat.py` (4.4), `physics.py` (4.5), `prompt.py` (4.6), `checks.py` (hard filters, soft penalties), `judge.py` (4.8), `engine.py` (4.7, 4.9, edits, store), `card.py` (4.10), `adapters.py` (Spark and SAM protocols, mocks, call meter), `api.py` (section 5).

Existing pipeline steps and the frontend are untouched. The only change outside the new module is two lines in `backend/app/main.py` that mount the router.

## Test results

```
backend: 217 passed, 6 skipped (live, off by default) in 20.9s
  existing suite: 132 passed, unchanged
  new evolution tests: 85 passed
ruff: all checks passed on backend/app/evolution, tests/evolution and the two scripts
```

Hard-card coverage (section 8). Each card has at least one test in `tests/evolution/test_hard_cards.py`:

| Card | What the test asserts |
|---|---|
| RC-R1-01 | The schema rejects any dominance field. Every worked plan draws traits from both parents. A plan with every trait from one parent is blocked. |
| RC-R1-14, RC-R2-16, RC-R5-10 | A sweep of every ordered pair among the 200 animals (more than 30,000 distant pairs, each with and without myth) routes to chimera or mythic and carries the speculative label. Plans that lose the label or are switched to hybrid are blocked. |
| RC-R2-01 | `cache_key(A,B) != cache_key(B,A)`. Lion x tiger (liger, 321 kg) and tiger x lion (tigon) differ. Swapped parents are blocked. |
| RC-R2-03 | Donkey x horse matches the mule override field by field for seeds 0 to 4, including horse mass. An edit to a mule field is refused with RC-R2-03. |
| RC-R2-11 | Polar bear x grizzly routes to hybrid in both orders and by alias. A chimera-mode copy is blocked. |
| RC-R3-01, RC-R3-02 | The lion x eagle chimera has wings in the forelimb slot (4 limbs). The mythic version has 6 limbs and the label. Removing the label, or adding 4 legs plus wings in chimera mode, is blocked; the physics step repairs the latter. |
| RC-R3-09 | Tiger x emperor scorpion at 257 kg gets the arthropod label, with "insect breathing limits size" as the reason. Stripping the label blocks the plan. |
| RC-R5-01 | No BLEND inside a PATCH region in chimera or mythic plans. An injected BLEND is blocked. In evolve, invalid offspring are dropped before render, so no image is spent on them. |

Mutation check: disabling the RC-R5-01 check, or the RC-R3-01 limb repair, made 16 tests fail. Both changes were reverted.

Worked examples (`test_worked_examples.py`): each of the 4 examples is asserted for routing, host, limb plan and label over seeds 0 to 9, plus the example's own claims. Examples: liger larger than both parents; tawny coat leaning lion; faint stripes only on flanks and legs; never a full mane with full stripes; eagle feathers starting at the forequarters; octopus tentacles jointless; heads stay with the host. The mythic six-limb variant is tested too.

Section 8 also asks for "quality tests on the four worked examples, scored by the critic and checked by a person". That needs real images and was not done here. The mock critic only shows that the scoring path runs.

## The 4 worked-example plans (mock mode, seed 0)

Generated with `/fuse` code paths in mock mode. `scores` come from the mock critic and mock SAM, so they say nothing about real image quality.

| Example | Route | Host | Limb plan | Label |
|---|---|---|---|---|
| 1. donkey x horse | hybrid, known pair `mule` | horse | legs + legs (4) | real hybrid precedent |
| 2. lion x tiger | hybrid, known pair `liger` | lion | legs + legs (4) | real hybrid precedent |
| 3. lion x eagle | chimera | lion | eagle wings (forelimb slot) + legs (4), display or gliding at 199 kg | speculative chimera, no real-world precedent; non-flying wings |
| 4. eagle x octopus | chimera | golden eagle | wings + legs (4), octopus tentacles in place of the tail | speculative chimera, no real-world precedent |

### 1. donkey x horse

```json
{
  "id": "crt_0c92d85dfa6f",
  "parents": {
    "sire": "donkey",
    "dam": "horse"
  },
  "lineage": {
    "parent_ids": [],
    "generation": 0
  },
  "mode": "hybrid",
  "known_pair": "mule",
  "host": "horse",
  "identity_balance": 0.258,
  "habitat": {
    "name": "dry woodland",
    "source": "bridging",
    "adjustments": [
      "more patterned, irregular coat markings for a closed habitat",
      "dark back and light belly (mild countershading)",
      "larger ears and longer tail for shedding heat"
    ],
    "visible_trait": "larger ears and longer tail for shedding heat"
  },
  "size": {
    "mass_kg": 563.5,
    "flags": []
  },
  "silhouette": "horse-height equine frame with the horse's neck and body, a short thick donkey head with long ears, a short upright mane, thin limbs on small hooves",
  "limb_plan": {
    "forelimbs": {
      "kind": "legs",
      "donor": null
    },
    "hindlimbs": {
      "kind": "legs",
      "donor": null
    },
    "extra_wings": null,
    "appendages": [],
    "wing_use": "none",
    "requested_wings": null
  },
  "traits": {
    "size": {
      "op": "BLEND",
      "donor": [
        "donkey",
        "horse"
      ],
      "value": 0.5,
      "strength": null,
      "region": null,
      "part": null,
      "note": "geometric mean of parent masses",
      "flags": []
    },
    "body": {
      "op": "PICK",
      "donor": "horse",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "horse neck shape and body",
      "flags": []
    },
    "head": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "short thick donkey head",
      "flags": []
    },
    "face": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "ears": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "long donkey ears",
      "flags": []
    },
    "skull": {
      "op": "BLEND",
      "donor": [
        "donkey",
        "horse"
      ],
      "value": 0.35,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "mane": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "short donkey mane",
      "flags": []
    },
    "tail": {
      "op": "BLEND",
      "donor": [
        "donkey",
        "horse"
      ],
      "value": 0.5,
      "strength": null,
      "region": null,
      "part": null,
      "note": "tail short-haired at the base and longer below",
      "flags": []
    },
    "limbs": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "thin donkey limbs",
      "flags": []
    },
    "feet": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "small donkey hooves",
      "flags": []
    },
    "coat_color": {
      "op": "BLEND",
      "donor": [
        "donkey",
        "horse"
      ],
      "value": 0.51,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "coat_pattern": {
      "op": "OVERLAY",
      "donor": "donkey",
      "value": null,
      "strength": 0.5,
      "region": [
        "flanks",
        "legs"
      ],
      "part": null,
      "note": "reduced: the pattern donor does not own the body",
      "flags": [
        "habitat pattern +0.10"
      ]
    },
    "coat_texture": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "coarse donkey coat",
      "flags": []
    },
    "behavior": {
      "op": "PICK",
      "donor": "donkey",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "behavior may follow one parent",
      "flags": []
    }
  },
  "labels": [
    "real hybrid precedent"
  ],
  "processes": [
    "region mosaic as in mules"
  ],
  "card_trace": [
    "RC-R2-01",
    "RC-R2-16",
    "RC-R2-03",
    "RC-R2-06",
    "RC-R1-01",
    "RC-R1-02",
    "RC-R1-04",
    "RC-R1-05",
    "RC-R1-06",
    "RC-R1-11",
    "RC-R2-02",
    "RC-R2-07",
    "RC-R2-15",
    "RC-R4-09",
    "RC-R4-01",
    "RC-R4-02",
    "RC-R4-05",
    "RC-R4-04",
    "RC-R4-11",
    "RC-R4-10",
    "RC-R3-12",
    "RC-R6-01",
    "RC-R7-06",
    "RC-R6-03",
    "RC-R6-04",
    "RC-R6-02",
    "RC-R6-05",
    "RC-R7-07",
    "RC-R6-07",
    "RC-R7-10"
  ],
  "checks": [
    {
      "step": "body_plan_class",
      "result": "pass",
      "detail": "host class: vertebrate (quadruped)",
      "cards": []
    },
    {
      "step": "limb_budget",
      "result": "pass",
      "detail": "4 limbs",
      "cards": []
    },
    {
      "step": "size_ceiling",
      "result": "pass",
      "detail": "within ceilings",
      "cards": []
    },
    {
      "step": "flight_anatomy",
      "result": "pass",
      "detail": "no wings",
      "cards": []
    },
    {
      "step": "posture",
      "result": "pass",
      "detail": "limbs fixed by a documented known-pair override; posture left as documented",
      "cards": [
        "RC-R2-03"
      ]
    },
    {
      "step": "part_rendering",
      "result": "pass",
      "detail": "no soft parts",
      "cards": []
    }
  ],
  "scores": {
    "critic": 1.0,
    "silhouette": 1.0,
    "thumbnail": 0.5,
    "soft_penalty": 0.0,
    "quality": 0.95
  },
  "seed": 0
}
```

### 2. lion x tiger

```json
{
  "id": "crt_0a2c41cf1b99",
  "parents": {
    "sire": "lion",
    "dam": "tiger"
  },
  "lineage": {
    "parent_ids": [],
    "generation": 0
  },
  "mode": "hybrid",
  "known_pair": "liger",
  "host": "lion",
  "identity_balance": 0.673,
  "habitat": {
    "name": "grassland",
    "source": "shared",
    "adjustments": [
      "plainer coat with fewer markings for an open habitat",
      "dark back and light belly (strong countershading)"
    ],
    "visible_trait": "plainer coat with fewer markings for an open habitat"
  },
  "size": {
    "mass_kg": 321.2,
    "flags": [
      "beyond both parents"
    ]
  },
  "silhouette": "very large cat frame, longer and heavier than either parent, long body, heavy forequarters, small or no mane",
  "limb_plan": {
    "forelimbs": {
      "kind": "legs",
      "donor": null
    },
    "hindlimbs": {
      "kind": "legs",
      "donor": null
    },
    "extra_wings": null,
    "appendages": [],
    "wing_use": "none",
    "requested_wings": null
  },
  "traits": {
    "size": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.5,
      "strength": null,
      "region": null,
      "part": null,
      "note": "geometric mean of parent masses",
      "flags": []
    },
    "body": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.5,
      "strength": null,
      "region": null,
      "part": null,
      "note": "long heavy cat body",
      "flags": []
    },
    "head": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "face": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "ears": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.35,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "skull": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.35,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "mane": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": 0.3,
      "region": null,
      "part": null,
      "note": "reduced mane or none",
      "flags": []
    },
    "tail": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.53,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "limbs": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": -0.1,
      "strength": null,
      "region": null,
      "part": null,
      "note": "slightly past the lion's proportions, beyond both parents",
      "flags": [
        "beyond both parents"
      ]
    },
    "feet": {
      "op": "PICK",
      "donor": "tiger",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "coat_color": {
      "op": "BLEND",
      "donor": [
        "lion",
        "tiger"
      ],
      "value": 0.25,
      "strength": null,
      "region": null,
      "part": null,
      "note": "tawny, lion-like base",
      "flags": []
    },
    "coat_pattern": {
      "op": "OVERLAY",
      "donor": "tiger",
      "value": null,
      "strength": 0.2,
      "region": [
        "flanks",
        "legs"
      ],
      "part": null,
      "note": "faint tiger stripes",
      "flags": [
        "habitat pattern -0.10"
      ]
    },
    "coat_texture": {
      "op": "PICK",
      "donor": "tiger",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "behavior": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "behavior may follow one parent",
      "flags": []
    }
  },
  "labels": [
    "real hybrid precedent"
  ],
  "processes": [
    "in-between blend as in real hybrids",
    "diluted pattern from a non-body donor",
    "growth beyond both parents in one cross direction"
  ],
  "card_trace": [
    "RC-R2-01",
    "RC-R2-16",
    "RC-R2-05",
    "RC-R2-08",
    "RC-R2-06",
    "RC-R1-01",
    "RC-R1-02",
    "RC-R1-04",
    "RC-R1-05",
    "RC-R1-06",
    "RC-R1-11",
    "RC-R2-02",
    "RC-R2-07",
    "RC-R2-15",
    "RC-R1-13",
    "RC-R4-01",
    "RC-R4-02",
    "RC-R4-05",
    "RC-R4-11",
    "RC-R4-10",
    "RC-R3-12",
    "RC-R6-01",
    "RC-R7-06",
    "RC-R6-03",
    "RC-R6-04",
    "RC-R6-02",
    "RC-R6-05",
    "RC-R7-07",
    "RC-R6-07",
    "RC-R7-10"
  ],
  "checks": [
    {
      "step": "body_plan_class",
      "result": "pass",
      "detail": "host class: vertebrate (quadruped)",
      "cards": []
    },
    {
      "step": "limb_budget",
      "result": "pass",
      "detail": "4 limbs",
      "cards": []
    },
    {
      "step": "size_ceiling",
      "result": "pass",
      "detail": "within ceilings",
      "cards": []
    },
    {
      "step": "flight_anatomy",
      "result": "pass",
      "detail": "no wings",
      "cards": []
    },
    {
      "step": "posture",
      "result": "pass",
      "detail": "legs match the body size",
      "cards": []
    },
    {
      "step": "part_rendering",
      "result": "pass",
      "detail": "no soft parts",
      "cards": []
    }
  ],
  "scores": {
    "critic": 1.0,
    "silhouette": 1.0,
    "thumbnail": 0.5,
    "soft_penalty": 0.167,
    "quality": 0.917
  },
  "seed": 0
}
```

### 3. lion x eagle

```json
{
  "id": "crt_5c03aa1df608",
  "parents": {
    "sire": "lion",
    "dam": "golden_eagle"
  },
  "lineage": {
    "parent_ids": [],
    "generation": 0
  },
  "mode": "chimera",
  "known_pair": null,
  "host": "lion",
  "identity_balance": 0.881,
  "habitat": {
    "name": "forest",
    "source": "shared",
    "adjustments": [
      "more patterned, irregular coat markings for a closed habitat",
      "dark back and light belly (mild countershading)"
    ],
    "visible_trait": "more patterned, irregular coat markings for a closed habitat"
  },
  "size": {
    "mass_kg": 199.0,
    "flags": []
  },
  "silhouette": "horizontal lion frame carried on two hind legs, golden eagle wings in place of the forelegs",
  "limb_plan": {
    "forelimbs": {
      "kind": "wings",
      "donor": "golden_eagle"
    },
    "hindlimbs": {
      "kind": "legs",
      "donor": "lion"
    },
    "extra_wings": null,
    "appendages": [],
    "wing_use": "gliding_or_display",
    "requested_wings": null
  },
  "traits": {
    "size": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "host value; donor parts scaled to host size",
      "flags": []
    },
    "body": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "host value; donor parts scaled to host size",
      "flags": []
    },
    "limbs": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "tail": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "host value; donor parts scaled to host size",
      "flags": []
    },
    "ears": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "skull": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "head": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "face": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "mane": {
      "op": "PICK",
      "donor": null,
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "absent: no hair on the neck",
      "flags": [
        "gated"
      ]
    },
    "feet": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "coat_pattern": {
      "op": "PATCH",
      "donor": "golden_eagle",
      "value": null,
      "strength": 1.0,
      "region": [
        "forequarters",
        "neck"
      ],
      "part": null,
      "note": "golden eagle pattern in few large patches following the lion's body regions",
      "flags": []
    },
    "coat_color": {
      "op": "PATCH",
      "donor": "golden_eagle",
      "value": null,
      "strength": 1.0,
      "region": [
        "forequarters",
        "neck"
      ],
      "part": null,
      "note": "golden eagle color in few large patches following the lion's body regions",
      "flags": []
    },
    "coat_texture": {
      "op": "PATCH",
      "donor": "golden_eagle",
      "value": null,
      "strength": 1.0,
      "region": [
        "forequarters",
        "neck"
      ],
      "part": null,
      "note": "golden eagle feathers in few large patches following the lion's body regions",
      "flags": []
    },
    "behavior": {
      "op": "PICK",
      "donor": "lion",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "follows the head donor",
      "flags": []
    }
  },
  "labels": [
    "speculative chimera, no real-world precedent",
    "non-flying wings: display or gliding only"
  ],
  "processes": [
    "chimera patchwork: each region is one parent's tissue"
  ],
  "card_trace": [
    "RC-R2-01",
    "RC-R1-14",
    "RC-R2-16",
    "RC-R5-10",
    "RC-R6-08",
    "RC-R6-09",
    "RC-R5-02",
    "RC-R1-01",
    "RC-R1-09",
    "RC-R1-10",
    "RC-R5-01",
    "RC-R5-03",
    "RC-R5-04",
    "RC-R5-05",
    "RC-R5-06",
    "RC-R5-07",
    "RC-R6-02",
    "RC-R1-07",
    "RC-R1-08",
    "RC-R4-01",
    "RC-R4-02",
    "RC-R4-05",
    "RC-R4-11",
    "RC-R4-10",
    "RC-R3-12",
    "RC-R3-01",
    "RC-R3-05",
    "RC-R3-03",
    "RC-R3-04",
    "RC-R6-01",
    "RC-R7-06",
    "RC-R6-03",
    "RC-R6-04",
    "RC-R6-05",
    "RC-R7-07",
    "RC-R6-07",
    "RC-R7-10"
  ],
  "checks": [
    {
      "step": "body_plan_class",
      "result": "pass",
      "detail": "host class: vertebrate (quadruped)",
      "cards": []
    },
    {
      "step": "limb_budget",
      "result": "repaired",
      "detail": "golden eagle wings take the forelimb slot",
      "cards": [
        "RC-R3-01"
      ]
    },
    {
      "step": "size_ceiling",
      "result": "labeled",
      "detail": "199.0 kg is above about 40 kg: wings for display or gliding",
      "cards": [
        "RC-R3-05"
      ]
    },
    {
      "step": "flight_anatomy",
      "result": "labeled",
      "detail": "too heavy for its flight muscles: wings labeled non-flying",
      "cards": [
        "RC-R3-03",
        "RC-R3-04"
      ]
    },
    {
      "step": "posture",
      "result": "pass",
      "detail": "legs match the body size",
      "cards": []
    },
    {
      "step": "part_rendering",
      "result": "pass",
      "detail": "no soft parts",
      "cards": []
    }
  ],
  "scores": {
    "critic": 1.0,
    "silhouette": 1.0,
    "thumbnail": 1.0,
    "soft_penalty": 0.0,
    "quality": 1.0
  },
  "seed": 0
}
```

### 4. eagle x octopus

```json
{
  "id": "crt_efccdacdfc86",
  "parents": {
    "sire": "golden_eagle",
    "dam": "common_octopus"
  },
  "lineage": {
    "parent_ids": [],
    "generation": 0
  },
  "mode": "chimera",
  "known_pair": null,
  "host": "golden_eagle",
  "identity_balance": 0.881,
  "habitat": {
    "name": "rocky coast",
    "source": "bridging",
    "adjustments": [
      "plainer coat with fewer markings for an open habitat",
      "dark back and light belly (strong countershading)"
    ],
    "visible_trait": "plainer coat with fewer markings for an open habitat"
  },
  "size": {
    "mass_kg": 4.5625,
    "flags": []
  },
  "silhouette": "upright golden eagle frame on two legs, tentacles in place of the tail",
  "limb_plan": {
    "forelimbs": {
      "kind": "wings",
      "donor": "golden_eagle"
    },
    "hindlimbs": {
      "kind": "legs",
      "donor": "golden_eagle"
    },
    "extra_wings": null,
    "appendages": [
      "tentacles (tail)"
    ],
    "wing_use": "powered",
    "requested_wings": null
  },
  "traits": {
    "size": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "host value; donor parts scaled to host size",
      "flags": []
    },
    "body": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "host value; donor parts scaled to host size; deep keel and heavy flight chest",
      "flags": []
    },
    "limbs": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "tail": {
      "op": "PICK",
      "donor": "common_octopus",
      "value": null,
      "strength": null,
      "region": null,
      "part": "tentacles",
      "note": "signature part of the second parent; jointless and smoothly curving; longer means thinner",
      "flags": []
    },
    "ears": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "skull": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "head": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "face": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "mane": {
      "op": "PICK",
      "donor": null,
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "absent: no hair on the neck",
      "flags": [
        "gated"
      ]
    },
    "feet": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": null,
      "flags": []
    },
    "coat_pattern": {
      "op": "PATCH",
      "donor": "common_octopus",
      "value": null,
      "strength": 1.0,
      "region": [
        "belly",
        "flanks"
      ],
      "part": null,
      "note": "common octopus pattern in few large patches following the golden eagle's body regions",
      "flags": []
    },
    "coat_color": {
      "op": "PATCH",
      "donor": "common_octopus",
      "value": null,
      "strength": 1.0,
      "region": [
        "belly",
        "flanks"
      ],
      "part": null,
      "note": "common octopus color in few large patches following the golden eagle's body regions",
      "flags": []
    },
    "coat_texture": {
      "op": "PATCH",
      "donor": "common_octopus",
      "value": null,
      "strength": 1.0,
      "region": [
        "belly",
        "flanks"
      ],
      "part": null,
      "note": "common octopus skin in few large patches following the golden eagle's body regions",
      "flags": []
    },
    "behavior": {
      "op": "PICK",
      "donor": "golden_eagle",
      "value": null,
      "strength": null,
      "region": null,
      "part": null,
      "note": "follows the head donor",
      "flags": []
    }
  },
  "labels": [
    "speculative chimera, no real-world precedent"
  ],
  "processes": [
    "chimera patchwork: each region is one parent's tissue"
  ],
  "card_trace": [
    "RC-R2-01",
    "RC-R1-14",
    "RC-R2-16",
    "RC-R5-10",
    "RC-R6-08",
    "RC-R6-09",
    "RC-R5-02",
    "RC-R1-01",
    "RC-R1-09",
    "RC-R1-10",
    "RC-R5-01",
    "RC-R5-03",
    "RC-R5-04",
    "RC-R5-05",
    "RC-R5-06",
    "RC-R5-07",
    "RC-R6-02",
    "RC-R6-05",
    "RC-R1-07",
    "RC-R1-08",
    "RC-R4-09",
    "RC-R4-01",
    "RC-R4-02",
    "RC-R4-05",
    "RC-R4-11",
    "RC-R4-10",
    "RC-R3-12",
    "RC-R3-05",
    "RC-R3-03",
    "RC-R3-04",
    "RC-R3-10",
    "RC-R6-01",
    "RC-R7-06",
    "RC-R6-03",
    "RC-R6-04",
    "RC-R7-07",
    "RC-R6-07",
    "RC-R7-10"
  ],
  "checks": [
    {
      "step": "body_plan_class",
      "result": "pass",
      "detail": "host class: vertebrate (biped|winged)",
      "cards": []
    },
    {
      "step": "limb_budget",
      "result": "pass",
      "detail": "4 limbs",
      "cards": []
    },
    {
      "step": "size_ceiling",
      "result": "pass",
      "detail": "within ceilings",
      "cards": [
        "RC-R3-05"
      ]
    },
    {
      "step": "flight_anatomy",
      "result": "repaired",
      "detail": "flyer gets a deep keel and heavy chest",
      "cards": [
        "RC-R3-03"
      ]
    },
    {
      "step": "posture",
      "result": "pass",
      "detail": "legs match the body size",
      "cards": []
    },
    {
      "step": "part_rendering",
      "result": "repaired",
      "detail": "jointless soft parts: tail",
      "cards": [
        "RC-R3-10"
      ]
    }
  ],
  "scores": {
    "critic": 1.0,
    "silhouette": 1.0,
    "thumbnail": 1.0,
    "soft_penalty": 0.0,
    "quality": 1.0
  },
  "seed": 0
}
```

## Meta calls for one live run of the 4 examples

Counted from the code path: every adapter call goes through `Meter` (`backend/app/evolution/adapters.py`), and the counts below are what the mock run recorded. The live path would make the same calls in the same order.

Per `/fuse` with both parents given by name (the order recorded for each example):

```
spark:first_plan -> spark:polish -> image:render -> spark:critic -> sam:segment -> spark:critic_thumbnail
```

| | Spark | Images | SAM |
|---|---|---|---|
| Each example, names as input | 4 | 1 | 1 |
| **One live run of the 4 examples (names)** | **16** | **4** | **4** |
| Same run with photos for both parents (+1 Spark identify per parent) | 24 | 4 | 4 |
| Repeat of the same request (cache hit) | 0 | 0 | 0 |
| Optional: mythic lion x eagle variant | +4 | +1 | +1 |
| Optional: default `/evolve` from one seed (4 offspring x 3 rounds) | 39 | 12 | 12 |
| Optional: default `/evolve` from all 4 seeds | 156 | 48 | 48 |

Evolve arithmetic: 1 Spark call per round returns the whole batch (3), and each valid offspring costs polish, critic and thumbnail critic (3 Spark), 1 image and 1 SAM. Offspring that fail schema or hard-card checks cost no image, Spark or SAM call beyond the round's one Spark call.

Caveats on these numbers:
- They assume every call succeeds on its first attempt. The evolution engine has no retry wrapper of its own yet. If live adapters retry inside the adapter, failed attempts add calls, and `usage.guard` counts every attempt.
- The 4 examples fit the existing default live budget (15 images, 60 Spark). Default evolve on all 4 seeds does not (48 images). SAM has no budget counter in `usage.py` yet.
- E1-offline has no live Spark or SAM adapter. In real mode the engine refuses before its first call (tested), so these numbers are for the code path, not something that can run live today.

## Spec ambiguities and what I chose

Routing and labels
1. **Documented hybrids.** Section 4.1 routes only KNOWN_PAIRS and same genus to hybrid, but RC-R2-16 also allows "a documented hybrid". I also route pairs in `chimera_data.json` `hybrids` (wholphin, beefalo and others) to hybrid.
2. **Label for close relatives with no record.** Same-genus pairs with no recorded cross get "plausible hybrid of close relatives, no documented cross". "Real hybrid precedent" is kept for documented pairs. This is a fourth label not listed in 4.10.
3. **Mythic labels.** 4.10 lists three exclusive labels, but section 8 requires every distant pair to carry the speculative label. Mythic plans carry "mythic design" plus "speculative design, no real-world precedent".
4. **Myth on a hybrid pair.** A myth request on a known or same-genus pair is ignored, following the order of the 4.1 pseudocode.
5. **One-direction overrides.** Zebroid and cama are listed with one sire only. I followed them literally. Horse x zebra falls back to the same-genus hybrid without the stripe override, and there is no llama x dromedary override.

Host, genome and operators

6. **Host on the hybrid path.** 4.2 says hybrids have "no single host", but the section 3 example has a hybrid with `host: lion`. I use the override's frame donor when it names one (mule: horse, hinny: horse, liger: lion, zebroid: the non-zebra parent). Otherwise the host is null.
7. **Host tie-break.** Lion and eagle are both "structured" (RC-R6-09). The tie goes to the larger animal, then to the sire. RC-R6-08 ranks "human-like" first; I did not treat a bipedal bird as human-like.
8. **Fields added to the genome:**
   - `limb_plan` (forelimbs, hindlimbs, extra_wings, appendages, wing_use), since the spec tests a limb plan but section 3 has no field for it
   - `known_pair`, `checks` and `seed`
   - `part`, `note` and `flags` on traits
9. **GATE and PACKAGE.** GATE is a step after operator assignment, not a trait operator: for example, the mane is removed when the neck is not furred. PACKAGE is applied in two places: the default head-group assignment, and a soft penalty (RC-R1-11). Trait operators are BLEND, PICK, OVERLAY and PATCH.
10. **Chimera mass.** Example 3 says "blended mass" but the 4.3 table says chimeras use host values. I used the host's mass (lion, 199 kg). It is above 40 kg either way.
11. **Head swaps.** Head swaps only happen in mythic mode with a vertebrate donor (griffin-like). A chimera head swap made by evolution gets a soft RC-R7-02 penalty.

Order of steps
12. **Where Spark writes the first plan.** The code builds the skeleton (4.1 to 4.3). Spark's plan goes through the schema and hard-card filters, with a fallback to the code skeleton if it fails. Then come habitat (4.4) and physics (4.5).
13. **Hard checks before physics.** A wing donor is legitimately unresolved until the limb-budget check runs, so the pre-physics hard check does not flag it. A post-physics assertion does.
14. **Physics versus the mule (RC-R2-03).** Posture rules RC-R3-06 and RC-R3-07 would change the mule's limbs (horse mass 563 kg is more than twice the donkey's 250 kg). The hard card wins: physics leaves locked override fields alone and records that.
15. **Habitat re-runs.** The habitat step is idempotent: its deltas are flagged and undone before re-applying, so evolution does not compound them. The cold-climate mass nudge is skipped for the locked mule. The visible habitat trait is chosen by priority: eyes, then extremities, then pattern, then countershading.

Judge and evolve

16. **Silhouette check.** I used a simple shape comparison rather than a critic call: mask aspect against a range for the host frame, plus a component count. This saves a Spark call per render.
17. **Soft-penalty normalization.** The spec does not define it. I used the sum of weight x severity divided by 3, capped at 1.
18. **Archive axes.** I chose habitat for "mode or habitat", because routing fixes the mode for a pair.
19. **Batching.** One Spark call per round returns all offspring.
20. **Prompt polish.** One Spark call per render. The polished text is kept only if it still starts with the silhouette sentence, has no franchise name, and is at most 1.5x longer.
21. **Edits.** An edit makes a child creature: `parent_ids` is the original and the generation is unchanged, because an edit is not breeding. Editable genes: `traits.<tag>`, `habitat`, `host` and `size.mass_kg`.

Open thresholds (section 9)

22. The arthropod size threshold is 20 kg. It is a placeholder in `data/evo_config.json`.
23. The franchise blocklist is a starter list (`data/evo_config.json`). It has not been checked against R7 in full.

Data and infrastructure
24. **Name aliases.** The data has no `eagle`, `octopus` or `grizzly` ids. Aliases map them to `golden_eagle`, `common_octopus` and `brown_bear` (Ursus arctos).
25. **Data issues.** In `chimera_data.json`, the guanaco is recorded as *Lama glama*, the same species as the llama. That is likely an error, and I did not change it. The octopus has no mass.
26. **Storage.** The shared DbAdapter only accepts six fixed collections, so evolution stores creatures as JSON under `local_data_dir/evo/`. Images go through the existing StorageAdapter. There is no Supabase table for evo yet.
27. **Image input.** `/evo/fuse` takes images as base64 in the JSON body, rather than reusing `/assets` ids.

## Lancaster source retry (end of Step 4)

One attempt with `check_url` from the verifier, 2026-10-31T15:15:00Z: `https://eprints.lancs.ac.uk/id/eprint/50885/` returned **HTTP 200**. The source of RC-R6-03 and RC-R6-05 resolves. It timed out in runs 2 and 3 only, so it looks intermittent. It is already in the "Resolved links" history of `VERIFY_REPORT.md`.

## Not done (needs live work)

- Live EvoSpark and SAM adapters, with retries and a SAM budget counter.
- Person-checked quality tests of the 4 examples (section 8).
- The cost test that sets batch size and round count (4.9).
- Opening the 14 bot-blocked (403) source links in a browser.
