# R3. Body-plan limits: what a body can and cannot be built to do

Doc: docs/evolution/research/R3_body_plan_limits.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (the physical checks that run after R1 and R2 have picked traits)
Related: R1 (log-scale size blend, gate rules), R5 (chimeras between distant body plans)

## Why this doc exists

R1 and R2 decide which parent each trait comes from. This doc decides whether the result can physically work. It covers limb count and where wings come from, what flight needs, how size changes posture and proportions, and the hard ceilings on some body types. These are the checks that stop a "lion body with eagle wings glued on" from being called plausible.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Every flying vertebrate (pterosaurs, birds, bats) built its wings from the forelimbs. A vertebrate chimera with wings should give up its front legs, or be labeled a mythic six-limbed design.
2. Flight needs a power plant, not just wings: big chest muscles anchored on a keeled breastbone. Wings on a body without that chest read as decoration.
3. Flight has a size ceiling. A scaling study of soaring seabirds puts it around 41 kg. Heavier winged chimeras should be shown as gliders or flightless.
4. Big land animals stand on straighter, thicker legs. When a fusion is scaled up, its posture and bone thickness must change with it.
5. Arthropod-style bodies have a much lower size ceiling, set by how they breathe. Insect parts at mammal size are a red flag.
6. Tentacles have no skeleton. They bend anywhere and never have elbows or knees.

## 1. Limb count and where wings come from

Flapping flight evolved separately three times in vertebrates (pterosaurs, birds and bats), and each group built its wing from the forelimb, using different parts of it [S1], [S2]. Berkeley's Museum of Paleontology presents the three as a classic case of convergent evolution, with each lineage reaching flight from a different starting point [S1].

A Bristol University palaeontology piece makes the design consequence explicit: four legs plus a separate pair of wings would require a six-limbed starting body, which is not seen in vertebrates, so the classic fantasy dragon layout is improbable [S3]. That piece is a university blog rather than a paper, so the "six limbs never occur" phrasing is backed by the stronger point that all three real flying groups used their forelimbs.

Engine mapping:
- Default for a vertebrate base plus a wing donor: the wings replace the forelimbs (griffin-like front becomes bird-wing front, as in bats and birds). The body keeps two walking legs or uses the wings for walking support, as bats do.
- A six-limbed result (four legs plus wings) is allowed only as an explicit mythic or speculative design and must be labeled that way.

## 2. What flight needs: the chest

The avian breastbone carries a keel that anchors the main flight muscles. A 2021 study of sternum shape across birds found that a large sternum with a deep or forward-projecting keel is needed for powered flight in modern birds [S4].

The main downstroke muscle (pectoralis) is roughly 8 to 11 percent of body mass in birds, and its partner that lifts the wing is about a fifth of that [S5]. Across insects, birds and bats, how well an animal takes off depends mainly on its flight muscle ratio, which ranges from about 0.12 to 0.56 of body mass among the species studied [S6].

Engine mapping:
- A creature labeled as a flyer must show the chest to match: a deep keel or broad, heavy chest and shoulders.
- If the body donor has a narrow chest and the wings are grafted on, either rebuild the chest or label the wings as non-flying (display, gliding or vestigial).

## 3. The size ceiling on flight

Using accelerometers on albatrosses and petrels, Sato and colleagues measured how wingbeat frequency changes with body size. Their scaling relationships predicted a maximum size for soaring animals of about 41 kg and a 5.1 m wingspan; above that, the animal could not flap fast enough to stay aloft in poor winds [S7]. The confidence interval was wide (about 26 to 75 kg), and the authors note their result casts doubt on whether the largest pterosaurs could fly, a question that remains debated [S7].

Engine mapping: a winged chimera whose blended mass is above roughly 40 kg should be rendered and described as a glider or flightless. Between about 26 and 75 kg, flag it as borderline. This is a soft rule because the limit is a model estimate, not a hard law.

## 4. Size changes posture and bone shape on land

Bone and muscle strength does not grow as fast as body weight. Biewener's work at Harvard shows how mammals cope: small mammals run crouched, larger ones run with straighter limbs that line up with the ground force, which cuts the muscle force needed per kilogram. This keeps bone stress within safe limits from about 0.1 to 300 kg, at the cost of agility in large animals [S8], [S9]. Above roughly horse size, posture alone is no longer enough, and very large mammals show thicker, more robust bones relative to length [S9].

There are exceptions. A Royal Veterinary College study notes that cats keep the same crouched posture across a roughly 300-fold size range, compensating with relatively stronger support muscles instead [S10].

Engine mapping:
- When a fusion's blended size is much larger than the donor of its legs, straighten the legs and thicken the bones, and reduce suggestions of agility.
- When it is much smaller, a more crouched stance is plausible.
- If the leg donor is a cat, a crouched stance can stay at larger sizes, but limbs should look more heavily muscled.

## 5. The ceiling on insect-type bodies

Insects breathe through a network of air tubes rather than blood carrying oxygen from lungs. A PNAS study using synchrotron X-rays found that larger beetle species devote a disproportionately larger share of their body to these tubes, and that the bottleneck is the opening where legs join the body. Extrapolating from the leg data predicted a maximum beetle size close to the largest living beetle [S11].

Engine mapping: arthropod body parts (exoskeleton, jointed insect legs, insect wings) should not be scaled to large mammal size in a plausible fusion. If a pair forces it (for example a beetle body at tiger size), the result must be labeled speculative and the label should say why.

## 6. Tentacles and trunks: muscle without bones

Octopus arms, squid tentacles, elephant trunks and many tongues are "muscular hydrostats": dense muscle with no rigid skeleton, which keeps a constant volume, so getting thinner makes them longer and vice versa [S12]. A neuroscience study of octopus reaching notes that an octopus arm can bend at any point and in any direction, and can lengthen, shorten and twist [S13].

Engine mapping:
- Tentacle-type parts are rendered jointless and smoothly curving, never with elbows, knees or hooves.
- A tentacle that gets longer should get thinner.
- Whether tentacles can carry a large animal's weight on land is not settled by these sources; treat tentacle legs on a heavy land animal as speculative (UNVERIFIED card).

## 7. Order of checks

These checks run after R1 and R2 have chosen traits:
1. Body-plan class of the base (vertebrate, arthropod, soft-bodied).
2. Limb budget (wings take the forelimb slot for vertebrates).
3. Size check against the base's ceiling (flight, arthropod).
4. Posture and bone thickness from final size.
5. Part-type rendering rules (tentacles jointless).

Any failed check either changes the design or adds a visible "speculative" label. It never silently passes.

## What this doc does not settle

- Exact numeric ceilings for every body type. Only flight and beetles have sourced numbers here.
- Aquatic body limits (buoyancy lets sea animals get much larger). R4 (environment) should cover this.
- Whether a six-limbed vertebrate is impossible or just never evolved. For the engine both mean the same thing: label it.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, ZOO = museum.

- [S1] University of California Museum of Paleontology. Vertebrate flight: the three solutions to flight. UNI, ZOO (museum). https://ucmp.berkeley.edu/vertebrates/flight/converge.html
- [S2] Bell E, Andres B, Goswami A (2011). Integration and dissociation of limb elements in flying vertebrates: a comparison of pterosaurs, birds and bats. Journal of Evolutionary Biology. University of South Florida repository. PR, UNI. https://digitalcommons.usf.edu/geo_facpub/838
- [S3] Green E, Bristol Dinosaur Project blog, University of Bristol. Guest post on the biology of dragons. UNI. https://dinoproject.blogs.bristol.ac.uk/?p=811
- [S4] Lowi-Merri TM and colleagues (2021). The relationship between sternum variation and mode of locomotion in birds. BMC Biology. PubMed Central. PR. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8377870/
- [S5] Biewener AA (2011). Muscle function in avian flight: achieving power and control. Philosophical Transactions of the Royal Society B. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC3130450
- [S6] Marden JH (1987). Maximum lift production during takeoff in flying animals. Journal of Experimental Biology 130: 235 to 258. PR. https://cir.nii.ac.jp/crid/1363388843989515904
- [S7] Sato K and colleagues (2009). Scaling of soaring seabirds and implications for flight abilities of giant pterosaurs. PLoS ONE 4: e5400. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC2670537
- [S8] Biewener AA (1989). Scaling body support in mammals: limb posture and muscle mechanics. Science 245: 45 to 48. Record on Scilit. PR. https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18
- [S9] Biewener AA (2005). Biomechanical consequences of scaling. Journal of Experimental Biology 208: 1665 to 1676. Harvard Biewener Lab listing. PR, UNI. https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling
- [S10] Royal Veterinary College research repository. Study of muscle scaling in felids that keep a crouched posture across body sizes. PR, UNI. https://rvc-repository.worktribe.com/OutputFile/1397435
- [S11] Kaiser A, Klok CJ, Socha JJ, Lee WK, Quinlan MC, Harrison JF (2007). Increase in tracheal investment with beetle size supports hypothesis of oxygen limitation on insect gigantism. PNAS 104: 13198 to 13203. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC1941816
- [S12] Kier WM, Smith KK (1985). Tongues, tentacles and trunks: the biomechanics of movement in muscular-hydrostats. Zoological Journal of the Linnean Society 83: 307 to 324. Duke Scholars listing. PR, UNI. https://scholars.duke.edu/display/pub798983
- [S13] Gutfreund Y, Flash T, Fiorito G, Hochner B (1998). Patterns of arm muscle activation involved in octopus reaching movements. Journal of Neuroscience. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC6793066

## Rule cards

### RC-R3-01
rule: For a vertebrate base with a wing donor, the wings take the place of the forelimbs by default, because pterosaurs, birds and bats all built wings from forelimbs
applies_to: [limbs, body]
strength: hard
status: VERIFIED
source: https://digitalcommons.usf.edu/geo_facpub/838

### RC-R3-02
rule: A vertebrate design with four legs plus a separate pair of wings (six limbs) is allowed only when labeled as a mythic or speculative design, never as a plausible animal
applies_to: [limbs, pipeline]
strength: hard
status: VERIFIED
source: https://digitalcommons.usf.edu/geo_facpub/838

### RC-R3-03
rule: A creature described as a powered flyer must show a matching chest: a deep keel or a broad, heavily muscled chest and shoulders; otherwise its wings are labeled non-flying (display, gliding or vestigial)
applies_to: [body, limbs]
strength: soft
status: VERIFIED
source: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8377870/

### RC-R3-04
rule: Takeoff ability scales with the share of body mass in flight muscle (about 0.12 to 0.56 in studied flyers); a heavy body with small wing muscles should not be shown taking off
applies_to: [body, behavior]
strength: soft
status: VERIFIED
source: https://cir.nii.ac.jp/crid/1363388843989515904

### RC-R3-05
rule: Winged fusions above about 40 kg are shown as gliders or flightless, and those between about 26 and 75 kg are flagged as borderline, based on the soaring-animal size limit estimate
applies_to: [size, behavior, limbs]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC2670537

### RC-R3-06
rule: When a fusion is scaled well above its leg donor's size, straighten the limbs toward an upright posture and reduce agility claims, because larger mammals use upright limbs to keep bone and muscle stress safe
applies_to: [limbs, size, behavior]
strength: soft
status: VERIFIED
source: https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18

### RC-R3-07
rule: Above roughly horse size, also thicken limb bones relative to their length, since posture alone stops compensating
applies_to: [limbs, size]
strength: soft
status: VERIFIED
source: https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling

### RC-R3-08
rule: Cat-derived legs may keep a crouched stance at larger sizes, shown with heavier support muscles, since felids keep a crouched posture across a wide size range
applies_to: [limbs, size]
strength: soft
status: VERIFIED
source: https://rvc-repository.worktribe.com/OutputFile/1397435

### RC-R3-09
rule: Arthropod parts (exoskeleton, jointed insect legs, insect wings) must not appear at large mammal size in a plausible fusion; if a pair forces it, label the result speculative and say that insect breathing limits size
applies_to: [size, body, limbs, pipeline]
strength: hard
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC1941816

### RC-R3-10
rule: Tentacle and trunk parts are rendered jointless and smoothly curving (no elbows, knees or hooves), and a longer tentacle is a thinner one
applies_to: [limbs, tail, face]
strength: soft
status: VERIFIED
source: https://scholars.duke.edu/display/pub798983

### RC-R3-11
rule: Tentacles used as weight-bearing legs on a heavy land animal are treated as speculative
applies_to: [limbs, pipeline]
strength: soft
status: UNVERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6793066

### RC-R3-12
rule: Physical checks run after trait selection in a fixed order (body-plan class, limb budget, size ceiling, posture, part rendering); a failed check either changes the design or adds a visible speculative label, never a silent pass
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling
