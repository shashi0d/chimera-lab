# Research summary: Chimera Lab evolution engine

Doc: docs/evolution/research/RESEARCH_SUMMARY.md
Status: first pass complete (Oct 31, 2026)
Inputs: R1 to R8 in this folder
Feeds: docs/evolution/ALGORITHM.md

## What the research says in one paragraph

A fused creature should be decided trait by trait, not by picking a dominant parent. For pairs that can really interbreed (close relatives), the engine follows real hybrids: most traits land between the parents, a few regions come wholly from one parent, signature patterns arrive diluted, and parent order matters. For every other pair, the engine follows real lab chimeras: one parent (the host) owns the silhouette and size, and the other arrives as whole regions or large patches of its own tissue. Physical checks then stop impossible bodies from being called plausible, habitat makes the ecology visible, and perception research says the silhouette owner is what people will call the creature. Each creature is evolved as a text genome with a language model as the breeding operator, kept in a diverse archive rather than a single winner, and labeled honestly as a real hybrid, a speculative chimera or a myth.

## Docs at a glance

| Doc | Question it answers | Cards | Hard | Unverified | Sources |
|---|---|---|---|---|---|
| R1 inheritance | Which operator does each trait use? | 14 | 2 | 2 | 13 |
| R2 real hybrids | What do real crosses look like? | 16 | 4 | 4 | 16 |
| R3 body-plan limits | Can this body physically work? | 12 | 3 | 2 | 13 |
| R4 environment to form | How does habitat show in the body? | 11 | 0 | 2 | 12 |
| R5 real chimeras | What do two cell lines in one body look like? | 10 | 2 | 1 | 7 |
| R6 perception | What will people actually see? | 11 | 0 | 3 | 7 |
| R7 fiction and design | What do designers and myth teach? | 10 | 0 | 1 | 9 |
| R8 generative evolution | How do we run the loop with models? | 10 | 0 | 4 | 7 |
| Total | | 94 | 11 | 19 | 84 |

## Ten findings that change the engine

1. No dominant parent. Dominance is a relation between two versions of one gene, so the engine decides per trait (R1, RC-R1-01, hard).
2. Two paths, chosen by relatedness. Real hybridization is mostly between recent, close relatives, so only documented or same-genus pairs take the hybrid path; everything else takes the chimera path and is labeled speculative (R1, R2, R5; RC-R1-14, RC-R2-16, RC-R5-10, all hard).
3. In between is the default on the hybrid path. Measurements blend near the midpoint with modest spread; only a minority of traits go beyond both parents and those get flagged (R1, R2).
4. Region mosaics are real, but coherent. The mule takes its frame from the horse and head, ears, limbs and hooves from the donkey; donors cover sensible groups of regions, not scattered parts (R2, RC-R2-03 hard, RC-R2-06).
5. Patterns arrive diluted when the pattern donor does not own the body (zebroids, ligers). Our full-mane, full-stripe liger was the opposite of the documented look (R2).
6. Parent order is biological. Liger versus tigon and deer mouse crosses show reciprocal crosses can differ (R2, RC-R2-01 hard).
7. Chimeras are patches, not blends, with the host setting frame and size. Donor color appears at full strength inside few, large, region-aligned patches, and the host body can decide where the pattern shows (R5, RC-R5-01 hard).
8. Bodies have limits. Wings take the forelimb slot in vertebrates, six limbs need a mythic or speculative label, flight needs a matching chest and tops out around 40 kg, big bodies need straighter, thicker legs, and insect parts cannot be mammal-sized (R3; RC-R3-01, 02, 09 hard).
9. Silhouette names the animal. People call a cat shape with elephant skin a cat, they look at heads and eyes first, and classifiers lean on texture instead, so the critic needs a silhouette check (R6, R7).
10. Evolve a genome, keep a diverse archive. A text trait plan is varied by a language model, validated by code, rendered, judged, and stored in a quality-diversity grid, with short user rounds and branching from saved creatures (R8).

## How the docs fit together

- R1 supplies the operators (PICK, BLEND, OVERLAY, GATE, PATCH, PACKAGE).
- R2 supplies real outcomes and known-pair overrides for the hybrid path.
- R5 supplies the chimera path (host frame, donor patches).
- R4 adjusts plastic traits for the chosen habitat.
- R3 checks the result physically and adds labels.
- R6 and R7 shape the render prompt and the critic.
- R8 runs everything as an evolution loop.

## Conflicts and how they were resolved

- R1 PACKAGE versus R2 mule. R1 prefers face, ears and pigment from one parent; the mule mixes a donkey head and ears with a horse body. Resolution: PACKAGE is soft, and documented known-pair overrides (R2) win.
- R4 habitat pattern versus R1 and R2 inheritance. Habitat may change pattern strength and complexity, but R1 and R2 still decide which parent's pattern is present. Habitat adjusts, it does not swap donors.
- R6 shape versus R5 donor patches. The host keeps the silhouette; donor patches carry identity through surface and signature parts, so both parents read without stacking two animals.
- R7 myth versus R3 limits. Griffin-style designs stay available, but only in an explicit mythic mode with the six-limb label.

## Where the evidence is weakest

These cards are UNVERIFIED and should be soft penalties at half weight until better sources or live tests confirm them:
- Specific looks of some hybrids: liger mane and stripes, zebroid leg stripes, camel x llama details, polar bear x grizzly features, geep coat (encyclopedia, news or secondary summaries only).
- Design inferences of ours: log-scale size blend, gate examples, tentacles as weight-bearing legs, check order, habitat limits, the thumbnail test, the cold critic test, our animal-to-schema mapping, archive axes, code validation before render, constrained search space, hard-as-filter and soft-as-penalty, resemblance display.

## Open questions for live tests

1. Does Muse Spark produce valid offspring genomes in our schema, reliably enough to skip repairs?
2. Do Meta's vision models show the texture bias described for older classifiers? (affects how much the critic can be trusted)
3. Can SAM 3.1 masks support a usable silhouette check against the planned host?
4. What batch size and round count fit the Meta API budget?
5. Which archive axes do users actually find useful?

## Card index

All 94 cards. Hard cards are filters; soft cards are penalties. Full wording and sources live in each R doc.

| Card | Strength | Status | Applies to | Rule (short) |
|---|---|---|---|---|
| RC-R1-01 | hard | VERIFIED | pipeline, all_traits | Decide inheritance per trait, never per animal; the engine must not assign one parent as dominant for the whole ... |
| RC-R1-02 | soft | VERIFIED | size, limbs, tail, ears, face, body | Measurement traits (size, limb, neck, tail, ear and snout length) use BLEND: start near the midpoint of the parents ... |
| RC-R1-03 | soft | UNVERIFIED | size | Blend body size on a log scale (geometric mean of parent masses) rather than a plain average |
| RC-R1-04 | soft | VERIFIED | head, mane, tail | Clearly present-or-absent features (horns, crest, tail tuft, mane presence) use PICK: the feature comes fully from ... |
| RC-R1-05 | soft | VERIFIED | coat_color | Shade-like traits (base coat color, contrast) may use BLEND, matching incomplete dominance where the in-between form ... |
| RC-R1-06 | soft | VERIFIED | coat_pattern, coat_color | Patterns may use OVERLAY, where both parents' features are visible at once (a pattern over a base color), matching ... |
| RC-R1-07 | soft | VERIFIED | pipeline, coat_pattern, coat_color | Some traits can be inherited yet hidden because another trait controls whether they show (GATE); evaluate gating ... |
| RC-R1-08 | soft | UNVERIFIED | coat_pattern, mane, coat_texture | Gate examples for fusions: a fur pattern only shows on regions that carry fur; a mane only shows where the body ... |
| RC-R1-09 | soft | VERIFIED | coat_pattern, coat_color | PATCH is a valid coat mode: distinct blocks with clear edges, each block fully one version, no blending inside a ... |
| RC-R1-10 | soft | VERIFIED | coat_pattern | Each mosaic patch grows from a single cell lineage, so patches should be few and large rather than fine speckles |
| RC-R1-11 | soft | VERIFIED | face, ears, coat_pattern, skull | Face shape, ear form and pigment pattern share a developmental origin (neural crest); prefer taking them from the ... |
| RC-R1-12 | soft | VERIFIED | pipeline | Do not present the domestication syndrome explanation as settled science in any user-facing text; it is a debated ... |
| RC-R1-13 | soft | VERIFIED | all_traits | Allow a small share of traits to land beyond both parents; extremes are common in hybrids overall but rarer in ... |
| RC-R1-14 | hard | VERIFIED | pipeline | Genetics-based operators only predict real outcomes for parents that can interbreed; for any other pair the fusion ... |
| RC-R2-01 | hard | VERIFIED | pipeline, size | Parent order is biological. Store fusions as (sire, dam) and never treat A x B as identical to B x A, because ... |
| RC-R2-02 | soft | VERIFIED | size, limbs, skull, body | For a first-generation fusion, place most measurable traits (size, limb length, skull proportions) between the two ... |
| RC-R2-03 | hard | VERIFIED | body, head, ears, mane, limbs, feet, tail, coat_texture | Donkey sire x horse dam must render as the documented mule: horse height, neck shape and body; donkey short thick head, long ... |
| RC-R2-04 | soft | VERIFIED | ears, mane, tail, size | Horse sire x donkey dam (hinny) renders close to the mule but somewhat smaller and more horse-like, with shorter horse-shaped ... |
| RC-R2-05 | soft | VERIFIED | size | Size may exceed both parents only when a documented direction-specific case exists (lion sire x tiger dam); the ... |
| RC-R2-06 | soft | VERIFIED | body, head, ears, limbs | Region mosaics are allowed and realistic: one parent can supply the frame while the other supplies head, ears and ... |
| RC-R2-07 | soft | VERIFIED | coat_pattern, coat_color | When the pattern donor is not the body donor, render its pattern partial and reduced (zebroid: base body and color ... |
| RC-R2-08 | soft | UNVERIFIED | coat_pattern, coat_color, mane | Lion x tiger renders as a tawny lion-like coat with faint tiger stripes; a male may have a reduced mane or none; ... |
| RC-R2-09 | soft | UNVERIFIED | coat_pattern, limbs | Zebroid stripes are strongest on the legs and do not appear on white patches of a patterned horse parent |
| RC-R2-10 | soft | UNVERIFIED | body, tail, feet, coat_color, behavior | Polar bear x grizzly renders with a long polar-like neck and visible tail, a small grizzly-like shoulder hump, ... |
| RC-R2-11 | hard | VERIFIED | pipeline | Wild polar bear x grizzly hybrids are genetically confirmed, so the pair qualifies for the real-hybrid path |
| RC-R2-12 | soft | VERIFIED | skull, size | Inherited traits can fit a new lifestyle: when a fusion takes the larger parent's size, it may also take a larger, ... |
| RC-R2-13 | soft | VERIFIED | body, all_traits | Even distantly related compatible parents (camel x guanaco) give an intermediate-looking animal, not a part swap; a ... |
| RC-R2-14 | soft | UNVERIFIED | ears, tail, feet, body | Camel x llama renders with short camel-like ears, a long camel-like tail, split llama-like hooves and no hump |
| RC-R2-15 | soft | VERIFIED | behavior | Behavior can follow one parent even when the body is mixed, and a behavior can be present without the physical ... |
| RC-R2-16 | hard | VERIFIED | pipeline | Use the real-hybrid path only for pairs with a documented hybrid or a close relationship (same genus); all other ... |
| RC-R3-01 | hard | VERIFIED | limbs, body | For a vertebrate base with a wing donor, the wings take the place of the forelimbs by default, because pterosaurs, ... |
| RC-R3-02 | hard | VERIFIED | limbs, pipeline | A vertebrate design with four legs plus a separate pair of wings (six limbs) is allowed only when labeled as a ... |
| RC-R3-03 | soft | VERIFIED | body, limbs | A creature described as a powered flyer must show a matching chest: a deep keel or a broad, heavily muscled chest ... |
| RC-R3-04 | soft | VERIFIED | body, behavior | Takeoff ability scales with the share of body mass in flight muscle (about 0.12 to 0.56 in studied flyers); a heavy ... |
| RC-R3-05 | soft | VERIFIED | size, behavior, limbs | Winged fusions above about 40 kg are shown as gliders or flightless, and those between about 26 and 75 kg are ... |
| RC-R3-06 | soft | VERIFIED | limbs, size, behavior | When a fusion is scaled well above its leg donor's size, straighten the limbs toward an upright posture and reduce ... |
| RC-R3-07 | soft | VERIFIED | limbs, size | Above roughly horse size, also thicken limb bones relative to their length, since posture alone stops compensating |
| RC-R3-08 | soft | VERIFIED | limbs, size | Cat-derived legs may keep a crouched stance at larger sizes, shown with heavier support muscles, since felids keep a ... |
| RC-R3-09 | hard | VERIFIED | size, body, limbs, pipeline | Arthropod parts (exoskeleton, jointed insect legs, insect wings) must not appear at large mammal size in a plausible ... |
| RC-R3-10 | soft | VERIFIED | limbs, tail, face | Tentacle and trunk parts are rendered jointless and smoothly curving (no elbows, knees or hooves), and a longer ... |
| RC-R3-11 | soft | UNVERIFIED | limbs, pipeline | Tentacles used as weight-bearing legs on a heavy land animal are treated as speculative |
| RC-R3-12 | soft | UNVERIFIED | pipeline | Physical checks run after trait selection in a fixed order (body-plan class, limb budget, size ceiling, posture, ... |
| RC-R4-01 | soft | VERIFIED | coat_pattern | Fit coat pattern to the fusion's habitat: closed, forested or tree-climbing lifestyles lean patterned and irregular; ... |
| RC-R4-02 | soft | VERIFIED | coat_pattern, pipeline | Habitat may adjust pattern strength and complexity beyond what either parent shows, because coat pattern tracks ... |
| RC-R4-03 | soft | VERIFIED | size | In a cold habitat, nudge body size toward the upper end of the blended range (Bergmann's rule), staying within R3 ... |
| RC-R4-04 | soft | VERIFIED | ears, tail, limbs, face | In a hot habitat, enlarge heat-shedding extremities (ears, tail, beak, limbs); in a cold habitat, shorten them ... |
| RC-R4-05 | soft | VERIFIED | coat_color | Default to a dark-back, light-belly gradient, stronger in open, sunny habitats and smaller bodies; describe it as a ... |
| RC-R4-06 | soft | VERIFIED | body, tail, behavior | A fusion assigned a fast open-water lifestyle gets a streamlined torpedo body and a crescent or fluked tail; ... |
| RC-R4-07 | soft | VERIFIED | face, head, behavior | A nocturnal or dusk-active fusion with a bird or reptile head gets visibly larger eyes and pupils; with a mammal ... |
| RC-R4-08 | soft | VERIFIED | skull, head | Larger prey goes with a larger, wider skull and stronger jaws |
| RC-R4-09 | soft | VERIFIED | pipeline, behavior | A fusion may live in a habitat neither parent uses (a bridging niche), because niche separation is what lets hybrid ... |
| RC-R4-10 | soft | UNVERIFIED | pipeline, body, limbs | Habitat adjusts plastic traits (pattern, shading, extremity size, eye size) but never the body-plan class or limb ... |
| RC-R4-11 | soft | UNVERIFIED | pipeline | At least one habitat-linked trait must be visible in the image, so the ecology appears in the creature and not only ... |
| RC-R5-01 | hard | VERIFIED | coat_pattern, coat_texture, coat_color, all_traits | On the chimera path, each region is fully one parent's tissue; blend between regions only at the edges, never within ... |
| RC-R5-02 | soft | VERIFIED | body, size, pipeline | The host parent sets silhouette, body size and overall frame; the donor contributes regions, organs or patches |
| RC-R5-03 | soft | VERIFIED | all_traits, pipeline | Chimeras are not 50:50; allow the donor share to vary between runs, and never present a fixed even split as the ... |
| RC-R5-04 | soft | VERIFIED | coat_color, coat_texture | Donor regions keep the donor's own color and surface (feathers, hair, skin), shown at full strength inside the region |
| RC-R5-05 | soft | VERIFIED | coat_pattern | Where donor pattern appears follows the host's body layout (its skin and feather regions), not the donor's own ... |
| RC-R5-06 | soft | VERIFIED | coat_pattern, body | Donor regions align with body segments or regions (the level of a graft), not random scattered fragments |
| RC-R5-07 | soft | VERIFIED | behavior, head | Behavior can follow the parent that supplied the brain or head tissue |
| RC-R5-08 | soft | UNVERIFIED | coat_texture, body | A sheep and goat style chimera shows mixed patches of both coat types (hair and wool), with the overall look leaning ... |
| RC-R5-09 | soft | VERIFIED | pipeline, behavior | Where very different tissues meet, the description may note a seam or incompatibility; never claim a distant-pair ... |
| RC-R5-10 | hard | VERIFIED | pipeline | Documented interspecies chimeras pair close relatives only; any chimera between distant groups must be labeled a ... |
| RC-R6-01 | soft | VERIFIED | body, pipeline | The body silhouette donor sets the creature's identity for human viewers; choose it deliberately (or expose it as a ... |
| RC-R6-02 | soft | VERIFIED | coat_pattern, coat_texture, coat_color, all_traits | Carry the second parent mainly through surface texture, pattern and selected signature parts, which tell viewers ... |
| RC-R6-03 | soft | VERIFIED | head, face | Keep the head fully visible and uncluttered; the head and eyes draw the earliest and most looks, so the head donor ... |
| RC-R6-04 | soft | VERIFIED | face, head | Every creature must have clearly discernible eyes; viewers search for eyes wherever they are, so extra or displaced ... |
| RC-R6-05 | soft | VERIFIED | tail, face, body | Signature parts that draw looks on the real animal (a tail tuft, a trunk, an udder-like feature) are the best ... |
| RC-R6-06 | soft | UNVERIFIED | pipeline | The creature must read as one animal at a glance; test the render at thumbnail size as well as full size |
| RC-R6-07 | soft | VERIFIED | body, face, limbs | Keep bilateral symmetry, visible sense organs and recognizable limbs unless the user explicitly asks for an alien ... |
| RC-R6-08 | soft | VERIFIED | body, pipeline | When building a hybrid, take the overall shape from the parent with the more structured body schema; a schema higher ... |
| RC-R6-09 | soft | UNVERIFIED | body, limbs | Specific mapping for our animals: four-legged mammals and birds count as structured frames; octopus, jellyfish and ... |
| RC-R6-10 | soft | VERIFIED | pipeline | A model critic's animal label is not proof of human readability, because standard image classifiers lean on texture ... |
| RC-R6-11 | soft | UNVERIFIED | pipeline | Readability critic test: show the final image cold and ask which two animals it combines and whether it is one ... |
| RC-R7-01 | soft | VERIFIED | pipeline | Frame every creature as a fictional example of real processes; its card names the processes behind its look (hybrid ... |
| RC-R7-02 | soft | VERIFIED | pipeline, body, limbs | Myth-style part swaps (griffin-like layouts) belong only to an explicit mythic mode, labeled as myth and never ... |
| RC-R7-03 | soft | VERIFIED | pipeline | Never state that a myth creature came from a specific fossil as fact; the Protoceratops and griffin link is contested |
| RC-R7-04 | soft | VERIFIED | body, all_traits | Design pattern from manga chimeras: one consistent base body carries selected traits from the other species, and ... |
| RC-R7-05 | soft | VERIFIED | pipeline | Human and animal fusions are out of scope; parents are animals only |
| RC-R7-06 | soft | VERIFIED | body, pipeline | State the intended silhouette in the plan and validate the render with a silhouette-only check; the creature must ... |
| RC-R7-07 | soft | VERIFIED | coat_pattern, coat_texture | Interior detail (pattern lines, texture flow) should echo the silhouette's shapes rather than cut across them |
| RC-R7-08 | soft | VERIFIED | limbs, pipeline | Six limbs read as believable only as a consistent world rule, as with Pandora's mostly six-limbed fauna; in our ... |
| RC-R7-09 | soft | VERIFIED | pipeline | Write the biology rulebook before designing creatures, and treat design parameters as a shared palette across many ... |
| RC-R7-10 | soft | UNVERIFIED | pipeline | Show myth and fiction resemblances as "resembles X (culture or work)", tagged unverified; never render or name-match ... |
| RC-R8-01 | soft | VERIFIED | pipeline, all_traits | Represent each creature as a structured text genome (trait plan with donor, operator, strength and region per trait, ... |
| RC-R8-02 | soft | VERIFIED | pipeline | Use a language model as the crossover and mutation operator: give it parent genomes and the rule cards, and parse ... |
| RC-R8-03 | soft | UNVERIFIED | pipeline | Validate every offspring genome by code (schema and hard rule cards) before rendering, so no image budget is spent ... |
| RC-R8-04 | soft | VERIFIED | pipeline | Keep a quality-diversity archive (best creature per cell of a few user-meaningful axes) instead of a single best ... |
| RC-R8-05 | soft | UNVERIFIED | pipeline | Archive axes for Chimera Lab: identity balance between the two parents, crossed with habitat or mode (hybrid, ... |
| RC-R8-06 | soft | VERIFIED | pipeline | A model may score quality and assign diversity cells for subjective outputs, but its judgments need periodic human ... |
| RC-R8-07 | soft | VERIFIED | pipeline | Keep interactive sessions to a few short rounds with small grids, because users tire after evaluating relatively few ... |
| RC-R8-08 | soft | VERIFIED | pipeline | Store parent ids for every saved creature so anyone can branch from it later; branching from others' results helps ... |
| RC-R8-09 | soft | UNVERIFIED | pipeline | Constrain the search space (fixed creature-plan schema, R3 checks passed) before users see candidates, to reduce ... |
| RC-R8-10 | soft | UNVERIFIED | pipeline | Hard rule cards act as filters on candidates; soft rule cards act as score penalties, so rules guide the models ... |
