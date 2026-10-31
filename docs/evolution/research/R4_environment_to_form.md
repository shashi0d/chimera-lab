# R4. Environment to form: how habitat and lifestyle show up in the body

Doc: docs/evolution/research/R4_environment_to_form.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (habitat step, visible ecology traits)
Related: R2 (coyote skull and prey), R3 (size limits), R6 (what viewers notice)

## Why this doc exists

Our live report found that the plans talked about wetlands, dusk activity and fish diets, but none of it showed in the images: no webbing, no larger eyes, nothing aquatic. This doc collects the well-studied links between environment and body form, so the engine can turn a chosen habitat into visible traits.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Coat pattern tracks habitat more than ancestry. In cats, patterned coats go with closed, forested habitats and tree climbing, plain coats with open ones, and pattern changes over short evolutionary time.
2. Climate shapes size and extremities. Colder places favor larger bodies (Bergmann's rule) and warmer places favor larger ears, tails, beaks and limbs (Allen's rule). Both are tendencies, not laws.
3. Dark-back, light-belly shading is the default for most animals, and it is stronger in open, brightly lit habitats.
4. Fast open-water swimmers from unrelated groups converge on the same torpedo body and crescent tail.
5. Eye shape tracks activity time in birds and reptiles (night-active species have relatively larger corneas), but much less in mammals.
6. A hybrid's success in nature is tied to finding a niche different from its parents. That gives the engine permission to place a fusion in a new, bridging habitat, as long as the traits match it.

## 1. Habitat sets coat pattern

Allen and colleagues analysed the flank patterns of many cat species against their ecology, controlling for shared ancestry. Patterning, and pattern complexity and irregularity, were related to habitat, tree climbing and night activity. Pattern carried little signal of ancestry, which the authors read as camouflage adapting to ecology over relatively short timescales [S1]. Summaries of the results describe patterned cats in closed habitats such as forest, and plain cats in open habitats such as grassland, desert and mountains [S1].

Engine mapping: once the fusion's habitat is chosen, the coat pattern should fit it. A fusion living in open grassland leans plain; a forest or tree-climbing fusion leans spotted or irregular. Because pattern follows ecology more than ancestry, it is a legitimate place for the habitat to override both parents. R1 and R2 still govern how a parent's pattern is inherited; this rule adjusts strength and complexity.

## 2. Climate sets size and extremities

Bergmann's rule. Larger body size in colder environments. A review of statistically tested studies found about 72 percent of bird species and 65 percent of mammal species follow it [S2], and a separate analysis of mammals found broad support for the trend, while not supporting heat conservation as the explanation [S3].

Allen's rule. Larger appendages in warmer climates to dump heat. A 2021 review in Trends in Ecology and Evolution describes beaks and ears as heat-shedding organs and finds widespread evidence of appendages growing as climates warm [S4].

Engine mapping: for a cold habitat, nudge body size up within the blended range and shorten ears, tail and limbs; for a hot habitat, enlarge ears and other extremities. These are soft nudges on top of the R1 blend, never overrides of R3 size limits.

## 3. Countershading

Countershading (darker back, lighter belly) is perhaps the most common coloration pattern in animals. A study of 114 ruminant species found that stronger countershading went with open lighting environments, living nearer the equator and smaller body size [S5]. A review of the topic notes that the concealment function has long been assumed and only recently tested directly, so the "why" is still argued [S6].

Engine mapping: default to a dark-back, light-belly gradient for terrestrial and aquatic fusions, stronger in open, sunny habitats. Present it as a common pattern, not as proven camouflage.

## 4. Water shapes the body

Fast open-water swimmers from unrelated groups (tuna, mako sharks, dolphins and the extinct ichthyosaurs) independently evolved a torpedo-shaped (fusiform) body, which the Smithsonian's ocean portal presents as a textbook case of convergent evolution [S7]. A study of ichthyosaur body plans describes their shift from long serpentine forms to stocky, fish-like bodies converging with sharks and dolphins [S8], and an exceptional mosasaur fossil shows a streamlined body and crescent tail fin evolving in yet another reptile group [S9].

Engine mapping: if a fusion is assigned an open-water, fast-swimming lifestyle, streamline the body and give it a crescent or fluked tail. A land frame dropped into water without these changes should be described as a shoreline or wading animal, not a pelagic swimmer.

## 5. Light level shapes the eyes

Across vertebrates, night-active species tend to have larger corneas relative to eye length (more light gathering), while day-active species have relatively longer eyes (sharper images). This holds well in birds and lizards, but a study of 266 mammal species found most mammals have night-type eye shapes regardless of activity, a legacy of their nocturnal ancestry [S10].

Engine mapping: for a nocturnal or dusk-active fusion with a bird or reptile head, enlarge the eyes and pupils visibly. For a mammal head the change should be smaller.

## 6. Diet and prey shape the skull

R2 documents that northeastern coyotes with wolf ancestry are larger, with wider skulls better suited to hunting deer [S11]. The general pattern, that skull robustness follows prey size, is applied here as a soft rule.

## 7. A fusion may live somewhere new

The Heredity review of hybrid traits notes that niche separation from the parent species is considered the single most important factor in a hybrid lineage establishing itself [S12]. For the engine this means a fusion does not have to live where either parent lives. It can occupy a bridging habitat (a wetland between a forest parent and a river parent), as long as its visible traits match that habitat.

## 8. Order of the habitat step

1. Choose the habitat: shared by both parents, or a bridging one, or the user's choice.
2. Apply plastic, habitat-linked traits: pattern strength and complexity, countershading, extremity size, eye size.
3. Leave the body plan to R3. Habitat does not add limbs or change body-plan class.
4. Make at least one habitat trait visible in the image, so the ecology is in the creature, not only in the text.

## What this doc does not settle

- Gloger's rule (darker coloration in warm, humid places) came up only in secondary coverage; it is not used here.
- Habitat rules are statistical tendencies across species. They predict direction, not exact amounts.
- Feet and webbing for semi-aquatic life need their own sources in a later pass.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, ZOO = museum.

- [S1] Allen WL, Cuthill IC, Scott-Samuel NE, Baddeley R (2011). Why the leopard got its spots: relating pattern development to ecology in felids. Proceedings of the Royal Society B 278: 1373 to 1380. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134
- [S2] Meiri S, Dayan T (2003). On the validity of Bergmann's rule. Journal of Biogeography 30: 331 to 351. Tel Aviv University. PR, UNI. https://typeset.io/pdf/on-the-validity-of-bergmann-s-rule-sf29n9xsn5.pdf
- [S3] Ashton KG, Tracy MC, de Queiroz A (2000). Is Bergmann's rule valid for mammals? The American Naturalist 156: 390 to 415. PubMed. PR. https://pubmed.ncbi.nlm.nih.gov/29592141/
- [S4] Ryding S, Klaassen M, Tattersall GJ, Gardner JL, Symonds MRE (2021). Shape-shifting: changing animal morphologies as a response to climatic warming. Trends in Ecology and Evolution 36: 1036 to 1048. Australian National University portal. PR, UNI. https://researchportalplus.anu.edu.au/en/publications/shape-shifting-changing-animal-morphologies-as-a-response-to-clim/
- [S5] Allen WL, Baddeley R, Cuthill IC, Scott-Samuel NE (2012). A quantitative test of the predicted relationship between countershading and lighting environment. The American Naturalist. Dryad data record. PR. https://datadryad.org/dataset/doi:10.5061/dryad.4291n
- [S6] Rowland HM (2009). From Abbott Thayer to the present day: what have we learned about the function of countershading? Philosophical Transactions of the Royal Society B. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC2674085
- [S7] Smithsonian Ocean portal. Fish body shapes, including the fusiform shape and its convergent evolution. ZOO (museum). https://ocean.si.edu/node/111022
- [S8] Gutarra S and colleagues (2019). Effects of body plan evolution on the hydrodynamic drag and energy requirements of swimming in ichthyosaurs. Proceedings of the Royal Society B. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC6458325
- [S9] Lindgren J, Caldwell MW, Konishi T, Chiappe LM (2010). Convergent evolution in aquatic tetrapods: insights from an exceptional fossil mosasaur. PLoS ONE 5: e11998. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC2918493
- [S10] Hall MI, Kamilar JM, Kirk EC (2012). Eye shape and the nocturnal bottleneck of mammals. Proceedings of the Royal Society B. PubMed Central. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC3497252
- [S11] New York State Museum. Coyote evolution study, Kays, Curtis and Kirchman (2010), Biology Letters. ZOO (museum), PR summary. https://nysm.nysed.gov/node/8054
- [S12] Rieseberg LH, Archer MA, Wayne RK (1999). Transgressive segregation, adaptation and speciation. Heredity 83: 363 to 372. PR. https://www.nature.com/articles/6886170

## Rule cards

### RC-R4-01
rule: Fit coat pattern to the fusion's habitat: closed, forested or tree-climbing lifestyles lean patterned and irregular; open habitats lean plain
applies_to: [coat_pattern]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134

### RC-R4-02
rule: Habitat may adjust pattern strength and complexity beyond what either parent shows, because coat pattern tracks ecology more than ancestry
applies_to: [coat_pattern, pipeline]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134

### RC-R4-03
rule: In a cold habitat, nudge body size toward the upper end of the blended range (Bergmann's rule), staying within R3 size limits
applies_to: [size]
strength: soft
status: VERIFIED
source: https://pubmed.ncbi.nlm.nih.gov/29592141/

### RC-R4-04
rule: In a hot habitat, enlarge heat-shedding extremities (ears, tail, beak, limbs); in a cold habitat, shorten them (Allen's rule)
applies_to: [ears, tail, limbs, face]
strength: soft
status: VERIFIED
source: https://researchportalplus.anu.edu.au/en/publications/shape-shifting-changing-animal-morphologies-as-a-response-to-clim/

### RC-R4-05
rule: Default to a dark-back, light-belly gradient, stronger in open, sunny habitats and smaller bodies; describe it as a common pattern, not proven camouflage
applies_to: [coat_color]
strength: soft
status: VERIFIED
source: https://datadryad.org/dataset/doi:10.5061/dryad.4291n

### RC-R4-06
rule: A fusion assigned a fast open-water lifestyle gets a streamlined torpedo body and a crescent or fluked tail; otherwise describe it as a shoreline or wading animal
applies_to: [body, tail, behavior]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC6458325

### RC-R4-07
rule: A nocturnal or dusk-active fusion with a bird or reptile head gets visibly larger eyes and pupils; with a mammal head the change is smaller
applies_to: [face, head, behavior]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3497252

### RC-R4-08
rule: Larger prey goes with a larger, wider skull and stronger jaws
applies_to: [skull, head]
strength: soft
status: VERIFIED
source: https://nysm.nysed.gov/node/8054

### RC-R4-09
rule: A fusion may live in a habitat neither parent uses (a bridging niche), because niche separation is what lets hybrid lineages establish; its visible traits must then match that habitat
applies_to: [pipeline, behavior]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/6886170

### RC-R4-10
rule: Habitat adjusts plastic traits (pattern, shading, extremity size, eye size) but never the body-plan class or limb count; those stay with R3
applies_to: [pipeline, body, limbs]
strength: soft
status: UNVERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134

### RC-R4-11
rule: At least one habitat-linked trait must be visible in the image, so the ecology appears in the creature and not only in the text
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134
