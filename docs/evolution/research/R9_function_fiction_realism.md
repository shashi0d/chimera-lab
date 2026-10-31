# R9. Function, fiction and realism: can it live, what may be bent, and what makes it look real

Doc: docs/evolution/research/R9_function_fiction_realism.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (new function audit after the physical checks; fiction licenses per mode; render realism rules)
Related: R2 (hybrids), R3 (body-plan limits), R4 (environment to form), R5 (real chimeras), R6 (perception), R7 (fiction and design)

## Why this doc exists

R3 asks whether a body can be built. This doc asks three further questions:

1. Can the planned creature perform its basic functions (breathe, eat, move, carry its weight, keep its temperature, sense)?
2. Which rules may a fictional creature bend, which may it never bend, and what has to be shown when it bends one?
3. What makes a fictional creature look real rather than glued together?

It also settles the vocabulary: hybrid, chimera and mythic composite are three different things, and the engine must never mix the labels.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Three kinds of mixed animal, three labels. A hybrid has both parents' DNA in every cell. A biological chimera is one body built from cells of two different embryos. A mythic composite (griffin, manga flying lion) is a part swap from story and art, not biology.
2. Add a function audit after the physical checks: breathing, feeding, support, movement, heat, senses. Each function ends as pass, repaired, or labeled. Reproduction is not on the list: a mule is a real animal and is generally sterile, and fertility cannot be seen in an image.
3. Breathing is the clearest test. Fish gills collapse in air, so gills alone cannot serve a land creature.
4. Feeding is a soft test. Mammal teeth track diet reasonably well; bird beaks track diet weakly. Never reject a plan over beak shape alone.
5. Size is the master variable. Making a body bigger without changing its shape breaks its legs and starves its breathing. A fiction that changes size must show the compensation (thicker legs, bigger chest or breathing openings).
6. Fiction gets a budget, not a free pass. Following H. G. Wells, a believable fantastic creature bends one rule and obeys every other rule strictly. Each bend is a declared license on the card.
7. Some things are never bent in any mode: honest labels, provenance, and the believability floor (parts attach to a structure that can carry them, weight rests on the ground, senses are visible, it reads as one creature).
8. Real creatures look real because their anatomy is built from the inside out and every part does a job. Purposeless extras make a design look fake.

## 1. Hybrid, chimera, mythic composite

Hybrid (R2): the offspring of two species, where every cell carries DNA from both parents and traits land in between. Only close relatives can produce one. Examples: mule, liger.

Biological chimera (R5): the Jackson Laboratory's mouse genetics glossary defines a chimera as an animal formed from two different embryonic sources [S11]. Each region of the body is entirely one species' tissue, so nothing is "in between" at the cell level. Every documented interspecies chimera is between fairly close relatives (R5).

Mythic composite: a genetics glossary from California State University, San Bernardino notes that the word itself comes from the Greek monster with a lion's head, a goat's body and a serpent's tail [S12]. Griffins and manga flying beasts belong here. They are part swaps from story and art. R7 already places them in an explicit mythic mode.

Engine mapping:
- Lion x eagle can never be a hybrid and has no precedent as a biological chimera, so every version of it is labeled speculative or mythic.
- The card states which of the three the creature is, in plain words, every time.

## 2. The function audit

The audit runs after the physical checks (ALGORITHM.md 4.5) and before the render, so it costs no images. Each function returns pass, repaired, or labeled. A failed function never passes silently, matching RC-R3-12.

### 2.1 Breathing

Fish gills fail in air. A University of Illinois study on gill mechanics states that gills exposed to air typically collapse and stick together through surface tension, reducing gas exchange and potentially causing death [S1]. Some amphibious fish survive on land, which is why that study models animals leaving water [S1]. The general rule holds: gills need water.

Engine mapping:
- A land or flying creature that takes gill parts must also have an air-breathing system, or live in water or a very wet habitat. Otherwise the plan is repaired (gills become vestigial slits, lungs assumed) or labeled.
- An aquatic creature built on a land host keeps lungs and is shown as a surface breather.

### 2.2 Feeding

Mammal teeth carry real diet information. A Duke University study of mustelid carnassial teeth found that dental form reflects each species' diet, and concluded that molar form across mammals is largely driven by diet [S4]. Florida State University work on rodent teeth lays out the expected pattern: plant eaters have large, robust, high-crowned grinding molars; meat eaters have sharp, bladed cheek teeth with shearing crests [S13]. The link is not exact. A carnivore dental dataset from Oregon, Clemson and San Francisco universities reports substantial error when inferring diet from tooth shape [S5].

Bird beaks carry much less. A Bristol-led study of 176 bird species, published in Evolution, found diet explains under 12 percent of beak shape variation, and similar beaks go with very different diets [S3].

Engine mapping:
- Diet follows the head donor's mouthparts, because the head does the eating.
- For a mammal head, check that teeth and diet agree (grinding molars with plants, bladed cheek teeth with meat). A mismatch is repaired or flagged, as a soft rule.
- For a beak, do not reject or repair on beak shape versus diet. Only flag something extreme, such as a nectar-feeder beak on a large predator.

### 2.3 Support and size

J. B. S. Haldane's 1926 essay "On Being the Right Size" is the classic statement of the square-cube problem. Scaling an animal up while keeping its shape multiplies its weight far faster than the strength of its bones; a large animal must either make its legs short and thick like a rhinoceros or splay them like a giraffe [S2]. The same essay explains that breathing and gut surfaces must grow faster than the body, so large animals fold those surfaces into lungs and coiled guts, and that insects stay small because air soaks into them through tubes rather than being pumped [S2]. Haldane adds that if insects pumped air, they could reach lobster size, though not human size [S2].

Engine mapping:
- Support: any creature scaled well above its leg donor gets thicker, straighter or splayed legs. R3's posture cards (RC-R3-06 to RC-R3-08) already enforce this; the audit reports it as a function.
- Breathing at size: a large creature built from small-animal parts shows the compensation (a deep chest, large nostrils or visible breathing openings).

### 2.4 Movement, heat and senses

These already have cards and only need reporting in the audit:
- Movement and flight: R3 (forelimb wings, flight chest, flight size ceiling, jointless tentacles, tentacle legs speculative).
- Heat: R4 (Allen's and Bergmann's rules, at least one visible habitat trait).
- Senses: R6 (eyes and head visible, read first).

## 3. What may be fictionalized

### 3.1 The fiction budget

H. G. Wells set out the working rule of believable fantastic fiction. The Encyclopedia of Science Fiction summarizes "Wells's Law" as the principle that a story should contain only one extraordinary assumption, developed afterwards with strict logic [S6]. Wells himself warned that any extra fantasy beyond the central assumption makes the invention look silly, and that touches of ordinary, prosaic detail are essential to make the impossible believable [S6].

Engine mapping: every rule the creature bends is a declared license, shown on the card with what was bent and what compensates for it.

| Mode | Licenses allowed | Meaning |
|---|---|---|
| Realistic | 0 | Every failed check is repaired. If it cannot be repaired, the result is labeled speculative. |
| Speculative | 1 | One rule bent on purpose, as Wells advises; everything else strict. |
| Mythic | Several | Myth and manga part swaps. Each license declared. Believability drops with each extra license, which the label states. |

### 3.2 What can be bent, with a license

| Rule bent | Source of the rule | What must be shown when bent |
|---|---|---|
| Arthropod parts at large size | R3 (RC-R3-09), Haldane [S2] | Thick supporting legs and visible breathing openings or a deep chest |
| Six limbs (four legs plus wings) | R3 (RC-R3-02), R7 | Wings attached with a shoulder structure that can carry them, not floating |
| Flight above about 40 kg | R3 (RC-R3-05) | Huge chest and wing muscles; otherwise show it gliding or grounded |
| Gills on a land creature | Section 2.1 [S1] | A wet habitat, or a second, air-breathing system |
| Tentacles carrying a heavy land body | R3 (RC-R3-11) | Many thick tentacles, short and low to the ground |

Giant insects are a useful middle case. Real ones existed: the griffinfly Meganeura, from about 300 million years ago, had a wingspan near 68 cm [S7]. So insect-part creatures up to that scale need no license. The reason they grew so large is still debated. A long-standing hypothesis credits high oxygen levels, but a 2025 Nature study argued that oxygen supply was probably not the limiting factor [S7], [S8]. The engine must not state oxygen as the settled explanation.

### 3.3 What is never bent, in any mode

Honesty rules (already enforced by RC-R1-14, RC-R2-16 and RC-R5-10, plus the project's provenance principle; no new card):
- Labels: a speculative or mythic creature is never presented as a real or predicted animal.
- Provenance: every fact shows where it came from, and model-estimated facts are marked.

The believability floor (R6, R7 and this doc):
- Parts attach to a structure that could carry them.
- Weight rests on the ground through the limbs.
- Eyes and head are visible.
- It reads as one creature, not two.
- Texture and pattern follow the body outline.

### 3.4 What is free

Color, pattern strength, art style and pose are style choices, not science. They need no license, as long as they do not import a third animal (E2b fix).

## 4. What makes a creature look real

Creature designers who build convincing fictional animals work from real anatomy. The publisher's description of Terryl Whitlatch's "Science of Creature Design" calls anatomy the secret behind believable creature design, whether the creature is real or imaginary [S10]. Whitlatch designed creatures for Star Wars [S10].

In a 2025 Creative Bloq feature, five professional creature artists described what makes imaginary creatures feel believable [S9]:
- Understand structure, weight and movement, and push those ideas while keeping the creature believable.
- A body must carry the anatomy its abilities need: a flyer gets strong wing muscles and a lighter frame; a burrower gets thicker forelimbs and stronger shoulders.
- Adding parts only to look cool, such as extra limbs or spikes, overwhelms a design when they serve no purpose.

Engine mapping, turned into render and plan rules:
- Build from the inside out: the host skeleton is the frame; donor parts attach where that skeleton can carry them.
- Every donor part names its job (fly, swim, grip, display, defend). A part with no job is dropped in realistic mode.
- Ability and anatomy must agree (flight implies a flight chest; digging implies heavy forelimbs).
- Prosaic detail: natural lighting, ground contact and shadow, ordinary wear on hooves and claws. Wells's "prosaic detail" principle [S6] is the source; the specific cues listed are project choices, not tested.

## What this doc does not settle

- No study tests which visual cues make people rate a fictional animal as realistic. Section 4 rests on designer practice and Wells, not on perception experiments. R6 covers what perception research exists.
- Whether a six-limbed vertebrate is impossible or just never evolved (R3 leaves this open). For the engine both mean a license.
- Fertility is not used. That mules are generally sterile is widely known but not yet sourced in R2.
- The fiction budget for mythic mode ("several") is a product decision, not a sourced number.

## Sources

Labels: PR = peer-reviewed, UNI = university-hosted, IND = industry, NEWS = science news, REF = reference work.

- [S1] Dynamic elastocapillary coalescence of fish gill lamellae. Peer-reviewed article, University of Illinois Urbana-Champaign research portal. PR, UNI. https://experts.illinois.edu/en/publications/dynamic-elastocapillary-coalescence-of-fish-gill-lamellae/
- [S2] Haldane J. B. S. (1926). On Being the Right Size. Harper's Magazine. Text hosted by the University of Texas at Austin. UNI. https://www.cs.utexas.edu/~witchel/S25-380L/papers/right-size.html
- [S3] Navalón G, Bright J A, Marugán-Lobón J, Rayfield E J (2019). The evolutionary relationship among beak shape, mechanical advantage, and feeding ecology in modern birds. Evolution 73(3): 422-435. University of Hull repository. PR, UNI. https://hull-repository.worktribe.com/output/3270317
- [S4] Selig K R (2023). Form, function, and tissue proportions of the mustelid carnassial molar. Mammal Research 68(4): 637-646. Duke University faculty database. PR, UNI. https://fds.duke.edu/db/aas/BAA/faculty%20all/krs75/publications/371619
- [S5] Price S, Hopkins S, Chiono A (2021). Dental measurement and diet data for mammals. Dryad dataset, Zenodo record. PR (data), UNI. https://zenodo.org/record/5532916
- [S6] The Encyclopedia of Science Fiction. Wells's Law. REF. https://www.sf-encyclopedia.com/entry/wellss_law
- [S7] Futura Sciences (2025). When dragons, and dragonflies, ruled the skies. NEWS. https://www.futura-sciences.com/en/?p=29524
- [S8] Nautilus. What happened to the ancient bug giants of 300 million years ago? Reporting a Nature study led from the University of Pretoria. NEWS. https://nautil.us/what-happened-to-the-ancient-bug-giants-of-300-million-years-ago-1279562
- [S9] Creative Bloq. Pro artists reveal how they design imaginary creatures that feel believable. IND. https://www.creativebloq.com/art/digital-art/pro-artists-reveal-how-they-design-imaginary-creatures-that-feel-believable
- [S10] Whitlatch T. Science of Creature Design: Understanding Animal Anatomy. Publisher description. IND. https://www.stillnorthbooks.com/book/9781933492568
- [S11] Mouse Genome Informatics, The Jackson Laboratory. Glossary: chimera. REF, UNI (research institute). https://informatics.jax.org/glossary/chimera
- [S12] California State University, San Bernardino genetics glossary: chimera. UNI. https://genetics.academic.csusb.edu/glossary:chimera
- [S13] Martin et al. (2016). Murine dental morphology and diet. Biological Journal of the Linnean Society. Florida State University. PR, UNI. https://www.bio.fsu.edu/%7esteppanlab/assets/files/Martin%20et%20al%20murine%20teeth%20BJLS%202016.pdf

## Rule cards

### RC-R9-01
rule: Use three distinct labels and never mix them: hybrid (both parents' DNA in every cell, real-hybrid route only), chimera (one body from two separate tissue sources), mythic composite (myth-style part swap)
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://informatics.jax.org/glossary/chimera

### RC-R9-02
rule: Run a function audit after the physical checks and before rendering, covering breathing, feeding, support, movement, heat and senses; each function ends as pass, repaired or labeled, never silently failed
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.cs.utexas.edu/~witchel/S25-380L/papers/right-size.html

### RC-R9-03
rule: Gills alone cannot serve a land or flying creature, because gills collapse in air; such a creature must also have an air-breathing system or live in water or a very wet habitat, otherwise repair or label it
applies_to: [body, pipeline]
strength: hard
status: VERIFIED
source: https://experts.illinois.edu/en/publications/dynamic-elastocapillary-coalescence-of-fish-gill-lamellae/

### RC-R9-04
rule: Diet follows the head donor's mouthparts; for a mammal head, grinding molars go with plant diets and bladed, shearing cheek teeth go with meat, and a mismatch is repaired or flagged
applies_to: [head, skull, behavior]
strength: soft
status: VERIFIED
source: https://fds.duke.edu/db/aas/BAA/faculty%20all/krs75/publications/371619

### RC-R9-05
rule: Never reject or repair a plan because a bird beak's shape seems not to fit the diet; beak shape explains under 12 percent of diet variation, so only extreme mismatches are flagged
applies_to: [head, behavior]
strength: soft
status: VERIFIED
source: https://hull-repository.worktribe.com/output/3270317

### RC-R9-06
rule: A creature scaled well above its leg donor must change shape to carry its weight, with short thick legs or splayed legs; the same shape at much larger size is not allowed
applies_to: [limbs, size]
strength: hard
status: VERIFIED
source: https://www.cs.utexas.edu/~witchel/S25-380L/papers/right-size.html

### RC-R9-07
rule: A large creature built from small-animal parts must show breathing compensation (deep chest, large nostrils or visible breathing openings), because breathing surfaces must grow faster than body size
applies_to: [body, size]
strength: soft
status: VERIFIED
source: https://www.cs.utexas.edu/~witchel/S25-380L/papers/right-size.html

### RC-R9-08
rule: Insect-part creatures up to about 70 cm wingspan have a real precedent (Meganeura, about 68 cm) and need no size license; larger ones need a declared license with visible compensation
applies_to: [size, body]
strength: soft
status: VERIFIED
source: https://www.futura-sciences.com/en/?p=29524

### RC-R9-09
rule: Never state high atmospheric oxygen as the settled reason giant insects existed; a 2025 Nature study argued oxygen was probably not the limiting factor
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://nautil.us/what-happened-to-the-ancient-bug-giants-of-300-million-years-ago-1279562

### RC-R9-10
rule: Fiction budget: a realistic design takes no licenses; a speculative design bends at most one rule on purpose and obeys every other rule strictly; every bent rule is declared on the card with its compensation
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.sf-encyclopedia.com/entry/wellss_law

### RC-R9-11
rule: Mythic designs may take several licenses, but each one is declared, and the label states that believability drops with each extra license
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://www.sf-encyclopedia.com/entry/wellss_law

### RC-R9-12
rule: Every donor part must have a job (fly, swim, grip, dig, display, defend); a part with no job is dropped in realistic mode, because purposeless extras such as extra limbs or spikes make a design look fake
applies_to: [all_traits]
strength: soft
status: VERIFIED
source: https://www.creativebloq.com/art/digital-art/pro-artists-reveal-how-they-design-imaginary-creatures-that-feel-believable

### RC-R9-13
rule: Anatomy must match ability: a flyer shows strong wing muscles and a lighter frame, a digger shows thick forelimbs and strong shoulders
applies_to: [body, limbs]
strength: soft
status: VERIFIED
source: https://www.creativebloq.com/art/digital-art/pro-artists-reveal-how-they-design-imaginary-creatures-that-feel-believable

### RC-R9-14
rule: Build believability from the inside out: donor parts attach where the host skeleton could carry them, with muscle and surface following the skeleton
applies_to: [body, limbs]
strength: soft
status: VERIFIED
source: https://www.stillnorthbooks.com/book/9781933492568

### RC-R9-15
rule: Render ordinary, prosaic detail consistently (natural lighting, ground contact and shadow, normal wear on feet and claws) so the one impossible element is believable
applies_to: [all_traits]
strength: soft
status: UNVERIFIED
source: https://www.sf-encyclopedia.com/entry/wellss_law
