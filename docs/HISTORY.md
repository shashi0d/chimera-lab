# How Chimera Lab got here

A short record of what was tried before the current prompt-mode Lab, what was measured, and why it was replaced.
The full record (code, reports, benchmark runs, every generated image and visual-QA screenshot) is at the git tag
**`archive/evolution`**: `git checkout archive/evolution`.

## 1. The evolution agent (Oct 2026)

The first design treated a chimera as a biology problem. A fixed pipeline, later an agent, built a typed "genome"
for the creature, then drew it and checked the drawing:

- **Data:** a curated set of ~120 species (`chimera_data.json`, 2.8 MB) with body plans, parts and traits; unknown
  animals were resolved through GBIF and web-cited trait lookups, then cached.
- **Plan:** host and donor, which parts transfer, covering and extent, habitat and "can it live" functions, scored
  against ~90 rule cards drawn from cited research (genetics, anatomy, fiction design).
- **Render and inspect:** Muse Image drew the plan; plan-blind critics (Muse Spark, plus Muse Spark Open on Baseten)
  described the image and answered a checklist; SAM 3.1 segmented parts for an anatomy map.
- **Repair:** covering and surface failures were fixed by edit turns, structural ones by re-planning and re-rendering.
- **Agent (S3c–S5):** Muse Spark Open ran this as a tool loop with code guardrails, a live trace in the UI and up to
  4 renders and 30 tool calls per creature (~5 minutes per creature).

### What was measured
- **Fixed 11-case benchmark, agent vs pipeline:** about even. Full matches 5 vs 6 of 11; average failures 1.82 vs
  1.91; fewer structural failures (0.55 vs 0.91) but more integration failures (1.27 vs 1.0). The agent helped on
  structural host ties (where the pipeline had no rule) and lost when it re-rolled on critic misreads, at ~1.6× the
  calls (39 vs 24 per creature) and 27% more time.
- **Critics:** Spark Open agreed with Meta Spark on 15 of 15 checklist answers; integration rules generalised to
  held-out hosts (92% vs 98% tuned); donor identity often failed (a crab's plating read as a woodlouse; fur drawn over
  a tortoise shell). Hard coverings over fur read as worn, not grown, from S2 through S5.
- **Anatomy map:** heads, legs, tails, wings and named parts found every time; the torso 3/22, a covering 5/20.
- **Validation:** typed plan operations took tool-call refusals from 15/158 to 0/142.

## 2. Direct prompts (Nov 2026)

Calling Meta's models directly, with no app logic, showed how much the pipeline was adding:

- **One plain prompt to Muse Image** ("create a hybrid of A and B", or with both photos) gave appealing, coherent
  creatures in ~15–25 s and one call; the agent took ~40 calls and ~5 minutes for comparable critic scores.
- **Muse Image anchors on the first image:** the first photo supplies the body, scene and camera; the second
  supplies the attached features. Spark's two-step plans were more order-robust but not visibly better.
- **"Hybrid" vs "chimera":** the same design either way; "hybrid" blends more.
- Muse Spark with the image-generation tool failed every call; Spark → Muse Image in two steps worked.
- Muse Image sometimes refuses a pair outright (e.g. a black panther–owl hybrid × snake).

## 3. Why prompt mode won

Users compared the agent's results with a one-line prompt in a chat app and preferred the prompt. The measurements
agreed: the long compiled anatomy prompt made images stiffer, the critics cost minutes and calls without a clear
quality gain, and the rule system only covered the species in the data set. The product became:

- **Fusion:** one Muse Image call from a short prompt, an art style (real, drawing, anime, comic, cartoon), a white
  background, and the parents' photos or earlier creatures as references ("blend the animals, not the art styles").
- **Around it, only light model calls:** a topic check on typed text, and a profile written from the finished image
  (name, size, habitat, explorer's notes) that later steps reuse.
- **Iteration by the user, not an agent:** Revise, Paint (a marked area, filled from the parents' anatomy) and Draw
  (marks become body parts), each a new image on the canvas.

## 4. What carried over

- The live adapters (retries, budgets, key-free recordings), Supabase storage and auth, and the job runner.
- The identify step for photos (refuses people and non-animals).
- From the critics: "describe the image plan-blind first", now used to write each creature's profile.
- From the rule cards: anatomy guardrails, now short prompt rules (keep the number of limbs, attach parts where they
  can work, never erase to background).

## 5. Ideas parked for later

- Real mask inpainting and scribble-to-image on self-hosted GPU models (Modal), for Paint and Draw.
- Generation jobs as Modal functions, so the web app can scale beyond one container.
- An optional "expert" mode that plans anatomy for users who want biological plausibility.
