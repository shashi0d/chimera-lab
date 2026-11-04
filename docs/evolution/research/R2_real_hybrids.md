# R2. Real hybrids: what crosses between species actually look like

Doc: docs/evolution/research/R2_real_hybrids.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (blend operators, direction handling, known-pair overrides)

## Why this doc exists

Our live runs swapped whole parts between parents and kept every signature trait at full strength (full lion mane plus bold tiger stripes everywhere). Real hybrids do not look like that. This doc collects documented hybrids between real species and pulls out the patterns the evolution engine should copy.

Scope: true hybrids only, meaning offspring of two species where every cell carries DNA from both parents. Chimeras (one body built from two separate cell lines) are a different process and are covered in R5.

Tag vocabulary used in the rule cards (shared by all R docs): size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Real hybrids happen mainly between recent, closely related species; about 10 percent of animal species are known to hybridize with at least one other species [S16]. For distant pairs there is no hybrid precedent, so the engine must switch to the chimera path (R5) and label the result as speculative.
2. The default outcome is in between, not either parent. Most traits of a first-generation hybrid land between the parents, and extreme traits are the minority, especially in wild animal crosses.
3. Hybrids are often mosaics by body region. The mule takes its frame from one parent and its head, ears and legs from the other. This is region-level mixing, not a whole-animal blend and not a full part swap.
4. Signature patterns show up diluted. Zebra stripes in zebroids and tiger stripes in ligers appear, but reduced in strength or extent.
5. Which parent is the father and which is the mother can matter, sometimes a lot (liger versus tigon). The engine must keep parent order and treat it as biological, not cosmetic.
6. Size can overshoot both parents in specific crosses. This is rare, has a known cause, and should only fire when a documented case says so.
7. Behavior can follow one parent even when the body is mixed.

## Case studies

### 1. Mule and hinny (horse x donkey)

Parentage. A mule comes from a male donkey and a female horse. A hinny comes from a male horse and a female donkey. University of New Hampshire Extension teaching material lists the visual differences between the two parent species: the donkey has longer ears, a tufted tail, a coarser more upright mane, and lacks chestnuts on the hind legs [S5].

What a mule looks like. An equine extension veterinarian at the University of Illinois College of Veterinary Medicine describes the mule as drawing different traits from each parent. From the horse it gets height, the length and shape of the neck, and the length of the coat and tail bone. From the donkey it gets a short thick head, long ears, a short mane, coarse coat texture, thin limbs and small hooves. The tail is a mix along its length: short donkey-like hair near the base and longer hair further down, though still shorter than a horse tail [S4].

Mule versus hinny. The same source says hinnies tend to be smaller and more horse-like, but that the two can really only be told apart by knowing the parents, not by looking [S4]. The Donkey Sanctuary describes hinny ears as smaller than a donkey's and shaped like a horse's, with a mane and tail that usually resemble a horse's [S6].

Engine lesson. This is the clearest documented example of region-level mosaic inheritance: frame and proportions from one parent, extremities (head, ears, limbs, hooves) from the other, and at least one part (the tail) blended along its length. It also shows that the reciprocal cross is close but not identical.

Our earlier live run drew a textbook mule (long ears, short upright mane, horse body). It was scientifically right, which means the mule is the reference answer for horse plus donkey.

### 2. Liger and tigon (lion x tiger)

Parentage. A liger has a lion father and a tiger mother. A tigon has a tiger father and a lion mother.

Size. Ligers are described as the largest living cats, bigger than either parent, while tigons are roughly parent-sized. A geneticist explainer from The Tech Interactive (run with Stanford geneticists) gives the leading explanation: genomic imprinting, where some growth genes are switched on or off depending on which parent they came from. The idea is that lions and tigers evolved different growth "settings", so the lion father's growth-promoting signal is not held back by a tiger mother, while in the reverse cross the lioness's growth-limiting signal does hold it back [S2]. The explainer also notes that few genetic studies exist in big cats, so the cat-specific mechanism is inferred from rodent work.

The rodent evidence. Princeton research on two deer mouse species (Peromyscus) showed that crosses between them give parent-of-origin growth problems: one direction gives undersized young, the other gives overgrown young. They found imprinting works normally in each parent species but breaks down in the hybrids, and that the most overgrown hybrids had the most disrupted imprinting [S1], [S3].

Coat and mane. General reference sources agree that a liger shows faint tiger-like stripes on a tawny, lion-like coat, and that a male liger may grow a mane that is smaller than a lion's [S13]. These details come from encyclopedic sources, not from a zoo or peer-reviewed description, so they are marked UNVERIFIED in the rule cards.

Engine lesson. The parent order in the cache key is biologically meaningful. Size can overshoot both parents only for a documented direction-specific case, never as a general rule. Our live liger render (full mane plus bold stripes everywhere) is the opposite of the documented look: both signature traits at 100 percent.

### 3. Zebroids (zebra x horse or donkey)

What is documented. The Darwin Museum in Moscow describes zebra x horse hybrids bred in early 20th century experiments: the young looked like their mother but carried stripes on the legs, neck and body from their father [S12]. Charles Darwin reported a donkey-zebra-horse hybrid at London Zoo that had faint stripes on its shoulders, flanks and legs when young and very few as an adult (reported second hand via IFLScience) [S14].

Commonly repeated but weaker claims. Many popular sources say zebroid stripes are boldest on the legs and fade over the body, and that stripes do not appear on white patches when the horse parent is a pinto or similar [S14]. I did not find a zoo or peer-reviewed source for either claim in this pass, so both are UNVERIFIED.

Engine lesson. The non-zebra parent supplies the body shape and base color; the zebra supplies a pattern that is present but partial. A pattern donor does not need to own the body.

### 4. Polar bear x grizzly bear (grolar or pizzly)

What is documented. A peer-reviewed study in the journal Arctic used genetic parentage analysis to identify four first-generation hybrids and four backcrosses in the Canadian Arctic, all traced to one female polar bear that mated with two grizzly males [S8]. So wild hybrids between these two species are confirmed.

Appearance. A 2009 study of two hybrid cubs at Osnabrueck Zoo (Preuss and colleagues, Der Zoologische Garten 78: 204 to 220) is widely summarized: a long polar-bear-like neck and visible tail, a small grizzly-like shoulder hump, foot soles partly covered in hair (in between the furred polar sole and the bare grizzly sole), and hair that is hollow but less so than polar bear hair [S10]. A Nature commentary citing that study reports the zoo hybrids showed seal-hunting style behavior without the strong swimming of polar bears [S9]. I read only these secondary summaries, not the zoo paper itself, so the per-feature claims are UNVERIFIED.

Engine lesson. One animal can carry traits that pick one parent (tail, hump), traits that blend (sole fur, hair hollowness), and behavior that leans to one parent while performance does not. Mixed modes inside one creature are normal.

### 5. Eastern coyote (coyote x wolf ancestry)

What is documented. Research from the New York State Museum, published in Biology Letters, used museum skulls and genetics to show that northeastern coyotes carry wolf ancestry from hybridization in Canada. The hybrid-origin coyotes are larger, with wider skulls better suited to hunting deer, and they expanded their range quickly [S11].

Engine lesson. A hybrid trait can be functionally coherent with a new lifestyle: bigger skull goes with bigger prey. This is a real-world precedent for tying inherited traits to ecology, which R4 develops further.

### 6. Cama (dromedary camel x guanaco or llama)

What is documented. A peer-reviewed study in Proceedings of the Royal Society B reports the first camel x guanaco hybrid, produced by artificial insemination because the parents differ so much in size. Its appearance was intermediate between camel and guanaco, and DNA fingerprinting confirmed the parentage [S7].

Popular reporting adds that the first cama had short camel-like ears, a long camel-like tail, llama-like split hooves and no hump [S15]. This came from news reports, so it is UNVERIFIED.

Engine lesson. Even quite distant relatives (separated for millions of years, needing lab help to cross) still produce an in-between animal, not a part swap. The hump, the most iconic camel feature, did not carry over in the first animal, which is a reminder that signature features are not guaranteed to transfer.

## Cross-cutting patterns

### Pattern A. In between is the default, extremes are the exception

A review of 171 hybrid studies in Heredity found that extreme ("transgressive") traits, beyond the range of both parents, are common overall. But they were least frequent in crosses between wild, outbred animal species. Across animals, 31 percent of measured traits were transgressive, and in comparisons restricted to wild outcrossing species it was about 23 percent of animal traits. Only about a quarter of animal body-shape traits were transgressive [S3]. The review also notes that extremes mostly show up in later hybrid generations, while first-generation hybrid vigor is a separate effect.

For the engine: a first-generation fusion should place most traits between the parents. A small minority of traits may go beyond both parents, and those should be flagged as unusual.

### Pattern B. Region mosaics are real

Mule (frame from horse, extremities from donkey), grolar (tail from one parent, hump from the other), cama (ears and tail from one, hooves from the other). Real hybrids pick a donor per region surprisingly often, but they do it for a coherent set of regions, and they usually blend at least one feature.

### Pattern C. Signature patterns arrive diluted

Liger stripes faint, zebroid stripes partial, grolar coat mostly pale with brown patches. When a pattern donor does not also own the body, its pattern should be rendered at reduced strength or extent.

### Pattern D. Direction matters

Liger versus tigon and the Peromyscus mice show that swapping which species is the father can change the result. Mule versus hinny shows a smaller but real difference.

### Pattern E. Size is mostly between, sometimes above

Most hybrids are intermediate in size (mule, cama, Osnabrueck bears smaller than polar bears but larger than grizzlies per summaries). Liger overgrowth is a documented, direction-specific exception.

## What this doc does not settle

- Real hybrids exist mainly for close relatives [S16]. Nothing here says what a lion plus octopus "should" look like. That is R3, R5 and R7 territory.
- Most hybrid photos and descriptions come from captive animals. Captivity affects size and condition.
- Several appearance details (liger mane rate, zebroid leg stripes, cama ears) still need a zoo, vet or peer-reviewed source. They are kept as soft, UNVERIFIED cards.

## Sources

Type labels: PR = peer-reviewed, UNI = university or university-affiliated, ZOO = zoo, museum or sanctuary, VET = veterinary, NEWS = journalism, ENC = encyclopedia.

- [S1] Vrana P, Guan X, Ingram R, Tilghman S (1998). Genomic imprinting is disrupted in interspecific Peromyscus hybrids. Nature Genetics 20: 362 to 365. Listing at Princeton Lewis-Sigler Institute. PR, UNI. https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids
- [S2] The Tech Interactive, Ask a Geneticist: Why are ligers so big? (2018). UNI. https://www.thetech.org/ask-a-geneticist/why-are-ligers-so-big
- [S3] Rieseberg LH, Archer MA, Wayne RK (1999). Transgressive segregation, adaptation and speciation. Heredity 83: 363 to 372. PR. https://www.nature.com/articles/6886170
- [S4] Fuess TA, University of Illinois College of Veterinary Medicine. What is a mule made of? (republished on Engormix). VET, UNI. https://en.engormix.com/equines/horse-genetics/what-mule-made_n11953/
- [S5] University of New Hampshire Extension. Equine teaching resource: horse, donkey, mule and hinny. UNI. https://extension.unh.edu/sites/default/files/migrated_unmanaged_files/Resource004972_Rep7077.pdf
- [S6] The Donkey Sanctuary. Mules and hinnies. ZOO (sanctuary). https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies
- [S7] Skidmore JA, Billah M, Binns M, Short RV, Allen WR (1999). Hybridizing Old and New World camelids: Camelus dromedarius x Lama guanicoe. Proceedings of the Royal Society B 266: 649 to 656. PR. https://pmc.ncbi.nlm.nih.gov/articles/PMC1689826
- [S8] Pongracz JD, Paetkau D, Branigan M, Richardson E (2017). Recent hybridization between a polar bear and grizzly bears in the Canadian Arctic. Arctic 70(2): 151 to 160. PR. https://journalhosting.ucalgary.ca/index.php/arctic/article/view/67681
- [S9] Kelly B, Whiteley A, Tallmon D (2010). The Arctic melting pot. Nature 468: 891. Commentary citing Preuss et al. 2009. PR (commentary). https://www.nature.com/articles/468891a
- [S10] Live Science. Real or fake? 8 bizarre hybrid animals (summary of Preuss et al. 2009). NEWS. https://www.livescience.com/12047-real-fake-8-bizarre-hybrid-animals.html
- [S11] New York State Museum. Coyote evolution study, Kays, Curtis and Kirchman (2010), Biology Letters 6: 89 to 93. ZOO (museum), PR summary. https://nysm.nysed.gov/node/8054
- [S12] State Darwin Museum, Moscow. Zebroid: a horse or a zebra? ZOO (museum). https://darwinmuseum.ru/pages/a-zebroid-a-horse-or-a-zebra
- [S13] New World Encyclopedia. Liger. ENC. https://www.newworldencyclopedia.org/entry/Liger
- [S14] IFLScience. Zebroids, zeedonks, zorses, zonies: welcome to the world of zebra hybrids. NEWS. https://www.iflscience.com/zebroids-zeedonks-zorses-zonies-welcome-to-the-world-of-zebra-hybrids-80202
- [S15] Farm Show. Rama the cama (AP report). NEWS. https://www.farmshow.com/a_article.php?aid=11569
- [S16] Mallet J (2007). Hybrid speciation. Nature 446: 279 to 283. Author copy at University College London. PR, UNI. https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf

## Rule cards

### RC-R2-01
rule: Parent order is biological. Store fusions as (sire, dam) and never treat A x B as identical to B x A, because reciprocal crosses can differ in size and appearance
applies_to: [pipeline, size]
strength: hard
status: VERIFIED
source: https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids

### RC-R2-02
rule: For a first-generation fusion, place most measurable traits (size, limb length, skull proportions) between the two parents; allow only a minority of traits to exceed both parents, and flag any that do as unusual
applies_to: [size, limbs, skull, body]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/6886170

### RC-R2-03
rule: Donkey sire x horse dam must render as the documented mule: horse height, neck shape and body; donkey short thick head, long ears, short mane, coarse coat, thin limbs and small hooves; tail short-haired at the base and longer below
applies_to: [body, head, ears, mane, limbs, feet, tail, coat_texture]
strength: hard
status: VERIFIED
source: https://en.engormix.com/equines/horse-genetics/what-mule-made_n11953/

### RC-R2-04
rule: Horse sire x donkey dam (hinny) renders close to the mule but somewhat smaller and more horse-like, with shorter horse-shaped ears and a fuller mane and tail; never claim the two can be told apart by looks alone
applies_to: [ears, mane, tail, size]
strength: soft
status: VERIFIED
source: https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies

### RC-R2-05
rule: Size may exceed both parents only when a documented direction-specific case exists (lion sire x tiger dam); the reverse cross stays near parent size
applies_to: [size]
strength: soft
status: VERIFIED
source: https://www.thetech.org/ask-a-geneticist/why-are-ligers-so-big

### RC-R2-06
rule: Region mosaics are allowed and realistic: one parent can supply the frame while the other supplies head, ears and limbs, but the donor choice should cover a coherent group of regions rather than random single parts
applies_to: [body, head, ears, limbs]
strength: soft
status: VERIFIED
source: https://en.engormix.com/equines/horse-genetics/what-mule-made_n11953/

### RC-R2-07
rule: When the pattern donor is not the body donor, render its pattern partial and reduced (zebroid: base body and color from the non-zebra parent, stripes on parts of legs, neck and body)
applies_to: [coat_pattern, coat_color]
strength: soft
status: VERIFIED
source: https://darwinmuseum.ru/pages/a-zebroid-a-horse-or-a-zebra

### RC-R2-08
rule: Lion x tiger renders as a tawny lion-like coat with faint tiger stripes; a male may have a reduced mane or none; never full mane plus full-strength stripes
applies_to: [coat_pattern, coat_color, mane]
strength: soft
status: UNVERIFIED
source: https://www.newworldencyclopedia.org/entry/Liger

### RC-R2-09
rule: Zebroid stripes are strongest on the legs and do not appear on white patches of a patterned horse parent
applies_to: [coat_pattern, limbs]
strength: soft
status: UNVERIFIED
source: https://www.iflscience.com/zebroids-zeedonks-zorses-zonies-welcome-to-the-world-of-zebra-hybrids-80202

### RC-R2-10
rule: Polar bear x grizzly renders with a long polar-like neck and visible tail, a small grizzly-like shoulder hump, partly furred soles, and a mostly pale coat; behavior leans polar bear
applies_to: [body, tail, feet, coat_color, behavior]
strength: soft
status: UNVERIFIED
source: https://www.livescience.com/12047-real-fake-8-bizarre-hybrid-animals.html

### RC-R2-11
rule: Wild polar bear x grizzly hybrids are genetically confirmed, so the pair qualifies for the real-hybrid path
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://journalhosting.ucalgary.ca/index.php/arctic/article/view/67681

### RC-R2-12
rule: Inherited traits can fit a new lifestyle: when a fusion takes the larger parent's size, it may also take a larger, wider skull suited to larger prey
applies_to: [skull, size]
strength: soft
status: VERIFIED
source: https://nysm.nysed.gov/node/8054

### RC-R2-13
rule: Even distantly related compatible parents (camel x guanaco) give an intermediate-looking animal, not a part swap; a signature feature such as a hump is not guaranteed to transfer
applies_to: [body, all_traits]
strength: soft
status: VERIFIED
source: https://pmc.ncbi.nlm.nih.gov/articles/PMC1689826

### RC-R2-14
rule: Camel x llama renders with short camel-like ears, a long camel-like tail, split llama-like hooves and no hump
applies_to: [ears, tail, feet, body]
strength: soft
status: UNVERIFIED
source: https://www.farmshow.com/a_article.php?aid=11569

### RC-R2-15
rule: Behavior can follow one parent even when the body is mixed, and a behavior can be present without the physical performance behind it (hybrid bears with seal-hunting style behavior but weaker swimming)
applies_to: [behavior]
strength: soft
status: VERIFIED
source: https://www.nature.com/articles/468891a

### RC-R2-16
rule: Use the real-hybrid path only for pairs with a documented hybrid or a close relationship (same genus); all other pairs go to the chimera path and are labeled speculative
applies_to: [pipeline]
strength: hard
status: VERIFIED
source: https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf
