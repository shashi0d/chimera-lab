# R5. Real chimeras: one body built from two cell lines

Doc: docs/evolution/research/R5_real_chimeras.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (the chimera path for pairs that cannot hybridize)
Related: R1 (PATCH operator, mosaic patches), R2 (real hybrids and when they apply), R6 (patchwork read as most fused)

## Why this doc exists

R2 covers hybrids, where every cell carries both parents' DNA and traits land in between. Most of our pairs (lion plus eagle, horse plus octopus) can never hybridize, so R2 routes them here. A biological chimera is different: one body built from two separate cell populations, each keeping its own species identity. Real chimeras have been made in labs, and they show what "two animals in one body" looks like when it is not a part swap.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. In a chimera, each cell stays one species. So the visible result is patches and regions of each parent's tissue, not an in-between blend.
2. The host embryo sets the frame. In rat and mouse chimeras, body size and organ formation followed the host.
3. Chimeras are not 50:50, and the mix varies between individuals.
4. Donor tissue brings its own color, but the host body can decide where the pattern shows.
5. Behavior can travel with brain tissue.
6. Every documented interspecies chimera is between fairly close relatives. A chimera of distant body plans (bird plus octopus) has no biological precedent and must be labeled speculative.

## Case studies

### 1. Quail and chick chimeras

Nicole Le Douarin's lab grafted quail embryo tissue into chick embryos. Because quail and chick cells can be told apart under the microscope, each cell's species is identifiable after development [S1]. Material from the Society for Developmental Biology shows hatched chimeras with dark, pigmented quail feathers in the region of the graft and light chick feathers elsewhere; the chimeras had normal movement at hatching, but around two months of age the host rejected the quail graft and the birds developed paralysis [S1].

Pattern detail. A University College London doctoral thesis on pigment patterns found that quail neural crest cells grafted into chick gave a pigment pattern bearing little resemblance to the quail donor, and that in quail and guinea fowl chimeras the pattern mostly matched the genotype of the host feathers rather than the donor cells. The proposed model is that local cues in the skin decide which pigment cells switch on [S2].

Behavior. Transplanting large parts of the quail brain into chick embryos transferred some aspects of species-typical crowing behavior [S3].

Engine lesson: donor regions are fully the donor's tissue (dark quail feathers next to light chick feathers, no blend), they align with body regions (the graft level), the host body can control where a pattern appears, and behavior follows the tissue that produces it.

### 2. Sheep and goat chimeras ("geep")

Researchers at the Institute of Animal Physiology in Cambridge combined sheep and goat embryos and reported viable sheep and goat chimeras in Nature in 1984 [S4]. Contemporary farm press coverage described the animals as having patches of goat hair and sheep wool, with some looking sheep-like and some goat-like, and noted foot problems because the two species have different hooves [S5]. That appearance detail comes from journalism, not from the paper's abstract, so it is UNVERIFIED.

Engine lesson: a chimera's surface is a patchwork of both parents' coat types, the overall look can lean either way, and mismatched parts can cause problems where they meet.

### 3. Rat and mouse chimeras

Kobayashi and colleagues at the University of Tokyo injected rat stem cells into mouse embryos and the reverse, producing live rat and mouse chimeras. Their development was mainly shaped by the host embryo and foster mother, visible in body size and species-specific organ formation. They also grew a working rat pancreas inside mice that lacked their own [S6]. A Nature Methods highlight of the work stressed that the chimeras were not 50:50 rat and mouse, and that earlier attempts at viable mouse and rat chimeras had failed [S7].

Engine lesson: the host sets body size and frame; donor tissue contributes regions and organs. A specific organ or part can come wholly from the donor.

## Cross-cutting patterns

### Pattern A. Patches, not blends

Each region of a chimera is fully one species' tissue [S1]. This is the biological version of R1's PATCH operator. Unlike a hybrid (R2), nothing in a chimera is "in between" at the cell level, although the overall animal mixes both.

### Pattern B. Host frame, donor regions

Body size and overall form followed the host in rat and mouse chimeras [S6]. Combined with R6 (the silhouette owner is what people name the animal), this gives a clean design default: the host parent supplies silhouette and size; the donor supplies patches, regions or specific parts.

### Pattern C. Color from donor, layout from host

Donor tissue shows its own pigment [S1], but where pattern appears can follow the host's skin and feather layout [S2]. For the engine: when the donor's coat shows on the host, use the donor's colors in patches whose placement follows the host's body regions, rather than copying the donor's own pattern layout.

### Pattern D. Mixed bodies have seams

Graft rejection in quail and chick chimeras [S1] and reported hoof problems in geep [S5] show that combining tissues has costs at the boundaries. The engine's text can mention a seam or incompatibility where two very different tissues meet. That is honest, and it adds character.

### Pattern E. Only close relatives so far

Sheep with goat, rat with mouse, quail with chick: all documented interspecies chimeras pair species that are fairly closely related, and even rat with mouse succeeded only recently [S7]. Nothing documents a chimera across body plans (vertebrate with cephalopod, bird with mammal). Those fusions are design, not biology, and must say so.

## How the chimera path should work

1. Pick the host: by default the parent with the more structured body (R6), or the user's choice. The host sets silhouette, size class and limb plan (R3).
2. Pick donor regions: whole regions or organs (a tail, the forelimbs as wings, a skin region), aligned with body segments rather than random fragments.
3. Paint donor tissue in patches: few and large (R1), full donor color inside each patch, no blending within a patch.
4. Let the host's body layout decide where donor pattern appears.
5. Run R3 physical checks, then label: "speculative chimera, no real-world precedent" for any pair beyond close relatives.

## What this doc does not settle

- Natural chimerism (for example blood chimerism in twins) is usually invisible from the outside, so it was not used for visual rules.
- Human and primate chimera research exists but is outside scope and ethically sensitive; it is not used here.
- The geep's appearance needs a better primary source than farm press.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, SOC = scientific society, NEWS = journalism.

- [S1] Society for Developmental Biology, Developmental Biology Cinema. Quail-chick chimeras (Nicole Le Douarin material). SOC. https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html
- [S2] Richardson MK (1990). The formation of pigment patterns in bird embryos. PhD thesis, University College London. UNI. https://discovery-pp.ucl.ac.uk/id/eprint/10108322
- [S3] Balaban E, Teillet MA, Le Douarin N (1988). Application of the quail-chick chimera system to the study of brain development and behavior. Science. Record at FAO AGRIS. PR. https://agris.fao.org/search/en/records/65dfe6754c5aef494fe67490
- [S4] Fehilly CB, Willadsen SM, Tucker EM (1984). Interspecific chimaerism between sheep and goat. Nature 307: 634 to 636. PR. https://www.nature.com/articles/307634a0.pdf
- [S5] Farm Show (1984). British scientists create a sheep/goat hybrid (report on the Babraham chimeras). NEWS. https://www.farmshow.com/a_article.php?aid=6960
- [S6] Kobayashi T and colleagues, University of Tokyo (2010). Generation of rat pancreas in mouse by interspecific blastocyst injection of pluripotent stem cells. Cell 142: 787 to 799. PubMed. PR, UNI. https://pubmed.ncbi.nlm.nih.gov/20813264/
- [S7] Nature Methods research highlight (2010). Species collage (on Kobayashi et al.). PR (journal highlight). https://www.nature.com/articles/nmeth1110-872.pdf

## Rule cards

### RC-R5-01
rule: On the chimera path, each region is fully one parent's tissue; blend between regions only at the edges, never within a patch
applies_to: [coat_pattern, coat_texture, coat_color, all_traits]
strength: hard
status: VERIFIED
source: https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html

### RC-R5-02
rule: The host parent sets silhouette, body size and overall frame; the donor contributes regions, organs or patches
applies_to: [body, size, pipeline]
strength: soft
status: VERIFIED
source: https://pubmed.ncbi.nlm.nih.gov/20813264/

### RC-R5-03
rule: Chimeras are not 50:50; allow the donor share to vary between runs, and never present a fixed even split as the biological norm
applies_to: [all_traits, pipeline]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/nmeth1110-872.pdf

### RC-R5-04
rule: Donor regions keep the donor's own color and surface (feathers, hair, skin), shown at full strength inside the region
applies_to: [coat_color, coat_texture]
strength: soft
status: VERIFIED
source: https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html

### RC-R5-05
rule: Where donor pattern appears follows the host's body layout (its skin and feather regions), not the donor's own pattern layout
applies_to: [coat_pattern]
strength: soft
status: VERIFIED
source: https://discovery-pp.ucl.ac.uk/id/eprint/10108322

### RC-R5-06
rule: Donor regions align with body segments or regions (the level of a graft), not random scattered fragments
applies_to: [coat_pattern, body]
strength: soft
status: VERIFIED
source: https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html

### RC-R5-07
rule: Behavior can follow the parent that supplied the brain or head tissue
applies_to: [behavior, head]
strength: soft
status: VERIFIED
source: https://agris.fao.org/search/en/records/65dfe6754c5aef494fe67490

### RC-R5-08
rule: A sheep and goat style chimera shows mixed patches of both coat types (hair and wool), with the overall look leaning toward either parent
applies_to: [coat_texture, body]
strength: soft
status: UNVERIFIED
source: https://www.farmshow.com/a_article.php?aid=6960

### RC-R5-09
rule: Where very different tissues meet, the description may note a seam or incompatibility; never claim a distant-pair chimera would be healthy or viable
applies_to: [pipeline, behavior]
strength: soft
status: VERIFIED
source: https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html

### RC-R5-10
rule: Documented interspecies chimeras pair close relatives only; any chimera between distant groups must be labeled a speculative design with no real-world precedent
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.nature.com/articles/nmeth1110-872.pdf
