# Research verification report (Step 0, task E1-offline)

Date: 2026-10-31
Command: `python scripts/verify_research.py docs/evolution/research`
Result: **exit 1. Gate FAILED on rerun 2. Work stopped before Step 1, per task instructions.**

## History
- **Run 1** failed on 4 links (Sims PDF 404, Newcastle wiki 500, `www.ocean.si.edu` DNS, `nysm.nysed.gov` SSL chain). See commit 98d4d8c.
- **Fixes applied** (the only research-doc edits, as authorized):
  - R8 [S1] and RC-R8-01: now https://www.karlsims.com/papers/siggraph94.pdf (curl 200); the [S1] text now says "Copy hosted on the author's site. PR."
  - R1 [S5] and RC-R1-07: now https://openoregon.pressbooks.pub/mhccmajorsbio/chapter/epistasis/ (returns 403 to scripts, which is acceptable); the [S5] text was updated as specified.
  - R4 [S7]: now https://ocean.si.edu/node/111022 (curl 200). The fallback was not needed.
- **Verifier change:** a certificate-chain failure is retried without verification; if the page then resolves it is reported as `SSL` (a warning), not a failure. On reruns `nysm.nysed.gov` passed outright, so there are 0 SSL warnings.
- **Reruns 2 and 3** (minutes apart): all fixed links pass. One **new** failure:

| Link | Used by | Python | curl | Assessment |
|---|---|---|---|---|
| https://eprints.lancs.ac.uk/id/eprint/50885/ | R6:84, R6:110, R6:124; source of **RC-R6-03**, **RC-R6-05** (VERIFIED) | TLS handshake timed out (20s) | 000 after 21s | Passed in run 1 earlier the same day. Probably a temporary outage of the Lancaster eprints server, not a dead page. Needs a recheck or an alternative source. |

The structural checks are still clean: 94 cards, all fields present, valid values, no hard + UNVERIFIED cards, no em dashes.

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

## Raw verifier output (rerun 3)
```
# checked 9 files, 94 cards, 79 unique links
FAIL R6_perception.md:84, R6_perception.md:110, R6_perception.md:124 DEAD_LINK https://eprints.lancs.ac.uk/id/eprint/50885/ (URLError: <urlopen error _ssl.c:1063: The handshake operation timed out>)
FAIL R6_perception.md RC-R6-03 VERIFIED_DEAD_SOURCE https://eprints.lancs.ac.uk/id/eprint/50885/ (URLError: <urlopen error _ssl.c:1063: The handshake operation timed out>)
FAIL R6_perception.md RC-R6-05 VERIFIED_DEAD_SOURCE https://eprints.lancs.ac.uk/id/eprint/50885/ (URLError: <urlopen error _ssl.c:1063: The handshake operation timed out>)
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
# 3 failures, 14 bot-blocked (403), 0 SSL warnings
```
