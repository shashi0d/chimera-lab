# Before and after

The five most improved screens from the PV correction loop. Each pair is the same state captured by `npm run shots`. Left is pv-1, right is the corrected round.

## 1. Success: the creature leads (PV1-04, PV1-08)

| Before (pv-1) | After (pv-2) |
|---|---|
| ![](pv-1/1440x900/light/20-success-real-hybrid.png) | ![](pv-2/1440x900/light/20-success-real-hybrid.png) |

The Fusion node used to end in an 8-row step log with per-step details: taller and busier than the plate. It now folds into a summary (thumbnail, name, "8 steps · 0.7s", "Generated fusion") with a "Show steps" disclosure. The tasksheet's "result inside the Fusion node" requirement is also covered. The mock plate is now full-bleed, so the UI's frame and caption are the only frame.

## 2. Many nodes: no more stacking (PV1-01, PV2-02)

| Before (pv-1) | After (pv-3) |
|---|---|
| ![](pv-1/1440x900/light/60-fit-view-many-nodes.png) | ![](pv-3/1440x900/light/60-fit-view-many-nodes.png) |

The second Fusion node and its Result landed on top of the first pair, leaving ports unreachable (blocker). New nodes now use free-space placement, and images added next to an empty Fusion node are wired into it and placed to its left, so the canvas reads as two clean rows.

## 3. Failed input: no layout shift (PV1-03)

| Before (pv-1) | After (pv-2) |
|---|---|
| ![](pv-1/1440x900/light/30-error-human.png) | ![](pv-2/1440x900/light/30-error-human.png) |

The flag note grew the Image node into its neighbour. Notes are now an overlay strip inside the image frame, with a cinnabar rule, so the card's height never changes.

## 4. Panel beside its node at 1024 (PV1-11)

| Before (pv-1) | After (pv-3) |
|---|---|
| ![](pv-1/1024x768/light/23-panel-open.png) | ![](pv-3/1024x768/light/23-panel-open.png) |

At narrower widths the drawer covered the very image it explains. Opening the panel now pans the canvas so the Result node sits fully to the left of it.

## 5. Offline add: new work is always in view (PV1-02, PV2-01)

| Before (pv-1) | After (pv-3) |
|---|---|
| ![](pv-1/1440x900/light/41-offline-upload-queue.png) | ![](pv-3/1440x900/light/41-offline-upload-queue.png) |

The queued image was dropped half above the viewport, and its note pushed the card taller. It is now placed right or down in free space, auto-wired to the free B input, and revealed (zooming out only if needed). The "Waiting for connection" note sits inside the frame.
