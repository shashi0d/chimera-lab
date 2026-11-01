# R1 Stream C notes: submission documents

Branch `r1-docs`, based on `evo` at `990703e`. Written Nov 1, 2026. No model calls were made.

## What I produced

| File | What |
|---|---|
| `docs/submission/BUILT_DURING_HACKATHON.md` | Dated list of the work by date and phase with commit ranges; everything from outside or before the repo, with licence status |
| `docs/submission/README.md` | The README rewrite; the lead moves it to the repo root at merge |
| `docs/submission/ARCHITECTURE.md` | Two Mermaid diagrams (system; agent loop) with a sourced table and notes |
| `docs/submission/VIDEO_SCRIPT.md` | 3-minute shot list with timings, voiceover and what judges should see; marked PENDING the owner's S5 ratings |
| `docs/submission/SUBMISSION_FORM.md` | Form answers and prize flags |
| `docs/submission/X_POST.md` | Main post and two alternates, character-counted |

## Sources used, by claim area

| Claim area | Sources |
|---|---|
| Dates, phases, commits, authorship | `git log --all` (times converted to US Eastern), `docs/BUILD_LOG.md`, commit trailers |
| Pre-existing and outside items | `data/chimera_data.json` `meta` block and its source URLs (counted with a script), `docs/design-system/ZD.md`, BUILD_LOG E1 and S3b part 0, `backend/requirements.txt`, `frontend/package.json`, licence fields in the installed packages' metadata (`.venv`, `frontend/node_modules` of the main checkout) |
| How the agent works | `backend/app/evolution/agent.py` (docstring, `TOOLS`, `OP_TOOLS`), D-066 to D-094, `data/evo_config.json` (`agent`, `routing`, `critic_decision`) |
| Models and their jobs | `backend/app/config.py`, `backend/app/evolution/live.py` (`sam-3.1`), `data/evo_config.json` `routing`, `docs/evolution/S1_CAPABILITIES.md` |
| Benchmark numbers | `docs/evolution/live/s5/scores.json` (totals checked against `S5_BENCHMARK.md`), `S5_BENCHMARK.md` usage table, ROADMAP 5b S5 row (0 refusals in 142 tool calls) |
| Known limits and examples | `S5_BENCHMARK.md` "Known limits"; I checked the S5 prompt files myself (see decision 4) |
| Labels | `backend/app/evolution/route.py` constants; `doc.json` `card.kind` for b01, b03, b05, b08, b09, b11 |
| Calibration and citation numbers | `docs/evolution/S3a_TRUST.md`, `docs/evolution/S3b_TRAITS.md` |
| R1 features (caps, SSE, gallery, endpoints) | D-096, `docs/api_contract.md` |
| Mermaid validity | Both diagrams parsed and rendered with mermaid 11.4.1 in headless Chromium (scratch script, not committed) |

## Decisions

1. **Times in US Eastern.** The deadline is Eastern. The first commit is Oct 29, 10:19 PM Eastern, which is Oct 30
   UTC; the brief's "repo created Oct 30" is the UTC date, and BUILT_DURING_HACKATHON.md says both.
2. **R1 work is described as the target, not as done.** Nothing from R1 was merged when I wrote these files, so the
   README has a status line and ARCHITECTURE.md says which parts are R1. The lead should update both at merge.
3. **Code paths in backticks, not markdown links.** The README moves to the root at merge and the other files stay
   in `docs/submission/`; backticked root-relative paths read the same from both places.
4. **I did not repeat S5 known limit 4 ("the plan keeps the lion's head" in b03).** `live/s5/b03/agent/plan.json`
   has `traits.head` PICK from the golden eagle ("myth-style head swap"), and `prompt_final.txt` asks for the eagle's
   head; the fixed pipeline's plan is the same. So the b03 image follows its plan. For "the image model sometimes
   ignores a correct prompt" I used instead: b08 (the same compiled prompt gave 1 failure, then extra legs; I
   compared `img1_prompt_compiled.txt` and `img2_prompt_compiled.txt`, identical), b06 (four renders from one
   compiled prompt, all failed), b01 (a re-render of the same compiled prompt passed) and b02 (the prompt says plates
   grown from the skin; both systems drew armor). The video script lists the b03 claim under "Do not say".
5. **"No user testing has been done"** is stated in the README and form. I found no user study in the repo.
6. **Money cost is "not measured".** `docs/BUILD_LOG.md` L1 says "Cost unknown", and I found no cost figure since.
7. **Prize flags:** Open Weight, Agentic and Creative flagged yes; Most Viral and Community Vote left to the owner.
8. **The README keeps the v1 env table out.** It lists only what a reader needs for the agent; the full v1 table is
   in git history (`README.md` at `990703e`).
9. **The four labels:** the brief names three; the code has a fourth, "speculative hybrid of close relatives"
   (D-055). The README lists the three and mentions the fourth in one line.

## Open questions for the owner

1. **Data-source licences.** `data/chimera_data.json` cites Animal Diversity Web (638 URLs), GBIF (1,978), Zenodo
   record 6468938 (5,540) and Wikipedia (381). Is Zenodo 6468938 AnimalTraits? What licence covers each source as
   used here, and may the derived file be public in the repo? All marked unknown for now.
2. **When was "Muse final.json" gathered?** The dataset says it was built Oct 28 from it. If any of it was gathered
   before Oct 27, it pre-dates the event and should be said so.
3. **The research docs (R1 to R10):** who or what wrote them, and when? The repo only says they were supplied by
   the owner and dated Oct 31.
4. **ZD design system:** is it your own work, and may it be public? It is pasted verbatim into `theme.css`, and the
   whole UI shows it.
5. **Impact framing:** the README names two intended users (creature designers; biology learners). Keep both, or
   lead with one? Is there any user feedback to cite?
6. **Prizes:** flag Most Viral and Community Vote?
7. **Is the repository public at submission?** The form has a placeholder.
8. **Problem statement:** the form text has a placeholder for the official theme wording, which is not in the repo.
9. **AI-assisted build:** BUILT_DURING_HACKATHON.md states that Claude Code was the coding agent (from the commit
   authors and trailers). Keep it there, and mention it on the form?
10. **Video run:** which pair for the live run in the video, and is spending one live run (about 40 calls) on it
    fine?

## For the lead, at merge

- Move `docs/submission/README.md` to the root, then update its status line and the R1 parts (endpoints, how to run
  the UI, frontend test commands and counts, the real backend test count).
- Add the R1 commits to BUILT_DURING_HACKATHON.md ("Nov 1 onward").
- S5_BENCHMARK.md known limit 4 and its showcase caveat for b03 ("an eagle head") read as if the image broke the
  plan; the plan asked for the eagle head (decision 4). Worth a correction note in the S5 report.
- The anatomy map colors b03's head as the host's (lion) although the plan's head trait is the eagle's
  (`live/s5/b03/agent/anatomy_map.json`, `"part": "head", "parent": "lion"`). That matches S5's statement that the
  map colors by the plan's parent; it seems to read the region list, not the head trait. Not investigated further
  (the engine is frozen).

## Could not verify

- Licences of the dataset's sources, the ZD system and the hosted model terms.
- Licences of the backend and frontend libraries other than FastAPI, pypdf, React, @xyflow/react, Zustand,
  idb-keyval, the three @fontsource packages and meta-sam-parser.
- Anything about R1 behaviour (UI, API, caps, resume): not built when I wrote this.
- Whether the direct experiments in `docs/live/direct*` count toward `docs/live/budget.json`.
- Hackathon rules and prize wording: taken from the task brief, not from a file in the repo.
