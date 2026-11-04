# R6. Perception: what makes a fused creature read as one animal made from both parents

Doc: docs/evolution/research/R6_perception.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (identity choice, signature cues, the readability critic)
Related: R1 to R3 decide what is plausible; this doc decides what people will actually see

## Why this doc exists

A creature can be biologically sensible and still fail as a picture: our eagle plus octopus runs read as "an eagle sitting on an octopus", and the mule render was correct but nobody would see a chimera in it. The goal here is the viewer's side: what people look at first, what they use to decide what an animal is, and how people naturally build hybrids in their heads.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Shape carries identity for human viewers. In a well-known experiment a cat shape covered in elephant skin texture is still a cat to people. Whoever owns the silhouette owns the name.
2. Texture and pattern are the "adjective": they tell viewers which other animal is involved, but they do not change what the creature is.
3. People look at the head and eyes first, and they hunt for eyes even when eyes are not on the head. The head donor sets the first impression; eyes must be easy to find.
4. People decide "that is an animal" from a glance of well under a second. A fusion must read as one animal at thumbnail size.
5. When people imagine new creatures they keep bilateral symmetry, sense organs and limbs. When they build hybrids, they take the overall shape from the more structured parent.
6. Image classifiers do not see like people: many lean on texture where people lean on shape. A critic model's label alone is not proof that a human will read the image correctly.

## 1. Shape names the animal, texture modifies it

Geirhos and colleagues ran nine psychophysical experiments (97 observers, about 48,500 trials) comparing people with standard image classifiers on pictures where shape and texture disagree, such as a cat outline filled with elephant skin. People mostly answered with the shape category; the classifiers mostly answered with the texture category [S7]. The paper also notes that object shape is regarded as the single most important cue for human object recognition, more than size or texture [S7].

Engine mapping: the body silhouette donor is the creature's noun ("a lion"), and the other parent arrives mostly through surface and selected parts (the adjective: "octopus-skinned", "eagle-winged"). Choosing the silhouette donor is choosing the identity, so it must be a deliberate decision (or a user dial), never a side effect of image order.

## 2. Heads and eyes get looked at first

In an eye-tracking study, adults viewing animal pictures showed a strikingly consistent pattern: the head and eyes drew many fixations, alongside a few species-specific parts (a cat's tail, a cow's udder, a snake's body), and the order of looking was similar across people. The authors attribute this to the shared structure of animals, especially having a head [S4].

A Biology Letters study used fantasy monsters with eyes in odd places (hands, tails, tentacles). Viewers still looked at the eyes early and often, wherever they were, which shows people target eyes themselves, not just the middle of the head [S5].

Engine mapping:
- The head donor shapes the first impression more than any other part, so the head should be fully visible, not cropped or hidden.
- Every creature needs clearly discernible eyes. Extra or displaced eyes will grab attention, so use them only on purpose.
- Species-specific "signature parts" (a tail tuft, a trunk) also draw looks and are the best carriers of the second parent's identity.

## 3. The first glance decides

Thorpe and colleagues flashed unseen photographs for 20 ms and asked people whether each contained an animal. Brain responses separating "animal" from "no animal" appeared roughly 150 ms after the image, showing the needed visual processing happens in under 150 ms [S6].

Engine mapping: readability must hold at a glance. A practical check is to test the render at small size (a thumbnail) as well as full size. That thumbnail test is our design inference from this finding, so its card is UNVERIFIED.

## 4. Imagination follows known body rules

Ward asked people to invent animals for a distant, very different planet. Even when told to be as imaginative as possible, most creations kept Earth-animal features: bilateral symmetry, sense organs such as eyes, and limbs [S1]. A King's College London article summarizes the conclusion: imagination of the unfamiliar is structured by what people already know [S2].

Engine mapping: keep bilateral symmetry, visible sense organs and recognizable limbs unless the user explicitly asks for something alien. These are what make an invented creature read as an animal at all. This also supports R3: designs that break these features should be labeled, not slipped through.

## 5. How people build hybrids in their heads

Shen and Gil studied how people construct hybrids from two or more "parents". They propose that the overall shape of the hybrid is chosen by a small set of principles tied to abstract body schemas defined by parts, symmetry and orientation, arranged in a hierarchy: human-like over dog-like (four-legged animal) over car-like over knife-like over tree-like over shapeless. A schema higher in the hierarchy is preferred as the hybrid's overall shape [S3].

Engine mapping: when one parent has a strongly structured body (a four-legged mammal, a bird) and the other is comparatively shapeless (an octopus, a jellyfish), the structured parent should supply the overall frame by default, and the shapeless parent contributes surface, limbs-as-tentacles or signature parts. Where specific animals sit in that hierarchy (for example whether a bird counts as dog-like) is our interpretation, not stated by the source, so that mapping is UNVERIFIED.

## 6. Machines judge differently from people

The same Geirhos study found that standard image classifiers rely heavily on texture: a cat with elephant texture is an elephant to the network [S7]. That result is for classic ImageNet-trained networks. Whether Meta's current vision models share this bias is unknown and should be tested, not assumed.

Engine mapping: the readability critic (a model shown the image cold and asked which animals it is made from) is useful, but its answer can be swayed by texture. Pair it with a shape check, such as comparing the segmented silhouette against the planned body donor.

## 7. Project observations (not literature)

These come from our own saved runs in docs/live/, not from published sources. They are consistent with sections 1 and 2 but are single runs:
- In eagle plus octopus renders, whichever animal owned the head was what the creature read as.
- The two-step "chimera" render read as two animals stacked, not one creature.
- The lion plus octopus render, where octopus mottling spread across the haunch, read as the most fused.

## What this doc does not settle

- Cultural differences in how hybrids are read.
- How much a written label or name changes what people see. Shen and Gil's related work suggests language matters, but it was not reviewed here.
- How Meta's specific models perceive fused creatures. That needs a small live test.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, PRE = peer-reviewed conference paper with arXiv copy.

- [S1] Ward TB and colleagues (2002). Article in Memory and Cognition (Psychonomic Society) reviewing structured imagination, including Ward (1994) on imagined alien animals. PR. https://link.springer.com/content/pdf/10.3758%2FBF03195281.pdf
- [S2] King's College London. Responses: the philosophising brain (summary of Ward 1994). UNI. https://www.kcl.ac.uk/responses-the-philosophising-brain
- [S3] Shen Y, Gil D (2023). How to build a hybrid: the structure of imagination. Poetics Today 44(4): 513 to 543. Tel Aviv University research portal. PR, UNI. https://cris.tau.ac.il/en/publications/how-to-build-a-hybrid-the-structure-of-imagination/
- [S4] Kovic V, Plunkett K, Westermann G (2009). An eye-tracking study of animate objects. Psihologija 42(3): 307 to 327. Lancaster University repository. PR, UNI. https://eprints.lancs.ac.uk/id/eprint/50885/
- [S5] Levy J, Foulsham T, Kingstone A (2013). Monsters are people too. Biology Letters 9: 20120850. University of Essex repository. PR, UNI. https://repository.essex.ac.uk/9355/
- [S6] Thorpe S, Fize D, Marlot C (1996). Speed of processing in the human visual system. Nature 381: 520 to 522. PubMed. PR. https://pubmed.ncbi.nlm.nih.gov/8632824/
- [S7] Geirhos R and colleagues, University of Tuebingen (2019). ImageNet-trained CNNs are biased towards texture; increasing shape bias improves accuracy and robustness. ICLR 2019. PRE, UNI. https://arxiv.org/abs/1811.12231v3

## Rule cards

### RC-R6-01
rule: The body silhouette donor sets the creature's identity for human viewers; choose it deliberately (or expose it as a user control), never as a side effect of input order
applies_to: [body, pipeline]
strength: soft
status: VERIFIED
source: https://arxiv.org/abs/1811.12231v3

### RC-R6-02
rule: Carry the second parent mainly through surface texture, pattern and selected signature parts, which tell viewers which other animal is involved without changing what the creature is
applies_to: [coat_pattern, coat_texture, coat_color, all_traits]
strength: soft
status: VERIFIED
source: https://arxiv.org/abs/1811.12231v3

### RC-R6-03
rule: Keep the head fully visible and uncluttered; the head and eyes draw the earliest and most looks, so the head donor dominates the first impression
applies_to: [head, face]
strength: soft
status: VERIFIED
source: https://eprints.lancs.ac.uk/id/eprint/50885/

### RC-R6-04
rule: Every creature must have clearly discernible eyes; viewers search for eyes wherever they are, so extra or displaced eyes are used only on purpose
applies_to: [face, head]
strength: soft
status: VERIFIED
source: https://repository.essex.ac.uk/9355/

### RC-R6-05
rule: Signature parts that draw looks on the real animal (a tail tuft, a trunk, an udder-like feature) are the best carriers of the second parent's identity
applies_to: [tail, face, body]
strength: soft
status: VERIFIED
source: https://eprints.lancs.ac.uk/id/eprint/50885/

### RC-R6-06
rule: The creature must read as one animal at a glance; test the render at thumbnail size as well as full size
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://pubmed.ncbi.nlm.nih.gov/8632824/

### RC-R6-07
rule: Keep bilateral symmetry, visible sense organs and recognizable limbs unless the user explicitly asks for an alien design, because these are what make an invented creature read as an animal
applies_to: [body, face, limbs]
strength: soft
status: VERIFIED
source: https://link.springer.com/content/pdf/10.3758%2FBF03195281.pdf

### RC-R6-08
rule: When building a hybrid, take the overall shape from the parent with the more structured body schema; a schema higher in the human-like, four-legged, object, shapeless hierarchy is preferred
applies_to: [body, pipeline]
strength: soft
status: VERIFIED
source: https://cris.tau.ac.il/en/publications/how-to-build-a-hybrid-the-structure-of-imagination/

### RC-R6-09
rule: Specific mapping for our animals: four-legged mammals and birds count as structured frames; octopus, jellyfish and similar soft-bodied animals count as low-structure donors that contribute surface, tentacles or signature parts
applies_to: [body, limbs]
strength: soft
status: UNVERIFIED
source: https://cris.tau.ac.il/en/publications/how-to-build-a-hybrid-the-structure-of-imagination/

### RC-R6-10
rule: A model critic's animal label is not proof of human readability, because standard image classifiers lean on texture where people lean on shape; pair the critic with a silhouette check against the planned body donor
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://arxiv.org/abs/1811.12231v3

### RC-R6-11
rule: Readability critic test: show the final image cold and ask which two animals it combines and whether it is one creature or two; pass only if both parents are named and it reads as one creature
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://cris.tau.ac.il/en/publications/how-to-build-a-hybrid-the-structure-of-imagination/
