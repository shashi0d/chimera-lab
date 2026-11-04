# R1. Inheritance: how traits pass from two parents to one offspring

Doc: docs/evolution/research/R1_inheritance.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (the trait operators PICK, BLEND, OVERLAY, GATE, PATCH, PACKAGE)
Related: R2 (real hybrids, the observed outcomes this doc explains)

## Why this doc exists

The current pipeline asks "which parent is dominant?" and gives that parent whole body parts. Genetics does not work at that level. Dominance describes how two versions of one gene behave together, and different traits follow different inheritance modes. This doc maps each real inheritance mode to an operator the engine can apply per trait.

Plain-language glossary:
- Gene: one instruction in the DNA. Allele: one version of that instruction.
- Genotype: the alleles an animal carries. Phenotype: what you can see.
- Every offspring gets one allele of each gene from each parent.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. There is no "dominant parent". Dominance is a relationship between two alleles of a single gene, so the engine should decide per trait, never per animal.
2. Most visible size and shape traits are controlled by many genes at once and land on a continuous scale. Their default is a blend near the midpoint with some spread.
3. Some single-gene traits show one version fully (complete dominance), some show an in-between (incomplete dominance), and some show both side by side (codominance). These map to PICK, BLEND and OVERLAY.
4. Some genes switch others on or off (epistasis). A trait can be "inherited" and still not show because another gene hides it. This maps to GATE.
5. Patchwork coats are a real biological outcome, made when different cells in one body use different alleles. This maps to PATCH.
6. Some traits travel together because they come from the same embryonic tissue. This maps to PACKAGE, and it is the strongest argument against freely mixing face, ears and coat color from different parents.

## 1. Complete dominance, incomplete dominance, codominance

Complete dominance. One allele hides the other, so an animal with one copy of each looks the same as an animal with two copies of the dominant one [S1], [S2].

Incomplete dominance. The animal with one of each looks in between the two pure forms. The classic teaching example is red x white snapdragons giving pink flowers [S1], [S2].

Codominance. Both versions show fully at the same time. Teaching examples include AB blood type, and camellia flowers that show pink and white patches together [S1], [S2].

Multiple alleles. A gene can have more than two versions in a population, and they can form a ranking where some are dominant to others while two are codominant with each other [S1].

Key point for us: all of these are defined for alleles of one gene [S1], [S2]. Nothing in genetics makes a whole species or a whole parent "dominant". Our "dominant parent" field is a design shortcut, not biology.

Engine mapping:
- PICK: one parent's version appears fully. Use for discrete either-or traits (horn present or absent, a tail tuft present or absent).
- BLEND: an in-between value. Use for traits that look like a dial (color shade, ear length).
- OVERLAY: both parents' versions visible together. Use for patterns (stripes over a base coat, spots over a color).

## 2. Polygenic traits: most body measurements

Many traits are controlled by many genes, each adding a small effect. These traits vary smoothly rather than falling into a few types, and across a population they form a bell curve, with most individuals near the middle and few at the extremes. Human height is the standard example [S3]. Teaching sources stress that environment (for example nutrition) also shifts these traits [S3].

What this means for a cross between two different parents: with many small-effect genes, an offspring that receives about half from each parent usually lands near the middle. R2 confirms this for real animal hybrids, where most traits were intermediate and extremes beyond both parents were a minority (about a quarter to a third of animal traits, depending on the comparison) [S10].

Engine mapping: BLEND with spread. For size, body mass, limb length, neck length, tail length, ear length, snout length and similar: start at the midpoint between parents (on a log scale for size, since body mass spans orders of magnitude), add modest random variation, and only rarely allow a value outside both parents.

The log-scale choice is a design decision, not something these sources state. It is recorded in a soft UNVERIFIED card so R3 (body-plan limits and scaling) can confirm or replace it.

## 3. Epistasis: genes that hide other genes

Sometimes the effect of one gene depends on another gene. The textbook case is Labrador retriever coat color. One gene sets the pigment color (black or brown). A second gene controls whether that pigment gets deposited in the hair at all. A dog with two copies of the "no deposit" version is yellow no matter what the color gene says [S4], [S5]. Newcastle University's teaching wiki describes this as the genotype at one gene determining whether another gene's effect is expressed [S5].

Engine mapping: GATE. Some traits only show when a precondition is met. For a fusion this suggests rules like: a fur pattern needs fur to show on; a mane needs hair; a color pattern on a region needs that region to carry the pattern-bearing surface. Those specific fusion rules are our design inference from the principle, not facts stated in the sources, so their cards are UNVERIFIED and should be refined by R3 (body plans).

## 4. Mosaic patches: one body, two versions

Female mammals have two X chromosomes and switch one off at random in each cell early in development. In tortoiseshell and calico cats, one X carries an orange-color version of a gene and the other carries a black version, so patches of fur show one or the other. Researchers at Kyushu University identified the deletion behind the orange version and describe these coats as the classic visible example of random X inactivation [S6]. A University of Southern Maine review notes that each patch grows from a single cell, which is why the coat forms large blocks rather than a fine blend [S7].

Popular coverage adds that earlier switching gives larger patches, but I only found that in a news source, so it is UNVERIFIED [S11].

Engine mapping: PATCH. A coat can be made of distinct blocks, each fully one parent's version, with clear edges and no blending inside a block. Note that in nature this happens within one species from two alleles. Using it between two species is closer to a chimera (R5).

## 5. Linked packages: traits that share an origin

Darwin noticed that domesticated mammals tend to share an odd set of traits: white patches in the coat, shorter muzzles, smaller teeth, floppy or reduced ears, and tameness. A 2014 paper in the journal Genetics proposed that these all trace back to the neural crest, a group of embryonic cells that builds pigment cells, much of the face and skull, ear cartilage, teeth precursors and part of the adrenal system. Mild changes to neural crest cells would therefore shift all of these traits together [S8].

This explanation is still a hypothesis. The authors themselves published a 2021 reply to critics defending and clarifying it [S9], so the idea is debated. What is not debated is that these tissues share a developmental origin [S8].

Engine mapping: PACKAGE. Face shape, ear form and pigment pattern are developmentally linked, so they are more believable when they come mostly from the same parent, or shift together in the same direction. Mixing a donkey's long ears with a horse's face is fine (the mule does it, see R2), so this is a soft preference, not a ban.

## 6. Parent-of-origin effects

Some genes are switched on or off depending on whether they came from the father or the mother (genomic imprinting). In crosses between two deer mouse species, one direction gives undersized young and the other gives oversized young, and the imprinting system breaks down in the hybrids [S10b]. R2 covers the liger and tigon example in detail.

Engine mapping: the sire and dam roles must be stored and can change outcomes (RC-R2-01 covers the pipeline rule; this doc adds the reason).

## 7. Summary table: trait type to operator

| Trait kind | Real inheritance mode | Engine operator | Typical traits |
|---|---|---|---|
| Measurements | Polygenic, mostly additive | BLEND with spread | size, limb, neck, tail, ear and snout length |
| Either-or features | Often single-gene, complete dominance | PICK | horns, tail tuft, crest, presence of a mane |
| Shades | Incomplete dominance or polygenic | BLEND | base color, pattern contrast |
| Patterns over a base | Codominance-like, both visible | OVERLAY (diluted per R2) | stripes, spots, rosettes |
| Patchwork | Cell-level mosaic | PATCH | tortoiseshell-style coats |
| Masked traits | Epistasis | GATE | pattern needs fur, mane needs hair |
| Linked traits | Shared developmental origin | PACKAGE | face, ears, pigment |
| Direction-specific | Imprinting | keep sire and dam roles | size overshoot cases |

## What this doc does not settle

- Real genetics only applies to species that can actually interbreed, and hybridization is most likely between recent, closely related species [S12]. For distant pairs, these operators are a disciplined way to design, not a prediction of a real animal. The output must be labeled as speculative.
- Which specific traits are single-gene versus polygenic in each animal is mostly unknown. The engine should assume polygenic BLEND for anything that looks like a measurement and PICK only for clearly present-or-absent features.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, EDU = open educational textbook, NEWS = journalism.

- [S1] Salt Lake Community College, College Biology I (OpenStax-based). 20.1 Incomplete dominance, codominance, and multiple alleles. EDU, UNI. https://slcc.pressbooks.pub/collegebiology1/chapter/incomplete-dominance-and-codominance/
- [S2] LibreTexts Biology, Classical Genetics (Khan Academy). 2.2 Multiple alleles, incomplete dominance, and codominance. EDU. https://bio.libretexts.org/Bookshelves/Genetics/Classical_Genetics_(Khan_Academy)/02%3A_Non-Mendelian_inheritance/2.02%3A_Multiple_alleles_incomplete_dominance_and_codominance
- [S3] JoVE Science Education. Polygenic traits. EDU. https://www.jove.com/science-education/10778/polygenic-traits
- [S4] LibreTexts Biology, Online Open Genetics (Nickle and Barrette-Ng). 6.2 Epistasis and other gene interactions. EDU. https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/06%3A_Genetic_Analysis_of_Multiple_Genes/6.02%3A_Epistasis_and_Other_Gene_Interactions
- [S5] Mt. Hood Community College Majors Biology (Open Oregon open textbook). Epistasis, mouse coat color example. UNI. https://openoregon.pressbooks.pub/mhccmajorsbio/chapter/epistasis/
- [S6] Toh H, Sasaki H and colleagues, Kyushu University (2025). A deletion at the X-linked ARHGAP36 gene locus is associated with the orange coloration of tortoiseshell and calico cats. Kyushu University repository copy. PR, UNI. https://catalog.lib.kyushu-u.ac.jp/opac_download_md/7390840/7390840.pdf
- [S7] University of Southern Maine, Thinking Matters symposium (2019). X chromosome inactivation and calico cats (literature review poster). UNI. https://digitalcommons.usm.maine.edu/thinking_matters/173
- [S8] Wilkins AS, Wrangham RW, Fitch WT (2014). The "domestication syndrome" in mammals: a unified explanation based on neural crest cell behavior and genetics. Genetics 197: 795 to 808. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC4096361/
- [S9] Wilkins AS, Wrangham R, Fitch WT (2021). The neural crest/domestication syndrome hypothesis, explained: reply to Johnsson, Henriksen, and Wright. Genetics 219: iyab098. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC8633094
- [S10] Rieseberg LH, Archer MA, Wayne RK (1999). Transgressive segregation, adaptation and speciation. Heredity 83: 363 to 372. PR. https://www.nature.com/articles/6886170
- [S10b] Vrana P, Guan X, Ingram R, Tilghman S (1998). Genomic imprinting is disrupted in interspecific Peromyscus hybrids. Nature Genetics 20: 362 to 365. PR, UNI. https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids
- [S11] Live Science. Scientists reveal genes that make cats orange. NEWS. https://www.livescience.com/health/genetics/scientists-reveal-genes-that-make-cats-orange
- [S12] Mallet J (2007). Hybrid speciation. Nature 446: 279 to 283. Author copy at University College London. PR, UNI. https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf

## Rule cards

### RC-R1-01
rule: Decide inheritance per trait, never per animal; the engine must not assign one parent as dominant for the whole creature, because dominance is defined between alleles of a single gene
applies_to: [pipeline, all_traits]
strength: hard
status: VERIFIED
source: https://slcc.pressbooks.pub/collegebiology1/chapter/incomplete-dominance-and-codominance/

### RC-R1-02
rule: Measurement traits (size, limb, neck, tail, ear and snout length) use BLEND: start near the midpoint of the parents and add modest random spread, since many-gene traits vary continuously and cluster around the middle
applies_to: [size, limbs, tail, ears, face, body]
strength: soft
status: VERIFIED
source: https://www.jove.com/science-education/10778/polygenic-traits

### RC-R1-03
rule: Blend body size on a log scale (geometric mean of parent masses) rather than a plain average
applies_to: [size]
strength: soft
status: UNVERIFIED
source: https://www.jove.com/science-education/10778/polygenic-traits

### RC-R1-04
rule: Clearly present-or-absent features (horns, crest, tail tuft, mane presence) use PICK: the feature comes fully from one parent or is absent, not half-formed
applies_to: [head, mane, tail]
strength: soft
status: VERIFIED
source: https://bio.libretexts.org/Bookshelves/Genetics/Classical_Genetics_(Khan_Academy)/02%3A_Non-Mendelian_inheritance/2.02%3A_Multiple_alleles_incomplete_dominance_and_codominance

### RC-R1-05
rule: Shade-like traits (base coat color, contrast) may use BLEND, matching incomplete dominance where the in-between form appears
applies_to: [coat_color]
strength: soft
status: VERIFIED
source: https://slcc.pressbooks.pub/collegebiology1/chapter/incomplete-dominance-and-codominance/

### RC-R1-06
rule: Patterns may use OVERLAY, where both parents' features are visible at once (a pattern over a base color), matching codominance; per R2 the pattern is shown diluted when its donor does not own the body
applies_to: [coat_pattern, coat_color]
strength: soft
status: VERIFIED
source: https://slcc.pressbooks.pub/collegebiology1/chapter/incomplete-dominance-and-codominance/

### RC-R1-07
rule: Some traits can be inherited yet hidden because another trait controls whether they show (GATE); evaluate gating traits before the traits they control
applies_to: [pipeline, coat_pattern, coat_color]
strength: soft
status: VERIFIED
source: https://openoregon.pressbooks.pub/mhccmajorsbio/chapter/epistasis/

### RC-R1-08
rule: Gate examples for fusions: a fur pattern only shows on regions that carry fur; a mane only shows where the body carries hair
applies_to: [coat_pattern, mane, coat_texture]
strength: soft
status: UNVERIFIED
source: https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/06%3A_Genetic_Analysis_of_Multiple_Genes/6.02%3A_Epistasis_and_Other_Gene_Interactions

### RC-R1-09
rule: PATCH is a valid coat mode: distinct blocks with clear edges, each block fully one version, no blending inside a block, as in tortoiseshell and calico cats
applies_to: [coat_pattern, coat_color]
strength: soft
status: VERIFIED
source: https://catalog.lib.kyushu-u.ac.jp/opac_download_md/7390840/7390840.pdf

### RC-R1-10
rule: Each mosaic patch grows from a single cell lineage, so patches should be few and large rather than fine speckles
applies_to: [coat_pattern]
strength: soft
status: VERIFIED
source: https://digitalcommons.usm.maine.edu/thinking_matters/173

### RC-R1-11
rule: Face shape, ear form and pigment pattern share a developmental origin (neural crest); prefer taking them from the same parent or shifting them in the same direction
applies_to: [face, ears, coat_pattern, skull]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4096361/

### RC-R1-12
rule: Do not present the domestication syndrome explanation as settled science in any user-facing text; it is a debated hypothesis
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC8633094

### RC-R1-13
rule: Allow a small share of traits to land beyond both parents; extremes are common in hybrids overall but rarer in crosses between wild animal species
applies_to: [all_traits]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/6886170

### RC-R1-14
rule: Genetics-based operators only predict real outcomes for parents that can interbreed; for any other pair the fusion must be labeled speculative design, not a predicted animal
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf
