# UI standard

This is the quality bar for Chimera Lab, how it is checked, and what counts as a defect. It applies to every screen, including screens added in feature rounds F1 and F2.

## The bar

A first-time judge looks at any screen and believes it is a shipped, funded product with its own identity. That means:

1. **The creature is the hero.** On any screen with a result, the generated image is the largest and highest-contrast element. Process detail (steps, provenance) is smaller, quieter and one click away.
2. **Next action is obvious.** Every state shows either the next action (Fuse, Add images, Retry fusion) or a sentence that names what is missing. A disabled control always has a visible reason next to it.
3. **State is legible without color.** Every status has a word plus a glyph shape (check, cross, triangle, pulse dot, hollow ring). Port types differ by shape (circle vs diamond). Errors have a left rule and a title, not only red text.
4. **Nothing moves unless something is happening.** Allowed motion is listed in DESIGN_U1.md (Motion). Nothing may shift layout when state changes, and a node's height change must never push it into a neighbour.
5. **Honest provenance.** Each generated image carries "Generated fusion" in its caption. Real hybrids are named as real and kept separate from the generated image.
6. **Tokens only.** Every color, size, radius and duration comes from `theme.css` tokens (enforced by `scripts/check-css.sh`).

## Hard floors (automated)

| Check | Tool | Threshold |
|---|---|---|
| Accessibility | axe-core via `@axe-core/playwright` on empty, connected, result, panel, error and offline states, in both themes | 0 serious, 0 critical |
| Text contrast | `tests/unit/contrast.test.ts` computes WCAG ratios from the tokens | ≥ 4.5 for all text pairs, both themes |
| Keyboard | `a11y.spec.ts` keyboard-only walkthrough: add two images, fuse, open "How this was made" | completes with a visible focus ring |
| Hit targets | tool rail, zoom and top bar buttons | ≥ 32px (we use 36 to 40px) |
| Layout | no horizontal page overflow; no clipped text in titles, buttons, badges, banners, toasts, panel headings (checked through `scrollWidth`, unless `text-overflow: ellipsis` is intended) | 0 at 1440, 1280 and 1024 |
| Regressions | Playwright `toHaveScreenshot` baselines for approved screens (`tests/e2e/visual.spec.ts`) | ≤ 1% pixel diff |
| Styling rules | `scripts/check-css.sh` | single `theme.css`, no inline styles, hex only in token blocks |

## Verification method

1. `npm run shots -- --round <name>` captures the state matrix (see `docs/visual-qa/INDEX.md`). The tool starts its own mock backend and test-mode frontend, then reaches each state through test hooks and real interactions, with no manual clicking.
2. **Matrix scope.** All states are captured at 1440×900 in both themes. 1280×800 and 1024×768 capture the *core* states (flagged `core: true` in `capture.ts`) in both themes. Smaller widths only reflow the shell (tool rail, banners, panel), while node cards stay the same size. The layout assertions run the full flow at every width, so issues outside the core set are still caught. **Change from the tasksheet default:** a full matrix at all three widths would add about 200 near-duplicate images to review without testing anything new.
3. I review every screenshot in labelled 2×2 contact sheets (`scripts/contact_sheets.py`), scoring each one 1 to 5 on the six rubric criteria: hierarchy, clarity, state legibility, consistency, polish, craft. Any score below 4 is a defect.
4. Defects go into `docs/visual-qa/DEFECTS.md`, each with screenshot path, criterion, severity and planned fix. I fix them, recapture the affected states plus at least 10 unaffected ones, and re-review.

## What counts as a defect

| Severity | Definition | Examples |
|---|---|---|
| **Blocker** | A user cannot complete the flow, or the screen misleads | Nodes stacked on top of each other so ports can't be reached; a generated image without the "Generated fusion" label; a state that can't be left |
| **Major** | Flow works, but the screen looks broken or unfinished, or hierarchy is wrong | Overlap after a height change; content outside the viewport after an action; the creature smaller than the step log; unreadable contrast |
| **Minor** | Polish | Inconsistent spacing; a slightly misaligned port; transient "Saving…" noise; duplicated framing |

## Exit criteria for PV and every feature round

- No open blocker or major defects.
- Every reviewed screen scores 4 or more on all six criteria.
- All automated floors above pass.
- Baselines are re-approved only for intentional changes, and each change is logged in DECISIONS.md.
