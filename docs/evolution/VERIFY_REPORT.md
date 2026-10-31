# Research verification report (Step 0, task E1-offline)

Date: 2026-10-31
Command: `python scripts/verify_research.py docs/evolution/research`
Result: **exit 1. Gate FAILED. Work stopped before Step 1, per task instructions. No research doc was edited.**

## Setup notes
- No `incoming/` folder existed. The R1 to R8 docs, ALGORITHM.md and RESEARCH_SUMMARY.md were already in `docs/evolution/`. As instructed, no file was moved (RESEARCH_SUMMARY.md stays in `docs/evolution/research/`; it has 0 rule cards).
- `verify_research.py` did not exist. `scripts/verify_research.py` was written for this step (stdlib only, no AI calls) to the spec given by the user.

## Failures (not 403)

| Link | Cited in | Python result | curl cross-check | Assessment |
|---|---|---|---|---|
| https://course.ccs.neu.edu/cs5100f12/resources/reading/sims_creatures.pdf | R8:77, R8:92; source of **RC-R8-01** (VERIFIED) | HTTP 404 | 404 | Dead. Needs a new source. |
| https://teaching.ncl.ac.uk/bms/wiki/index.php/Epistasis | R1:109, R1:168; source of **RC-R1-07** (VERIFIED) | HTTP 500 | 500 | Server error. Dead or down. Needs a new source or a recheck. |
| https://www.ocean.si.edu/node/111022 | R4:86 | DNS failure | DNS failure (curl exit 6) | Host does not resolve. Probably `ocean.si.edu` without `www.`. |
| https://nysm.nysed.gov/node/8054 | R2:125, R2:216, R4:90, R4:149; source of **RC-R2-12**, **RC-R4-08** (VERIFIED) | SSL CERTIFICATE_VERIFY_FAILED | **200** | Probably a false alarm. The site works in curl; Python's trust store rejects its certificate chain, likely because the server omits an intermediate certificate. |

No structural failures: all 94 cards have all five fields, every strength and status value is valid, no card is hard + UNVERIFIED, and there are no em dashes.

## 403s (likely bot-blocked, check in a browser)
- https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling  (R3_body_plan_limits.md:104, R3_body_plan_limits.md:159, R3_body_plan_limits.md:194)
- https://blog.everythingdinosaur.com/blog/_archives/2024/06/21  (R7_fiction_and_design.md:74, R7_fiction_and_design.md:103)
- https://discovery-pp.ucl.ac.uk/id/eprint/10108322  (R5_real_chimeras.md:88, R5_real_chimeras.md:130)
- https://fma.fandom.com/wiki/Dolcetto  (R7_fiction_and_design.md:76, R7_fiction_and_design.md:117)
- https://hunterxhunter.fandom.com/wiki/Chapter_187  (R7_fiction_and_design.md:75, R7_fiction_and_design.md:110)
- https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids  (R1_inheritance.md:115, R2_real_hybrids.md:115, R2_real_hybrids.md:139)
- https://pubmed.ncbi.nlm.nih.gov/20813264/  (R5_real_chimeras.md:92, R5_real_chimeras.md:109)
- https://pubmed.ncbi.nlm.nih.gov/29592141/  (R4_environment_to_form.md:82, R4_environment_to_form.md:114)
- https://pubmed.ncbi.nlm.nih.gov/8632824/  (R6_perception.md:86, R6_perception.md:131)
- https://rvc-repository.worktribe.com/OutputFile/1397435  (R3_body_plan_limits.md:105, R3_body_plan_limits.md:166)
- https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies  (R2_real_hybrids.md:120, R2_real_hybrids.md:160)
- https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18  (R3_body_plan_limits.md:103, R3_body_plan_limits.md:152)
- https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf  (R1_inheritance.md:117, R1_inheritance.md:217, R2_real_hybrids.md:130, R2_real_hybrids.md:244)

## Raw verifier output
```
# checked 9 files, 94 cards, 79 unique links
FAIL R8_generative_evolution.md:77, R8_generative_evolution.md:92 DEAD_LINK https://course.ccs.neu.edu/cs5100f12/resources/reading/sims_creatures.pdf (HTTP 404)
FAIL R2_real_hybrids.md:125, R2_real_hybrids.md:216, R4_environment_to_form.md:90, R4_environment_to_form.md:149 DEAD_LINK https://nysm.nysed.gov/node/8054 (URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)>)
FAIL R1_inheritance.md:109, R1_inheritance.md:168 DEAD_LINK https://teaching.ncl.ac.uk/bms/wiki/index.php/Epistasis (HTTP 500)
FAIL R4_environment_to_form.md:86 DEAD_LINK https://www.ocean.si.edu/node/111022 (URLError: <urlopen error [Errno 11001] getaddrinfo failed>)
FAIL R1_inheritance.md RC-R1-07 VERIFIED_DEAD_SOURCE https://teaching.ncl.ac.uk/bms/wiki/index.php/Epistasis (HTTP 500)
FAIL R2_real_hybrids.md RC-R2-12 VERIFIED_DEAD_SOURCE https://nysm.nysed.gov/node/8054 (URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)>)
FAIL R4_environment_to_form.md RC-R4-08 VERIFIED_DEAD_SOURCE https://nysm.nysed.gov/node/8054 (URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1081)>)
FAIL R8_generative_evolution.md RC-R8-01 VERIFIED_DEAD_SOURCE https://course.ccs.neu.edu/cs5100f12/resources/reading/sims_creatures.pdf (HTTP 404)
403  R3_body_plan_limits.md:104, R3_body_plan_limits.md:159, R3_body_plan_limits.md:194 https://biewenerlab.oeb.harvard.edu/publications/biomechanical-consequences-scaling (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:74, R7_fiction_and_design.md:103 https://blog.everythingdinosaur.com/blog/_archives/2024/06/21 (403: likely bot-blocked, check in a browser)
403  R5_real_chimeras.md:88, R5_real_chimeras.md:130 https://discovery-pp.ucl.ac.uk/id/eprint/10108322 (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:76, R7_fiction_and_design.md:117 https://fma.fandom.com/wiki/Dolcetto (403: likely bot-blocked, check in a browser)
403  R7_fiction_and_design.md:75, R7_fiction_and_design.md:110 https://hunterxhunter.fandom.com/wiki/Chapter_187 (403: likely bot-blocked, check in a browser)
403  R1_inheritance.md:115, R2_real_hybrids.md:115, R2_real_hybrids.md:139 https://lsi.princeton.edu/research/faculty-publications/genomic-imprinting-disrupted-interspecific-peromyscus-hybrids (403: likely bot-blocked, check in a browser)
403  R5_real_chimeras.md:92, R5_real_chimeras.md:109 https://pubmed.ncbi.nlm.nih.gov/20813264/ (403: likely bot-blocked, check in a browser)
403  R4_environment_to_form.md:82, R4_environment_to_form.md:114 https://pubmed.ncbi.nlm.nih.gov/29592141/ (403: likely bot-blocked, check in a browser)
403  R6_perception.md:86, R6_perception.md:131 https://pubmed.ncbi.nlm.nih.gov/8632824/ (403: likely bot-blocked, check in a browser)
403  R3_body_plan_limits.md:105, R3_body_plan_limits.md:166 https://rvc-repository.worktribe.com/OutputFile/1397435 (403: likely bot-blocked, check in a browser)
403  R2_real_hybrids.md:120, R2_real_hybrids.md:160 https://thedonkeysanctuary.org.uk/all-about-donkeys/breeds/mules-and-hinnies (403: likely bot-blocked, check in a browser)
403  R3_body_plan_limits.md:103, R3_body_plan_limits.md:152 https://www.scilit.net/publications/cf6810694dbfb043ba6799af13e88f18 (403: likely bot-blocked, check in a browser)
403  R1_inheritance.md:117, R1_inheritance.md:217, R2_real_hybrids.md:130, R2_real_hybrids.md:244 https://www.ucl.ac.uk/taxome/jim/pap/mallet07_hybspn_Nature.pdf (403: likely bot-blocked, check in a browser)
# 8 failures, 13 bot-blocked (403)
```
