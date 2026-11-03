# Creative collaboration: research and first demo direction

## What was studied

- Adobe Firefly lets a creator generate from a prompt and reference, choose a result, then edit it with text, generative fill, or use it as a composition reference. Its Boards expose variations on a selected image. Sources: https://helpx.adobe.com/firefly/web/unified-generation-and-editing-experience/generate-and-edit-content.html and https://helpx.adobe.com/firefly/web/create-mood-boards/firefly-boards/generate-image-variations.html.
- Canva Magic Studio treats a generated image as material for further manipulation; Magic Grab separates a subject for repositioning and resizing. Source: https://www.canva.com/newsroom/news/magic-studio/.
- Fashion tool Tabi describes a connected research, design, review and development workflow, including generating a matching back view or colorway from a selected image. Source: https://www.tabi.sh/.

These are product documentation and vendor claims, not observations of actual user sessions. The parallel for chimera design is a creator-controlled loop: express an idea and references; see a concept; select a particular result; request a change; compare and recover earlier versions. A biology critique can be useful advice, but must not silently replace the requested anatomy. Generated image edits are probabilistic, so a UI must not promise pixel-perfect preservation or localized editing unless the underlying tool supports it.

## Audit of this checkout

- The current UI accepts two names or photos and a brief. `agentapi/routes.py` uses photos for identification, then discards them. Names take precedence even when a photo is supplied. Thus visual references do not reach the live render.
- `evolution/agent.py` makes an audited typed anatomy plan authoritative, explicitly telling the image model to ignore conflicting anatomy in the creator brief. The monkey upper body and spider lower body request may therefore be changed before rendering.
- The run saves one inspected image; making another run is not an edit of that selected image. Meta's existing adapter already supports `previous_response_id` for edit turns, but the creator-facing flow does not expose it.
- The existing run trace and choice machinery are useful for long jobs, while the organism feasibility card and host/donor framing should be optional advice rather than a gate for imaginative work.
- The main branch's ZD typography, indigo accent, spacing and components are the visual baseline. The current checkout has extensive uncommitted work; retain it while building the demo.

## Demo contract

1. Accept two named and/or uploaded animal references and a natural-language brief, including the monkey/spider example. Keep the reference images available to the image call; do not silently substitute taxonomy for visual references.
2. Generate a first concept that treats the creator's brief as the design authority. Show progress, failures, and the result honestly.
3. Let the creator select an existing draft, request a text revision of that exact draft, and compare or return to versions. Pass the selected image's provider response ID to the edit call; do not claim a mask or exact preservation.
4. Use Baseten as a creative collaborator for articulating a faithful render instruction, with the original brief visible and no authority to change it. Meta renders and edits. Failure must be visible, not replaced with fixture output.
5. Keep server-side credentials, spend limits, upload validation, and the project's visual language. Verify with automated tests and a real monkey/spider run before claiming a live demo.

This demo is an experiment in the collaboration loop. Selection masks, compositing, richer critique, exports and the full production workspace remain subsequent work, to be prioritized from the demo rather than implied to exist.

## Running the demo

Build the frontend with `cd frontend; npm run build`. From the repository root, run the backend in real mode with `CHIMERA_MODE=real`, `PYTHONPATH=backend`, and the Meta and Baseten keys configured, then open `/?view=studio` on its local URL. On Windows, `scripts/dev.ps1` starts both development servers in real mode. Each concept and revision counts against the existing daily run limits. The demo retains the version list in browser local storage; its editable provider response IDs remain server-side.

The paid live example is recorded in `docs/evolution/live/studio_demo/concept.webp` and `revision.webp`. The revision asked for longer, more delicate legs. It retained the main composition, but both images show an unwanted spider face at the join; they do not prove reliable anatomy or pixel-perfect edits. `scripts/studio_live_demo.py` repeats this paid test.

## FLORA workflow and chimera translation (Nov 2026)

FLORA's documentation describes an open canvas of connected blocks, direct manipulation and a history, with each inpaint producing a new block rather than replacing its source: https://docs.flora.ai/editor/canvas and https://docs.flora.ai/editor/image-editing. Its FAUNA agent can read the canvas, add and connect nodes, and execute a workflow through conversation: https://docs.flora.ai/editor/fauna. These are vendor descriptions, not a hands-on evaluation. For Chimera Lab, the equivalent should begin with two references and a brief on a canvas; every concept or revision should become a selectable, connected image node. The creator needs to compare branches, select what the collaborator is acting on, retain originals, and explicitly run paid actions. A conversational collaborator should eventually create and connect those actions, not just rewrite a prompt.

### Audit of the live monkey/spider example

- The first concept has a recognisable monkey head, torso and arms above a spider-like lower body with radiating legs. The general upper/lower arrangement follows the brief.
- A second spider face and mouthparts appear at the join. The result reads like a monkey placed on a whole spider, rather than a single invented creature with a coherent transition. This is a visible issue, although the creator may choose to keep it.
- Some limbs overlap or leave the frame, making the requested count difficult to verify confidently. The revision makes limbs thinner and longer but preserves the extra spider face; it does not address that defect.
- Whole-image text edits can drift in pose, features or composition. A real mask-based local edit would let a creator mark the seam or face; the current Meta adapter's chained edit accepts text and previous response ID, not a verified mask parameter. Do not label a painted selection as inpainting without a model that actually accepts a mask.
- Useful next controls: a selected-image visual review tied to the original brief; selectable suggestions; a connected, branchable version canvas; side-by-side comparison; local area editing once a compatible provider is validated; clear preservation intent and optional anatomy checks. Selection and human judgment remain authoritative.

The current review tool makes a plan-blind visual description with Meta and asks Baseten for optional suggestions using that observation and the original brief. It is advisory and can be wrong. The user can copy the suggestions into an editable instruction; no automatic change occurs.

## Background work

Studio concept and revision requests can run as background jobs. The studio polls for their stage and reloads the result after a page refresh. Work continues while the server process stays alive; a local server restart marks unfinished work interrupted instead of claiming it finished. This is an in-process demo queue, not durable job execution across server restarts or multiple workers. Visual review still uses an open request. Each submitted operation consumes the configured daily allowance even if the provider later fails.

## Painted-area edit prototype

The painted edit generates a whole-image candidate through the existing Meta edit API, then composites it into the user's painted mask. Unpainted decoded RGB pixels are retained exactly; this is protected-area compositing, not native mask-conditioned inpainting. The candidate can drift in composition, so transitions may look wrong. Composite outputs are saved as PNG and passed as image references for subsequent edits, because the provider's response ID refers to the uncomposited candidate. An initial live request failed with an upstream error; one retry succeeded. The recorded `region.png` removes the spider face but leaves a conspicuous abdomen seam. A model with verified native mask support remains a priority; Baseten's published FLUX library page describes models deployed to their own endpoint, which is not evidence that this workspace has such an endpoint: https://www.baseten.co/library/family/flux-1/.
