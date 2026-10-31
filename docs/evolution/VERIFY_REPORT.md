# Research verification report (Step 0, task E1-offline)

Date: 2026-10-31
Command: `python scripts/verify_research.py docs/evolution/research`
Result (run 4): **exit 0. Gate PASSED: 0 failures, 14 bot-blocked links (403), 0 SSL warnings, 0 timeout warnings.** Work continues to Step 1.

## Run history
- **Run 1** (commit 98d4d8c): failed on 4 links: the Sims PDF (404), the Newcastle wiki (500), `www.ocean.si.edu` (DNS), and `nysm.nysed.gov` (SSL chain; curl returned 200).
- **Source fixes** (the only research-doc edits, all authorized; commit 813f05c):
  - R8 [S1] and RC-R8-01 now use https://www.karlsims.com/papers/siggraph94.pdf
  - R1 [S5] and RC-R1-07 now use https://openoregon.pressbooks.pub/mhccmajorsbio/chapter/epistasis/ (returns 403 to scripts)
  - R4 [S7] now uses https://ocean.si.edu/node/111022 (the fallback was not needed)
- **Runs 2 and 3**: the fixed links passed. `eprints.lancs.ac.uk` timed out at the TLS handshake (curl also timed out after 21s).
- **Verifier rules added**, as decided by the user:
  - A certificate-chain failure that resolves without verification is reported as an `SSL` warning.
  - A timeout is reported as a `TIME` warning only if the URL is listed under "Resolved links" below, meaning it resolved in an earlier recorded run. A timeout on a link that never resolved is still a failure. Both cases were tested against an address that always times out (10.255.255.1): with the URL in the history the result was a warning (exit 0); without it, a failure (exit 1).
- **Run 4**: clean. The Lancaster link resolved again.

## Recheck later
- https://eprints.lancs.ac.uk/id/eprint/50885/ (R6:84, R6:110, R6:124; source of RC-R6-03 and RC-R6-05). It resolved in runs 1 and 4 and timed out in runs 2 and 3, so the server is intermittent. It will be retried once at the end of Step 4; the result goes in E1_OFFLINE.md.

## 403s (likely bot-blocked, check in a browser)
- https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling  (R3_body_plan_limits.md:104, R3_body_plan_limits.md:159, R3_body_plan_limits.md:194)
- https://blog.everythingdinosaur.com/blog/_archives/2024/06/21  (R7_fiction_and_design.md:74, R7_fiction_and_design.md:103)
- https://discovery-pp.ucl.ac.uk/id/eprint/10108322  (R5_real_chimeras.md:88, R5_real_chimeras.md:130)
- https://fma.fandom.com/wiki/Dolcetto  (R7_fiction_and_design.md:76, R7_fiction_and_design.md:117)
- https://hunterxhunter.fandom.com/wiki/Chapter_187  (R7_fiction_and_design.md:75, R7_fiction_and_design.md:110)
- https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids  (R1_inheritance.md:115, R2_real_hybrids.md:115, R2_real_hybrids.md:139)
- https://ocean.si.edu/node/111022  (R4_environment_to_form.md:86)
- https://pubmed.ncbi.nlm.nih.gov/20813264/  (R5_real_chimeras.md:92, R5_real_chimeras.md:109)
- https://pubmed.ncbi.nlm.nih.gov/29592141/  (R4_environment_to_form.md:82, R4_environment_to_form.md:114)
- https://pubmed.ncbi.nlm.nih.gov/8632824/  (R6_perception.md:86, R6_perception.md:131)
- https://rvc-repository.worktribe.com/OutputFile/1397435  (R3_body_plan_limits.md:105, R3_body_plan_limits.md:166)
- https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies  (R2_real_hybrids.md:120, R2_real_hybrids.md:160)
- https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18  (R3_body_plan_limits.md:103, R3_body_plan_limits.md:152)
- https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf  (R1_inheritance.md:117, R1_inheritance.md:217, R2_real_hybrids.md:130, R2_real_hybrids.md:244)

## Resolved links
The verifier reads this section as its history. Each URL below returned a status under 400 in at least one recorded run: run 1 (reconstructed from commit 98d4d8c as every link minus that run's FAIL and 403 lines) or run 4.
- https://agris.fao.org/search/en/records/65dfe6754c5aef494fe67490
- https://arxiv.org/abs/1504.04909
- https://arxiv.org/abs/1811.12231v3
- https://arxiv.org/abs/2302.12170v3
- https://arxiv.org/pdf/1801.08230
- https://arxiv.org/pdf/1806.05865
- https://bio.libretexts.org/Bookshelves/Genetics/Classical_Genetics_(Khan_Academy)/02%3A_Non-Mendelian_inheritance/2.02%3A_Multiple_alleles_incomplete_dominance_and_codominance
- https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/06%3A_Genetic_Analysis_of_Multiple_Genes/6.02%3A_Epistasis_and_Other_Gene_Interactions
- https://catalog.lib.kyushu-u.ac.jp/opac_download_md/7390840/7390840.pdf
- https://cdn.steamstatic.com/apps/valve/2008/GDC2008_StylizationWithAPurpose_TF2.pdf
- https://cir.nii.ac.jp/crid/1363388843989515904
- https://classics.stanford.edu/publications/first-fossil-hunters-dinosaurs-mammoths-and-myth-greek-and-roman-times
- https://cris.tau.ac.il/en/publications/how-to-build-a-hybrid-the-structure-of-imagination/
- https://darwinmuseum.ru/pages/a-zebroid-a-horse-or-a-zebra
- https://datadryad.org/dataset/doi:10.5061/dryad.4291n
- https://digitalcommons.usf.edu/geo_facpub/838
- https://digitalcommons.usm.maine.edu/thinking_matters/173
- https://dinoproject.blogs.bristol.ac.uk/?p=811
- https://en.engormix.com/equines/horse-genetics/what-mule-made_n11953/
- https://eprints.lancs.ac.uk/id/eprint/50885/
- https://extension.unh.edu/sites/default/files/migrated_unmanaged_files/Resource004972_Rep7077.pdf
- https://gizmodo.com/27-avatar-questions-answered-by-the-movies-designers-5464478
- https://journalhosting.ucalgary.ca/index.php/arctic/article/view/67681
- https://link.springer.com/content/pdf/10.3758%2FBF03195281.pdf
- https://news.cnrs.fr/node/2233
- https://nysm.nysed.gov/node/8054
- https://openoregon.pressbooks.pub/mhccmajorsbio/chapter/epistasis/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC1689826
- https://pmc.ncbi.nlm.nih.gov/articles/PMC1941816
- https://pmc.ncbi.nlm.nih.gov/articles/PMC2670537
- https://pmc.ncbi.nlm.nih.gov/articles/PMC2674085
- https://pmc.ncbi.nlm.nih.gov/articles/PMC2918493
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3061134
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3130450
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3497252
- https://pmc.ncbi.nlm.nih.gov/articles/PMC4096361/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6458325
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6793066
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8633094
- https://proceedings.iclr.cc/paper_files/paper/2024/hash/5b9bef4eae0f574cedbf9f4bf29d8ae7-Abstract-Conference.html
- https://repository.essex.ac.uk/9355/
- https://researchportalplus.anu.edu.au/en/publications/shape-shifting-changing-animal-morphologies-as-a-response-to-clim/
- https://scholars.duke.edu/display/pub798983
- https://sdbonline.org/archive/dbcinema/ledouarin/ledouarin.html
- https://slcc.pressbooks.pub/collegebiology1/chapter/incomplete-dominance-and-codominance/
- https://stars.library.ucf.edu/facultybib2010/1881
- https://typeset.io/pdf/on-the-validity-of-bergmann-s-rule-sf29n9xsn5.pdf
- https://ucmp.berkeley.edu/vertebrates/flight/converge.html
- https://www.cs.princeton.edu/courses/archive/fall07/cos597B/papers/mitchell-team-fortress.pdf
- https://www.farmshow.com/a_article.php?aid=11569
- https://www.farmshow.com/a_article.php?aid=6960
- https://www.iflscience.com/zebroids-zeedonks-zorses-zonies-welcome-to-the-world-of-zebra-hybrids-80202
- https://www.jove.com/science-education/10778/polygenic-traits
- https://www.karlsims.com/papers/siggraph94.pdf
- https://www.kcl.ac.uk/responses-the-philosophising-brain
- https://www.livescience.com/12047-real-fake-8-bizarre-hybrid-animals.html
- https://www.livescience.com/health/genetics/scientists-reveal-genes-that-make-cats-orange
- https://www.nature.com/articles/307634a0.pdf
- https://www.nature.com/articles/468891a
- https://www.nature.com/articles/6886170
- https://www.nature.com/articles/nmeth1110-872.pdf
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8377870/
- https://www.newworldencyclopedia.org/entry/Liger
- https://www.scientificamerican.com/blog/tetrapod-zoology/speculative-zoology-at-tet-zoo-the-story-so-far/
- https://www.thetech.org/ask-a-geneticist/why-are-ligers-so-big

## Raw verifier output (run 4)
```
# checked 9 files, 94 cards, 79 unique links
403  R3_body_plan_limits.md:104, R3_body_plan_limits.md:159, R3_body_plan_limits.md:194 https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:74, R7_fiction_and_design.md:103 https://blog.everythingdinosaur.com/blog/_archives/2024/06/21 (403: likely bot-blocked, check in a browser)
403  R5_real_chimeras.md:88, R5_real_chimeras.md:130 https://discovery-pp.ucl.ac.uk/id/eprint/10108322 (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:76, R7_fiction_and_design.md:117 https://fma.fandom.com/wiki/Dolcetto (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:75, R7_fiction_and_design.md:110 https://hunterxhunter.fandom.com/wiki/Chapter_187 (403: likely bot-blocked, check in a browser)
403  R1_inheritance.md:115, R2_real_hybrids.md:115, R2_real_hybrids.md:139 https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids (403: likely bot-blocked, check in a browser)
403  R4_environment_to_form.md:86 https://ocean.si.edu/node/111022 (403: likely bot-blocked, check in a browser)
403  R5_real_chimeras.md:92, R5_real_chimeras.md:109 https://pubmed.ncbi.nlm.nih.gov/20813264/ (403: likely bot-blocked, check in a browser)
403  R4_environment_to_form.md:82, R4_environment_to_form.md:114 https://pubmed.ncbi.nlm.nih.gov/29592141/ (403: likely bot-blocked, check in a browser)
403  R6_perception.md:86, R6_perception.md:131 https://pubmed.ncbi.nlm.nih.gov/8632824/ (403: likely bot-blocked, check in a browser)
403  R3_body_plan_limits.md:105, R3_body_plan_limits.md:166 https://rvc-repository.worktribe.com/OutputFile/1397435 (403: likely bot-blocked, check in a browser)
403  R2_real_hybrids.md:120, R2_real_hybrids.md:160 https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies (403: likely bot-blocked, check in a browser)
403  R3_body_plan_limits.md:103, R3_body_plan_limits.md:152 https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18 (403: likely bot-blocked, check in a browser)
403  R1_inheritance.md:117, R1_inheritance.md:217, R2_real_hybrids.md:130, R2_real_hybrids.md:244 https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf (403: likely bot-blocked, check in a browser)
# 0 failures, 14 bot-blocked (403), 0 SSL warnings, 0 timeout warnings, 65 resolved (history: run-1 resolved set, 62 URLs)
```
