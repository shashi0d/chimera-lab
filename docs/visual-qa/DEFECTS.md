# Visual defects

Scored against `docs/UI_STANDARD.md`. Criteria: H hierarchy, C clarity, S state legibility, K consistency, P polish, R craft. Paths are relative to `docs/visual-qa/`.

## Round pv-1

| ID | Screenshot | Criterion (score) | Severity | Defect | Planned fix | Status |
|---|---|---|---|---|---|---|
| PV1-01 | `pv-1/1440x900/*/60-fit-view-many-nodes.png` | P (1), C (2) | **Blocker** | The second Fusion node and its Result node land on top of the first pair. "Add fusion node" drops at window center, and the Result node uses a fixed offset, so ports are unreachable. | Use `findFreeSpot` for tool-rail nodes and for the auto-created Result node. | open |
| PV1-02 | `pv-1/1440x900/*/41-offline-upload-queue.png` | C (2), P (2) | **Major** | An image added to a non-empty canvas is placed above the viewport, half off-screen. The free-spot search also tries upward, and the view doesn't follow new nodes. | Search right and down only, then fit view so new nodes are visible. | open |
| PV1-03 | `pv-1/1440x900/*/30-error-human.png`, `41-offline-upload-queue.png` | P (2) | **Major** | Flagged and queued notes grow the Image node, which then overlaps the node below. This is a layout shift on a state change. | Render these notes as an overlay strip inside the image frame, so node height stays constant. | open |
| PV1-04 | `20-success-real-hybrid.png`, `21-success-warnings.png`, `22-version-2.png`, `61-canvas-100-percent.png` | H (3) | **Major** | After success, the Fusion card's 8-step log with per-step details is taller and busier than the creature plate. Process outweighs the result. The tasksheet (7.4) also asks for the result preview *inside* the Fusion node, which is missing. | On success, collapse steps to a summary row ("8 steps · 1.2s", expandable) and show a result thumbnail + name in the Fusion node. While running, show the detail of the latest finished step only. | open |
| PV1-05 | `02-drop-overlay.png` | P (2) | **Major** | The "Drop to add" label sits on top of the empty-state copy, and the two overlap. | Hide the empty-state card while dragging; enlarge the overlay label. | open |
| PV1-06 | `pv-1/1440x900/dark/*` (selected nodes) | S (3) | Minor | In dark theme the selection lift (black offset shadow) is nearly invisible on green-black. | Dark `--shadow-ink` uses a raised ink tone that reads on the dark canvas. | open |
| PV1-07 | most states | P (3) | Minor | Top bar flashes "Saving…" for every small change (upload progress), which is visual noise. | Only show "Saving…" if a save is pending for more than 1s. | open |
| PV1-08 | `20-*.png`, `21-*.png` | R (3) | Minor | The mock plate draws its own inner frame and caption inside the UI's plate frame: a double frame. | Mock renders full-bleed, without frame or caption (the UI supplies both). | open |
| PV1-09 | `04-uploading.png` | S (4) | Minor | Shows "Uploading 0%" because the screenshot throttles the request before any bytes go out. Real uploads report progress. | None. Noted as expected. | wontfix |
| PV1-10 | `30-error-*.png` | C (4) | Minor | After a failed first run, the Result node shows "The result appears here after you fuse." next to the error. It's acceptable, but it competes for attention. | After a failure with no versions, dim the empty Result node and say "No image yet. See the Fusion node." | open |
| PV1-11 | `pv-1/1024x768/*/23-panel-open.png` | H (3) | **Major** | At 1024 (and 1280) the side panel covers the Result node it describes, so the image and its explanation can't be seen together. | When the panel opens, pan the canvas so the node sits fully left of the panel. | open |

Scores for all other screens: ≥ 4 on every criterion. Strongest: `23-panel-open` (H5 C5 R5) and `40-offline-banner` / `42-server-unreachable` (S5: two distinct treatments, ink bar vs cinnabar band).
