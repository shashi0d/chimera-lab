# R10. Chimera science landscape: how real chimeras decide which species wins each part

Doc: docs/evolution/research/R10_chimera_science_landscape.md
Status: research, first pass (Oct 31, 2026); cards 12 to 14 added in S3a, 15 and 16 in S3b (Nov 1, 2026); RC-R10-13 superseded by RC-R10-15
Feeds: ALGORITHM.md (host and region selection, plan-level evolution, new LAYER operator, multi-parent trees, evolve carry-over)
Related: R1 (dominance per gene), R5 (real chimeras), R8 (generative evolution), R9 (function audit)

## Why this doc exists

R1 showed that dominance is a relation between two alleles of one gene, so a distant-pair chimera has nothing for dominance to act on. This doc asks the next question: in real chimeras, what does decide which species' cells end up in which part of the body? The answer turns out to be four mechanisms (competition, empty niches, tissue autonomy and layers), and each one transfers cleanly into the engine. It also surveys what other fields (plant chimeras, animals that borrow other species' parts, AI image blending) have learned.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Dominance is not strength or fitness. Even for genes, that reading is a known misconception. The engine never ranks a whole parent as dominant.
2. In real chimeras, each part is contested, and the fitter cells win it. The winner depends on the pair, not on a fixed ranking of species. This is the real-world base for plan-level selection.
3. Donor cells thrive where the host leaves an empty niche. Donor parts belong first where the host lacks a structure.
4. Some tissues carry their own species' blueprint wherever they go. A transplanted face skeleton keeps the donor's shape and size and even reshapes the host tissue next to it. Other tissues obey the host: organs grow to host size.
5. Plants show a third architecture: one species' skin over another species' body (a layer chimera).
6. Borrowed parts only work if the new body supports them.
7. Real three-species animals form as a family tree of pairwise crosses, and each parent shows in different features.
8. AI image blending research finds no single blending method suits every pair, and multi-concept images degrade past about three concepts.

## 1. Dominance: what transfers and what does not

Two education studies confirm the trap. A large survey of about 1,000 junior high students in Japan found about 90 percent believed dominant traits are better for survival or more common [S18]. A history-of-science essay on Mendel argues that a recessive allele is not suppressed by the dominant one; in a dominant and recessive pair, both alleles are expressed [S17].

What transfers is the philosophy, not the word:
- Each part of the body has two candidate versions, one from each parent.
- One version is expressed by a rule decided per part, never per animal (R1).
- The other version is carried, not destroyed. In genetics, a hidden recessive can reappear in a later generation. The engine can do the same in evolve: the genome carries both versions for each region, and an offspring may express the carried one (RC-R10-11, a design analogy, not biology).

For distant pairs, the expression rule cannot come from genes. Sections 2 to 4 show what real chimeras use instead.

## 2. Competition: the fitter cells win the contested part

When two species' cells share one embryo, they compete. A 2021 Nature study co-cultured human and mouse stem cells and found a previously unknown form of cell competition between species; the human cells lost and were eliminated [S1]. A Cell Stem Cell review summarizes the wider pattern: human stem cells were eliminated by mouse or rat cells but not by rhesus monkey cells, and human cells in turn eliminated cow cells, while mouse cells eliminated both monkey and cow cells [S2].

Two points matter for the engine:
- The winner is decided per pairing, not by a fixed ranking of species.
- The outcome can be changed. Disabling a single signaling pathway in the losing human cells let them survive and contribute more [S1].

Engine mapping: every region of the creature is a contest between the two parents' versions, scored by fitness in that body and habitat (plan-level selection, E5). There is no global "stronger animal". Mass is not a reason to win.

## 3. Empty niches: donors thrive where the host leaves room

Blastocyst complementation is how labs grow one species' organ inside another. A Development review explains the method: the host is engineered to lack an organ, which opens an empty developmental niche that donor cells fill with minimal competition from host cells [S4]. In a variant, disabling a growth receptor in the host gave donor cells a growth advantage from mid-gestation, and donor contribution kept rising over time, even after birth [S3].

Engine mapping: donor parts belong first in the host's empty niches, where the host lacks a structure that the donor has. An axolotl has no armor, so pangolin scales fill an empty niche on an axolotl body. Replacing a working host part needs a clear fitness gain. This is a strong, sourced argument for the axolotl host in axolotl x pangolin.

## 4. Tissue autonomy: some parts carry their own blueprint

Quail and duck chimeras are the clearest case. When the neural crest cells that build the beak were swapped between quail and duck embryos, quail cells built quail beaks on duck hosts and duck cells built duck bills on quail hosts. The donor cells ran their own programs and even changed gene expression in the host tissue next to them [S5], [S6]. The resulting birds are nicknamed "quck" and "duail", and the donor cells set both the size and the shape of the beak [S6].

Organs behave differently. A University of Tokyo team grew rat pancreases in mice, and they came out mouse-sized; in the reverse experiment, mouse pancreases grown in rats came out rat-sized [S7].

Engine mapping, a per-region autonomy rule:
- Face, jaw and beak skeleton: donor-autonomous. The donor part keeps its own shape and proportions, and the seam bends the host tissue toward it.
- Internal organs and overall body size: host-controlled. This matches RC-R5-02 (host sets size).

## 5. Layers: one species' skin over another's body

Plants add an architecture animals rarely show. A plant shoot grows from three cell layers, L1 (skin) to L3 (core), and a periclinal chimera has layers of different genotypes. Imperial College researchers built a tomato with its skin layer from a wild tomato species and its inner layers from cultivated tomato [S8]. Graft chimeras of this kind can even combine two different species, and the first recorded one, the "Bizarria" orange, appeared at a citrus graft junction in 1644 [S9].

Engine mapping: add a LAYER architecture beside region patches. The donor supplies the surface layer (skin, scales, feathers) over the host body, everywhere or across a whole body zone. PATCH (R1, R5) stays for separate regions. A plant-style layer chimera is real biology, but the animal version is a design inference, so it is labeled speculative.

## 6. Borrowed parts must be supported by the new body

Some animals really do run other species' parts. Sacoglossan sea slugs keep chloroplasts stolen from the algae they eat; a University of Aveiro study found that how well the stolen chloroplasts work depends on how well they match the slug species, not just on their source [S10]. Two of the four chloroplast-stealing species studied keep them without using them, because they lack the genes needed to make them work [S11]. Aeolid nudibranchs eat stinging animals and move the unfired stinging cells into their own back projections, where they serve as a borrowed defense [S12].

Engine mapping: a donor part only counts as working if the host body has the support it needs (R9 function audit). Without that support, the part is shown but labeled non-working, like the slugs that carry chloroplasts they cannot use.

## 7. More than two parents

A 2018 Biology Letters study confirmed a wild three-species warbler: a female hybrid of two Vermivora warblers mated with a chestnut-sided warbler. The male offspring sang like the chestnut-sided species but had body measurements like the Vermivora warblers [S19].

Engine mapping: three-parent creatures are built as a family tree of pairwise steps, ((A x B) x C), and the result is a mosaic in which each parent shows in different features. A three-way mix in one step has no precedent.

## 8. What AI image research has found

A 2025 study of concept blending in text-to-image diffusion models tested four zero-shot blending strategies and found no single approach best in all cases; results depended heavily on the kind of pair, such as animal-animal [S13]. The authors name symbolic constraints and partial blending, where only certain features transfer, as a future direction [S13]. That is close to what this engine already does with rule cards.

The CVPR 2024 Concept Weaver paper notes that earlier multi-concept methods struggled to scale to three or more concepts [S14].

Engine mapping:
- Choose the operator by pair type, not one fixed blend.
- Cap parents at three in realistic and speculative modes, and four in mythic mode with a warning.

## What this doc does not settle

- No study measures which parent "wins" each visible body region in a distant-pair animal chimera, because none exist. The per-region rules are transferred from cell-level and organ-level evidence.
- Layer chimeras are documented in plants, not as whole-animal skin swaps. Animal use is a design inference.
- The evolve carry-over of hidden versions (section 1) is a design analogy, not biology.

## Sources

Labels: PR = peer-reviewed, UNI = university-hosted, NEWS = science news, EDU = education.

- [S1] Zheng C and colleagues (2021). Cell competition constitutes a barrier for interspecies chimerism. Nature 592: 272-276. PR. https://www.nature.com/articles/s41586-021-03273-0
- [S2] Cell competition and the regulative nature of early mammalian development. Cell Stem Cell (2022), review. PR. https://www.cell.com/cell-stem-cell/fulltext/S1934-5909(22)00252-1
- [S3] Growth competition in interspecies chimeras: a new paradigm for blastocyst complementation. Cell Stem Cell (2021), preview of Nishimura et al. PR. https://www.cell.com/cell-stem-cell/fulltext/S1934-5909(20)30595-6
- [S4] The road to generating transplantable organs: from blastocyst complementation to interspecies chimeras. Development 148(12) (2021), review. PR. https://journals.biologists.com/dev/article/148/12/dev195792/269139/The-road-to-generating-transplantable-organs-from
- [S5] Schneider R A (2018). Neural crest and the origin of species-specific pattern. Genesis 56: e23219. PR, UNI (UCSF). https://pmc.ncbi.nlm.nih.gov/articles/PMC6108449
- [S6] Quail-duck chimera study of beak bone growth, Schneider lab, UCSF. PubMed Central. PR, UNI. https://pmc.ncbi.nlm.nih.gov/articles/PMC4698309
- [S7] University of Tokyo, Institute of Medical Science report on Yamaguchi T and colleagues (2017). Interspecies organogenesis generates autologous functional islets. Nature 542: 191-196. PR, UNI. https://www.ims.u-tokyo.ac.jp/imsut/content/900004612.pdf
- [S8] Using a periclinal chimera to unravel layer-specific gene expression in plants. Imperial College London and East Malling Research. PR, UNI. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4223383/
- [S9] Foster T M, Aranzana M J (2018). Attention sports fans! The far-reaching contributions of bud sport mutants to horticulture and plant biology. Horticulture Research. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC6046048
- [S10] Morelli and colleagues (2023). Kleptoplast performance in Elysia viridis depends on the algal donor. University of Aveiro repository. PR, UNI. https://ria.ua.pt/bitstream/10773/40784/1/2023%20Morelli%20et%20al_ORE.pdf
- [S11] Science News. Kleptoplast (on Proceedings of the Royal Society B findings). NEWS. https://www.sciencenews.org/?p=15372
- [S12] X-Ray Mag. How nudibranchs reuse their prey's stinging cells (primary source: Frontiers in Zoology). NEWS. https://xray-mag.com/content/how-nudibranchs-feed-polyps-without
- [S13] Blending concepts with text-to-image diffusion models (2025). arXiv preprint, later published in Discover Artificial Intelligence. PR. https://arxiv.org/pdf/2506.23630
- [S14] Kwon G and colleagues (2024). Concept Weaver: enabling multi-concept fusion in text-to-image models. CVPR 2024. PR. https://openaccess.thecvf.com/content/CVPR2024/papers/Kwon_Concept_Weaver_Enabling_Multi-Concept_Fusion_in_Text-to-Image_Models_CVPR_2024_paper.pdf
- [S17] Allchin D. Mendel's mistake? SHiPS Resource Center essay on dominance. EDU. https://shipseducation.net/updates/mendel2.htm
- [S18] Yamanoi T, Izawa Y, Kanai T (2020). A large-scale survey of junior high school students' comprehension of dominance and recessiveness. Journal of Science Education in Japan 44(3). PR. https://www.jstage.jst.go.jp/article/jssej/44/3/44_188/_article
- [S19] Toews D P L and colleagues (2018). A wood-warbler produced through both interspecific and intergeneric hybridization. Biology Letters 14: 20180557. Penn State research portal. PR, UNI. https://pure.psu.edu/en/publications/a-wood-warbler-produced-through-both-interspecific-and-intergener/

- [S20] Understanding Evolution, University of California Museum of Paleontology. Homologies and analogies: homologous characters are inherited from a common ancestor; analogous ones have separate origins (bird and bat wings are analogous as wings, homologous as forelimbs). UNI. https://evolution.berkeley.edu/evolution-101/the-history-of-life-looking-at-the-patterns/homologies-and-analogies/
- [S21] NC State University General Entomology, Arthropods: the exoskeleton and its jointed appendages are the hallmark of arthropods; the rigid exoskeleton "necessitated membranous joints to provide the flexibility needed for movement". UNI. https://genent.cals.ncsu.edu/bug-bytes/arthropods/

## Rule cards

### RC-R10-01
rule: Never rank a whole parent as dominant or stronger, and never treat dominance as fitness or frequency; neither size nor mass decides which parent wins
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.jstage.jst.go.jp/article/jssej/44/3/44_188/_article

### RC-R10-02
rule: On the chimera path, each body region is contested between the parents and goes to the version with higher fitness in that body and habitat; the winner is decided per pair, with no fixed ranking of species
applies_to: [all_traits, pipeline]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/s41586-021-03273-0

### RC-R10-03
rule: Donor parts fill the host's empty niches first (structures the host lacks); replacing a working host part requires a clear fitness gain
applies_to: [all_traits, pipeline]
strength: soft
status: VERIFIED
source: https://journals.biologists.com/dev/article/148/12/dev195792/269139/The-road-to-generating-transplantable-organs-from

### RC-R10-04
rule: A donor face, jaw or beak skeleton is autonomous: it keeps the donor's own shape and proportions, and the host tissue at the seam bends toward it
applies_to: [head, face, skull]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6108449

### RC-R10-05
rule: Internal organs and overall body size follow the host, even when built from donor cells
applies_to: [size, body]
strength: soft
status: VERIFIED
source: https://www.ims.u-tokyo.ac.jp/imsut/content/900004612.pdf

### RC-R10-06
rule: A layer architecture is allowed: the donor supplies the surface layer (skin, scales or feathers) over the host body or a whole body zone; in animals it is labeled speculative, because layer chimeras are documented in plants
applies_to: [coat_texture, coat_color, body]
strength: soft
status: VERIFIED
source: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4223383/

### RC-R10-07
rule: A borrowed donor part counts as working only if the host body supports it; otherwise it is shown but labeled non-working
applies_to: [all_traits, pipeline]
strength: soft
status: VERIFIED
source: https://ria.ua.pt/bitstream/10773/40784/1/2023%20Morelli%20et%20al_ORE.pdf

### RC-R10-08
rule: Creatures with three or more parents are built as a family tree of pairwise steps, and the result is a mosaic in which each parent shows in different features
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://pure.psu.edu/en/publications/a-wood-warbler-produced-through-both-interspecific-and-intergener/

### RC-R10-09
rule: Choose the fusion operator by the kind of pair; no single blending method suits all pairs
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://arxiv.org/pdf/2506.23630

### RC-R10-10
rule: Cap parents at three in realistic and speculative modes, and at four in mythic mode with a warning, because image models degrade with more concepts
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://openaccess.thecvf.com/content/CVPR2024/papers/Kwon_Concept_Weaver_Enabling_Multi-Concept_Fusion_in_Text-to-Image_Models_CVPR_2024_paper.pdf

### RC-R10-11
rule: The genome carries both parents' versions for each region (one expressed, one carried); in evolve, an offspring may express a carried version, the way a hidden recessive can reappear in a later generation
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://shipseducation.net/updates/mendel2.htm

### RC-R10-12
rule: A donor's protective covering (shell, carapace, scales, exoskeleton) is applied as a covering that replaces the host's covering in its zone and grows in the skin, not as pieces added on top; the host's covering stops at its edge, and the belly and legs keep the host's covering unless planned otherwise
applies_to: [coat_texture, body]
strength: soft
status: VERIFIED
source: https://www.nationalgeographic.com/animals/article/animals-armor-bioinspiration

### RC-R10-13
rule: A beetle donor's shield is its elytra: hardened forewings forming one close-fitting cover over the back; on a vertebrate host it maps to one domed dorsal shield from shoulders to hips, in two halves meeting at a midline seam, never as scattered plates
applies_to: [body, coat_texture]
strength: soft
status: VERIFIED
source: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9975656/
superseded_by: RC-R10-15 (S3b: elytra are wing-derived, so on a host without forewings only the cuticle material transfers, never the elytra shape)

### RC-R10-14
rule: Every donor part has an anatomical anchor on the host chosen by function (a horn anchors on the nasal or frontal bone as in a rhinoceros; a dorsal shield anchors along the spine); the plan records the anchor and the prompt states it
applies_to: [all_traits]
strength: soft
status: UNVERIFIED
source: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9975656/

### RC-R10-15
rule: Transfer traits, not shapes. Classify each donor feature as (a) material or covering, which grows on the host and conforms to the host's body shape; (b) homologous structure, placed where the host has the matching structure, keeping its form but fitted to host scale; (c) non-homologous structure, never transferred as a shape, only its material or function
applies_to: [all_traits, coat_texture, body]
strength: soft
status: VERIFIED
source: https://evolution.berkeley.edu/evolution-101/the-history-of-life-looking-at-the-patterns/homologies-and-analogies/

### RC-R10-16
rule: An exoskeleton covering is a whole-body system: hardened plates on each segment and limb section, joined by flexible cuticle at the joints; on a vertebrate host it covers body and limbs with flexible bands at joints, unless a stated functional reason limits it
applies_to: [coat_texture, body, limbs]
strength: soft
status: VERIFIED
source: https://genent.cals.ncsu.edu/bug-bytes/arthropods/
