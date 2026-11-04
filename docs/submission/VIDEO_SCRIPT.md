# Demo video script (3 minutes)

> **PENDING the owner's S5 ratings.** The six creatures below are the proposed showcase from
> `docs/evolution/S5_BENCHMARK.md` ("Proposed showcase"). Swap any creature the owner rates "fails" in
> `docs/evolution/benchmark/s5_review.html` for an alternate (b04 fixed pipeline, b07 agent) before recording.
> Also pending: the R1 UI and hosting (not merged at the time of writing), and the owner's answer on the ZD design
> system (`docs/r1/docs_notes.md`).

## Rules for this video

- **Real, unedited runs only.** Every creature shown is a saved run: the six S5 agent images
  (`docs/evolution/live/s5/<case>/agent/image.webp`, commits `d6b5d8f` to `3d0b519`) and one new live run recorded
  for the video. No retouching, no cherry-picked re-rolls presented as first tries.
- **Show only work built during the hackathon** (`docs/submission/BUILT_DURING_HACKATHON.md`). No v1 node canvas.
- **Every cut is stated on screen.** A live run takes about 5 minutes (295 s on average in S5), so the video starts a
  run, cuts, and returns to **the same run** after it finishes, reopened from its link.
- **Every creature is called generated.** The "Generated fusion" label stays visible. No franchise names, no
  "real animal" wording.
- **State the limits.** The benchmark result is "about even"; the video says so.

## Before recording

1. Start the live run for the video (suggested: Indian pangolin × horse, realistic, the b09 pair; any pair works).
   Note the run id. It costs one of the daily runs and about 40 model calls (S5: 39 per agent creature).
2. Keep the result whatever it is. If it has remaining failures, show them; the card states them.
3. Screen size 1440 × 900, light theme, browser zoom 100%.

## Shot list

| Time | Shot | On-screen action | Voiceover | What judges should see |
|---|---|---|---|---|
| 0:00 to 0:12 | Gallery | Open the app. The gallery is the first screen: the six showcase creatures, each tagged "Generated fusion". Slow scroll. | "This is Chimera Lab. You give it two animals, and an agent designs one creature from them, then tells you how it built it and what still looks wrong." | The product in one look; the generated label |
| 0:12 to 0:25 | Gallery, hover b09 | Hover the pangolin × horse card. | "It's for creature designers in games, film and tabletop, and for anyone learning biology by designing. Every choice it makes cites a rule from research on real hybrids, chimeras and body limits." | Who it is for |
| 0:25 to 0:45 | New run | Drop two photos (or type two names), pick "realistic", press start. The trace panel opens: `resolve_animal` twice, `propose_candidates`. | "The agent is Muse Spark Open, an open-weight model, running on Baseten. It calls tools: it looks up both animals, then code proposes candidate body plans." | A real run starting; the Baseten-hosted agent |
| 0:45 to 0:58 | Trace | `choose_candidate` appears with its reason, then plan operations and `audit_plan`. Freeze for 2 s on the reason text. | "Here it picks the host, the animal that sets the body, and says why. It can only change the plan through typed operations, and code audits the plan before anything is drawn." | The reason on every step; guardrails in code |
| 0:58 to 1:03 | Title card | Full-screen text: **"Cut. This run took N min. Same run, reopened from its link."** (fill in N from the run) | (no voiceover) | An honest cut |
| 1:03 to 1:30 | Trace, finished run | Scroll the same run's trace: `render`, `inspect` with failures listed, `edit`, `inspect` again. Hover one failure. | "Muse Image draws it. Then two critics inspect the image without seeing the plan: they describe it, count heads, legs and tails, and answer a checklist. Muse Spark 1.3 has the deciding vote, and SAM 3.1 checks that the planned parts are there. A covering problem gets one targeted edit; a body problem needs a new plan." | Plan-blind inspection; edit vs re-plan; four Meta models at work |
| 1:30 to 1:55 | Creature card | Open the card: label, host and reason, "Can it live?", remaining failures, anatomy map overlay toggled on. | "The card shows the label, real hybrid, speculative chimera or mythic composite, the host and why, whether the body could work, and any failure the final image still has. The anatomy map colors each part SAM finds by the parent it came from, and lists what it couldn't find." | Honesty on the card; anatomy map |
| 1:55 to 2:05 | b09 Indian pangolin × horse | Open the b09 showcase card. Highlight the host reason. | "Pangolin and horse tie as hosts. A fixed pipeline just takes the first name. The agent chose the horse, and the critic names both animals." | The agent's advantage on host ties |
| 2:05 to 2:13 | b01 axolotl × Chinese pangolin | Open b01. | "Axolotl and pangolin: scales over smooth skin, the axolotl's face kept." | Integration that works |
| 2:13 to 2:21 | b03 lion × golden eagle, mythic | Open b03. Point at the "mythic composite" label. | "In mythic mode it may bend up to three rules, declared on the card." | The mythic label and declared licenses |
| 2:21 to 2:29 | b11 crab × gray wolf | Open b11; show the trace steps `set_extent` then `set_covering_material_only`. | "Crab and wolf: after two failed armor attempts, a rule in code stopped the edits, and the agent changed the plan to crab color on wolf fur, keeping the claws." | The two-failure rule working |
| 2:29 to 2:36 | b08 red fox × barn owl, then b05 donkey × horse | Open b08, then b05. | "Fox and owl, wings in place of the forelegs. And a real hybrid, the mule, labelled as one." | Range: speculative and real hybrid |
| 2:36 to 2:52 | Benchmark slide | Text slide: agent 5 of 11 full matches, pipeline 6 of 11; average failures 1.82 vs 1.91; both parents named 7 vs 5. Then one line each: "Hard plates over fur still look worn, not grown." "A run takes about 5 minutes." | "We benchmarked the agent against a fixed pipeline on 11 cases. Overall they're about even. The agent wins host ties and names both parents more often. Hard plates over fur still look worn, not grown, and a run takes about five minutes." | Honest measurement and limits |
| 2:52 to 3:00 | End card | Logo, the four model names (Muse Spark Open on Baseten, Muse Spark 1.3, Muse Image 1.0, SAM 3.1), the app URL, "Every creature is generated." | "Chimera Lab. Built during the hackathon, with four Meta models." | Meta tooling recap; link |

## Facts behind the voiceover

| Line | Source |
|---|---|
| Agent is Muse Spark Open on Baseten | `backend/app/evolution/agent.py`, `data/evo_config.json` `routing.agent` |
| Code audits before rendering; typed operations only | D-089, D-094 |
| Two critics, plan-blind; Muse Spark 1.3 decides | D-072, D-084 |
| One edit for covering problems; structural needs a new plan | D-089 |
| b09 host reason; pipeline fell back to the first name; critic names both | `docs/evolution/S5_BENCHMARK.md`, b09 |
| b11 `set_extent` then `set_covering_material_only` | `docs/evolution/live/s5/b11/agent/trace.md` |
| Mythic: up to 3 declared licenses | D-060 |
| Benchmark numbers | `docs/evolution/live/s5/scores.json` |
| About 5 minutes per run | S5 agent average 295.3 s |

## Do not say

- That the agent is better overall. It is about even (S5).
- That b03's eagle head goes against the plan. The b03 plan gives the eagle's head ("myth-style head swap" in
  `live/s5/b03/agent/plan.json`), so the image follows it.
- That any creature is a real or possible animal, except that b05 is labelled as a documented real hybrid.
