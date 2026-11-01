# Submission form text (draft)

Draft answers for the hackathon form. Every number cites its source. Placeholders are in square brackets. Items
marked OWNER need the owner's decision before submitting (see `docs/r1/docs_notes.md`).

## Project name

Chimera Lab

## Track

Indie Developer (solo entry).

## One-liner

Give it two animals; an agent on Muse Spark Open designs one generated creature, checks it with critics that never
see its plan, and tells you what still looks wrong.

## Description

Chimera Lab turns two animals (a photo or a name for each) and a design mode into one generated creature, with a
card that explains how it was built.

An agent, Muse Spark Open running on Baseten, works through a tool loop. It looks up both animals, compares candidate
body plans, chooses which animal sets the body frame and says why, edits the plan only through typed operations,
and passes a code audit before anything is drawn. Muse Image 1.0 renders the creature. Two critics then inspect the
image without seeing the plan, Muse Spark 1.3 casting the deciding vote, while SAM 3.1 confirms the planned parts.
A covering problem gets a targeted image edit; a body problem needs a new plan.

The card shows the creature's label (real hybrid, speculative chimera or mythic composite), the host and the reason
for it, whether the body could work, any failure the final image still has, and an anatomy map coloring each part
by the parent it came from. Every creature is labelled "Generated fusion" and is never presented as a real animal.

## Problem statement fit

[OWNER: paste the official problem statement or theme here if the form asks for one; the repo does not record it.]

- **The problem:** a two-animal prompt to an image model gives a striking picture with no reasoning behind it. In
  our direct tests, input order alone decided which animal became the body (`docs/live/direct4/README.md`). A
  designer or learner gets no reason, no check and no statement of what is wrong.
- **What Chimera Lab adds:** a reason for every anatomy choice, grounded in rule cards from research on real
  hybrids, lab chimeras, body-plan limits and perception (126 cards, 18 hard; `data/rule_cards.json`), an
  independent check of the result, and an honest card.
- **Who it is for:** creature designers for games, film and tabletop; people learning biology by designing. No
  user testing has been done yet.

## How Meta models are used

| Model | Role | Evidence |
|---|---|---|
| Muse Spark Open (`meta-models/muse-spark-open-1026`, Baseten) | The agent: tool calling over 21 tools; one of the two critics; identify, checklist, prompt polish | `backend/app/evolution/agent.py`; S1 probe: tool calling correct over 4 turns, 15 of 15 checklist answers matched Muse Spark 1.3 (`docs/evolution/S1_CAPABILITIES.md`) |
| Muse Spark 1.3 (Meta Model API) | The deciding critic; web-search traits with citations that code verifies on the fetched page; plans for the fixed pipeline; the function audit | D-068, D-074, D-084 |
| Muse Image 1.0 (Meta Model API, Responses API) | Renders, and edit turns on the same image via `previous_response_id` | D-070; S1 measured an edit changing 3.7% of pixels on the same creature |
| SAM 3.1 (Meta Model API) | Presence checks for planned parts during inspect; the anatomy map | `backend/app/evolution/anatomy.py`; S5 found heads, legs and tails in 22 of 22 images |

In the 22-creature benchmark run: Spark Open 362 calls, Muse Spark 1.3 110, Muse Image 49 images, SAM 3.1 179
(`docs/evolution/S5_BENCHMARK.md`). Each model does the job it measured best at (routing per call type, D-069).

## Technical depth

- **Agent with guardrails in code:** audit before render, a host tie must be chosen, structural failures cannot be
  edited away, a drift check after edits, and runaway caps (4 renders, 30 tool calls). Each typed plan operation has
  its own schema, built per turn with the plan's own parts as enums; in the benchmark run 0 of 142 tool calls were
  refused, against 15 of 158 before (D-094, S5).
- **The two-failure rule:** two covering failures in a row lock covering edits until the plan changes (D-091,
  D-092).
- **Plan-blind critics, calibrated on owner-labelled images:** 6 of 6 failures caught with 0 of 5 false alarms on
  the first gold set (S3a), then 18 of 18 with 3 of 15 false alarms on 33 images (S3b).
- **Cited traits checked in code:** source tiers, the model's quote must appear on the fetched page, and the page
  must name the animal. Of 50 earlier citations, 16 survived (S3a).
- **A frozen benchmark:** 11 cases, hash-checked, scored in code; 22 live creatures, 700 calls, none failed, no
  reruns (S5).
- **Resumable runs:** saved after every tool step; a run can be left and reopened (D-090, R1).
- **Tests:** 956 backend tests passing in mock mode at S5 (`docs/BUILD_LOG.md`).

## What is new (built during the hackathon)

All of it. The first commit is Oct 29, 2026, 10:19 PM Eastern; every commit falls in the building period. The
animal dataset (built Oct 28), the owner's research documents, the ZD design system tokens, fonts and third-party
libraries came from outside or before the repo, and are listed with their licences in
`docs/submission/BUILT_DURING_HACKATHON.md`.

## Results, stated honestly

On the 11-case benchmark the agent and a fixed pipeline are about even: 5 vs 6 full matches, 1.82 vs 1.91 average
critic failures. The agent wins host ties (7 of 11 cases tie) and names both parents more often (7 vs 5), at about
1.6 times the calls. Hard plates and shells over fur still look worn, not grown. A run takes about 5 minutes
(`docs/evolution/S5_BENCHMARK.md`).

## Links

- App: [URL, hosting not decided]
- Repository: [https://github.com/shashi0d/chimera-lab, if public; OWNER]
- Video: [URL]
- X post: [URL]

## Prize categories to flag

| Prize | Flag? | One-line justification |
|---|---|---|
| Best Build on Meta Open Weight Models | Yes | The agent brain is Muse Spark Open (`meta-models/muse-spark-open-1026`) on Baseten, running every agent turn (139 in the benchmark run). |
| Best Agentic Use-Case | Yes | A tool-calling agent that chooses, audits, renders, inspects, edits and re-plans with a stated reason on every step, under guardrails enforced in code. |
| Best Creative Build (Muse Image) | Yes | Muse Image renders every creature and makes targeted edit turns on the same image, driven by a compiled plan. |
| Most Viral | OWNER | Depends on the X post; the creatures are shareable, but there is no engagement yet. |
| Community Vote | OWNER | The gallery is public, if hosting is ready. |
