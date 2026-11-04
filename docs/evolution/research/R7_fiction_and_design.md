# R7. Fiction and design: what myth, manga, film and game art teach about fused creatures

Doc: docs/evolution/research/R7_fiction_and_design.md
Status: research, first pass (Oct 31, 2026)
Feeds: ALGORITHM.md (mythic mode, framing text, silhouette design step)
Related: R5 (host frame, donor regions), R6 (readability), R3 (six limbs)

## Why this doc exists

The science docs say what is plausible. This doc looks at people who have designed fused and invented creatures for a living or for a story: speculative zoology authors, myth makers, manga artists, film creature teams and game artists. Their methods are design evidence, not biology. Fan wikis are used here only to describe what a fictional work contains, and they are labeled as design sources.

Copyright note: this doc describes ideas and design methods only. It reproduces no text or artwork, and the engine must never render a named franchise character. Hackathon rules also disqualify assets the team has no rights to.

Tag vocabulary for rule cards: size, body, head, face, ears, mane, tail, limbs, feet, coat_pattern, coat_color, coat_texture, skull, behavior, all_traits, pipeline.

## Key takeaways for the engine

1. Speculative zoology's core idea fits our pitch: use made-up animals to illustrate real processes. Each creature should say which real process it illustrates.
2. Myth chimeras like the griffin are part swaps. That look is legitimate as an explicitly labeled mythic mode, never as biology.
3. Manga chimeras follow a "base body plus donated, useful traits" pattern, the same shape as the R5 host and donor rule.
4. Professional character design starts from a distinctive silhouette, and interior detail echoes it. This matches R6 and gives the critic a concrete test.
5. Avatar's creature team made six limbs plausible inside their world by giving almost all of Pandora's fauna the same body plan. Six limbs need a world rule, not a one-off graft.

## 1. Speculative zoology: fictional examples of real processes

Dougal Dixon's After Man (1981) is widely treated as the start of modern speculative zoology. In an interview and in commentary by palaeontologist Darren Naish on Scientific American's Tetrapod Zoology blog, Dixon describes the purpose of the genre as using invented examples to show factual processes [S1].

Engine mapping: this is the clearest public framing for Chimera Lab's impact story (worldbuilding and learning). Every creature card should name the real processes behind its look, for example "blended size as in hybrids", "patchwork coat as in lab chimeras", "larger ears for a hot habitat (Allen's rule)". The text then teaches something true about each made-up animal.

## 2. Myth: the griffin as a part swap

The griffin joins a bird's head and wings to a big cat's body: a pure part swap on a six-limbed frame. Stanford historian of science Adrienne Mayor argued that the gold-guarding griffin legend grew from ancient encounters with Protoceratops skeletons in Central Asia [S2]. A 2024 study reported by Everything Dinosaur challenged that link, arguing the fossil resembles a griffin only in being a four-legged animal with a beak [S3].

Engine mapping: myth-style part swaps are culturally recognizable and fun, so they belong in an explicit mythic mode. They are labeled as myth, run the R3 six-limb label, and never claim a fossil origin as fact.

## 3. Manga: base body plus donated, useful traits

In Hunter x Hunter, the Chimera Ant queen passes the characteristics of whatever she eats on to her offspring, a process the series calls phagogenesis [S4]. In Fullmetal Alchemist, chimeras are made by alchemically fusing living things; several human chimeras keep a human body and gain animal traits, such as Dolcetto, fused with a dog [S5].

Engine mapping:
- The recurring design move is one consistent base body that carries selected traits from other species, and each donated trait does something. That matches R5 (host frame, donor regions) and R6 (the base owns the identity).
- Human and animal fusions are out of scope for Chimera Lab; R5 already excludes primate chimeras.

## 4. Game art: silhouette first

Valve's paper on Team Fortress 2 describes designing the nine character classes to have clearly different silhouettes so players can identify them quickly in any lighting, and validating designs by checking they still read with no interior detail. Interior details such as clothing folds were drawn to echo the silhouette shapes [S6]. Valve's GDC 2008 talk lists the character silhouette as the first step of character creation and the building block of the design [S7].

Engine mapping: before rendering, the plan should state the intended silhouette (host frame plus any donor parts that change the outline, such as wings, a trunk or tentacles). After rendering, a silhouette-only check (for example a segmentation mask) confirms it matches. Donor patterns and textures inside the outline should follow the outline's flow rather than cut across it.

## 5. Film: a world rule for body plans

A CNRS news feature on the Avatar films notes that most of Pandora's fauna have six limbs, while the humanoid Na'vi have four [S8]. Interviews with the film's creature designers describe working from a long design document by James Cameron and exploring a shared set of parameters across many creatures, including six legs and body markings, so the designs worked as an ecosystem [S9].

Engine mapping: six limbs read as believable when they are a consistent world rule (an alien lineage), and as a glued-on extra when only one creature has them. In mythic or speculative modes, a six-limbed design should say so in its label (R3) and keep the extra pair coherent with the body, not floating.

## 6. How the engine should use resemblances

The project data already lists mythology creatures that a fusion may resemble. From this doc:
- Show resemblances as "resembles X (culture)", always tagged unverified, as the U1 interface already does.
- Use franchise works only as design lessons, never as render targets or names.

## What this doc does not settle

- Taste. These sources describe methods; whether users prefer realistic or mythic results needs a test.
- Non-Western creature design traditions beyond the mythology list in the project data.
- Licensing of any specific reference image. The engine uses none.

## Sources

Type labels: UNI = university or university-affiliated, PR = peer-reviewed, IND = industry paper or talk, NEWS = journalism or science blog, ORG = research organization news, FAN = fan wiki, design source only.

- [S1] Naish D. Speculative zoology at Tet Zoo, the story so far. Scientific American Tetrapod Zoology blog. NEWS (expert science blog). https://www.scientificamerican.com/blog/tetrapod-zoology/speculative-zoology-at-tet-zoo-the-story-so-far/
- [S2] Stanford University Department of Classics. The First Fossil Hunters: Dinosaurs, Mammoths, and Myth in Greek and Roman Times (Mayor A, Princeton University Press). UNI. https://classics.stanford.edu/publications/first-fossil-hunters-dinosaurs-mammoths-and-myth-greek-and-roman-times
- [S3] Everything Dinosaur blog (June 2024). New study suggests Protoceratops fossils did not inspire the griffin legend. NEWS. https://blog.everythingdinosaur.com/blog/_archives/2024/06/21
- [S4] Hunterpedia (Hunter x Hunter fan wiki). Chapter 187. FAN, design source only. https://hunterxhunter.fandom.com/wiki/Chapter_187
- [S5] Fullmetal Alchemist Wiki (fan wiki). Dolcetto. FAN, design source only. https://fma.fandom.com/wiki/Dolcetto
- [S6] Mitchell J, Francke M, Eng D (2007). Illustrative rendering in Team Fortress 2. NPAR 2007. Copy on a Princeton course site. IND, PR. https://www.cs.princeton.edu/courses/archive/fall07/cos597B/papers/mitchell-team-fortress.pdf
- [S7] Mitchell J (2008). The illustrative world of Team Fortress 2: stylization with a purpose. GDC 2008 talk slides, Valve. IND. https://cdn.steamstatic.com/apps/valve/2008/GDC2008_StylizationWithAPurpose_TF2.pdf
- [S8] CNRS News. Feature on the science of the Avatar films (2025). ORG. https://news.cnrs.fr/node/2233
- [S9] Gizmodo. 27 Avatar questions answered by the movie's designers. NEWS. https://gizmodo.com/27-avatar-questions-answered-by-the-movies-designers-5464478

## Rule cards

### RC-R7-01
rule: Frame every creature as a fictional example of real processes; its card names the processes behind its look (hybrid blend, chimera patchwork, habitat rules)
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://www.scientificamerican.com/blog/tetrapod-zoology/speculative-zoology-at-tet-zoo-the-story-so-far/

### RC-R7-02
rule: Myth-style part swaps (griffin-like layouts) belong only to an explicit mythic mode, labeled as myth and never presented as biology
applies_to: [pipeline, body, limbs]
strength: soft
status: VERIFIED
source: https://classics.stanford.edu/publications/first-fossil-hunters-dinosaurs-mammoths-and-myth-greek-and-roman-times

### RC-R7-03
rule: Never state that a myth creature came from a specific fossil as fact; the Protoceratops and griffin link is contested
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://blog.everythingdinosaur.com/blog/_archives/2024/06/21

### RC-R7-04
rule: Design pattern from manga chimeras: one consistent base body carries selected traits from the other species, and each donated trait has a visible use
applies_to: [body, all_traits]
strength: soft
status: VERIFIED
source: https://hunterxhunter.fandom.com/wiki/Chapter_187

### RC-R7-05
rule: Human and animal fusions are out of scope; parents are animals only
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://fma.fandom.com/wiki/Dolcetto

### RC-R7-06
rule: State the intended silhouette in the plan and validate the render with a silhouette-only check; the creature must read with no interior detail
applies_to: [body, pipeline]
strength: soft
status: VERIFIED
source: https://www.cs.princeton.edu/courses/archive/fall07/cos597B/papers/mitchell-team-fortress.pdf

### RC-R7-07
rule: Interior detail (pattern lines, texture flow) should echo the silhouette's shapes rather than cut across them
applies_to: [coat_pattern, coat_texture]
strength: soft
status: VERIFIED
source: https://www.cs.princeton.edu/courses/archive/fall07/cos597B/papers/mitchell-team-fortress.pdf

### RC-R7-08
rule: Six limbs read as believable only as a consistent world rule, as with Pandora's mostly six-limbed fauna; in our engine a six-limbed design stays in mythic or speculative mode with its label
applies_to: [limbs, pipeline]
strength: soft
status: VERIFIED
source: https://news.cnrs.fr/node/2233

### RC-R7-09
rule: Write the biology rulebook before designing creatures, and treat design parameters as a shared palette across many creatures, as the Avatar team did
applies_to: [pipeline]
strength: soft
status: VERIFIED
source: https://gizmodo.com/27-avatar-questions-answered-by-the-movies-designers-5464478

### RC-R7-10
rule: Show myth and fiction resemblances as "resembles X (culture or work)", tagged unverified; never render or name-match a franchise character as an output
applies_to: [pipeline]
strength: soft
status: UNVERIFIED
source: https://classics.stanford.edu/publications/first-fossil-hunters-dinosaurs-mammoths-and-myth-greek-and-roman-times
