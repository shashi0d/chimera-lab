# Chimera Lab design

Chimera Lab is a creature workbench for science-grounded fusions. The design borrows from the natural-history world: field notebooks, specimen labels, museum plates and herbarium sheets. It does not borrow from AI-tool chrome. Flora supplies the interaction model only: an infinite canvas, cards with live previews, ports you drag to connect, and versions instead of overwrites.

## Principles

1. **Specimens, not widgets.** Every node is a specimen label: ink-ruled, flat paper, a catalog number in mono, the title in a book serif. The image is the specimen; the chrome is the label around it.
2. **The creature is the hero.** The generated image gets the largest area, a plate frame and a caption. Everything else (steps, warnings, provenance) is set smaller and quieter, and the provenance is one click away.
3. **Honest provenance.** Each generated image carries a visible "Generated fusion" caption. Real hybrids are labelled real, with their documented facts. Rule warnings are shown as field notes, not hidden.
4. **Ink conveys meaning; color reinforces it.** Every status has a word and a glyph shape as well as a color. Port types differ by shape (image ports are circles, creature ports are diamonds) as well as by hue.
5. **Quiet until it matters.** The canvas is calm graph paper. Motion is reserved for things that are actually happening: a run in progress, a refused connection, an image developing.

## Palette

The default (light) theme is "Field paper". The dark theme is "Night herbarium". Both use the same six named roles.

| Name | Light | Dark | Role |
|---|---|---|---|
| Vellum | `#F2EDE2` | `#121814` | Canvas and app background. Warm paper, never pure white; dark is green-black, never neutral black. |
| Folio | `#FBF8F1` | `#1B231E` | Node cards, panels, popovers. |
| Ink | `#1E2620` | `#E9E4D6` | Text, rules, edges, borders. |
| Moss | `#2F6B4F` | `#6FBF95` | Primary action (Fuse), creature ports, success. |
| Lapis | `#2E5A88` | `#86AEDB` | Image ports, focus ring, links, "real hybrid" marks. |
| Ochre | `#8A5A12` text / `#D9A441` fill | `#E3B65C` | Warnings and long waits. |
| Cinnabar | `#A8362A` | `#F08A7A` | Errors, refused connections, destructive actions. |

Secondary inks (muted text, hairlines) are derived as fixed tints of Ink and are defined as tokens. All text pairs meet WCAG AA: Ink on Vellum is 13.9:1, muted ink on Folio is 6.1:1, white on Moss is 6.3:1, and Ochre text `#8A5A12` on Folio is 5.6:1. Dark-theme pairs were checked the same way (see `frontend/tests/unit/contrast.test.ts`).

## Typography

| Face | Role | Why |
|---|---|---|
| **Newsreader** (variable serif, self-hosted) | Wordmark, node titles, creature names, panel headings. *Italic* for binomial (scientific) names, as natural-history convention requires. | It reads like a field guide and gives the product a voice that a UI sans can't. |
| **IBM Plex Sans** | All UI text, buttons, hints, messages. | Neutral and highly legible at 12 to 14px, with a technical-document heritage. |
| **IBM Plex Mono** | Catalog numbers, elapsed timers, rule ids, step counters, error ids. | The specimen-label register: numbers that look like they were stamped. |

Type scale (px; line-heights in tokens): 11 (micro: catalog numbers), 12 (caption), 13 (UI body), 14 (body), 16 (node title), 20 (panel title), 28 (empty-state headline), 36 (display). Tabular numerals for all timers.

## Spacing, radii, lines

- Spacing scale on a 4px base: 2, 4, 8, 12, 16, 24, 32, 48, 64.
- Radii are deliberately small: 2px (tags, ports), 4px (cards, inputs, buttons), 8px (panels, toasts). There are no pill buttons. Labels are cut paper, not lozenges.
- Hairline 1px rules in `--ink-rule`. Cards are flat, with no blur shadows. A selected card gets a **hard offset shadow** (3px 3px 0 Ink), like a label lifted off the sheet. While dragging, the offset grows to 6px.

## Motion plan

| What moves | When | Why | Duration |
|---|---|---|---|
| Edge "stitching" (dash offset) | An edge feeds a running fusion | Shows where data is flowing | 900ms loop |
| Step marker pulse | The current pipeline step | Shows liveness without a spinner wall | 1200ms loop |
| Image "develop" (blur 12px to 0, saturation 0 to 1) | A new result image first appears | Reads as a photographic plate developing; marks the payoff moment | 700ms |
| Shake (x ±4px, 3 cycles) | A connection is refused | Tactile "no" | 240ms |
| Toast slide-in from right | Toast appears | Peripheral notice | 180ms |
| Panel slide | "How this was made" opens | Spatial: comes from the node's side | 200ms |
| Card lift (shadow offset) | Select or drag | Direct manipulation | 120ms |

Nothing else animates. No fade-and-slide-up on mount. With `prefers-reduced-motion: reduce`, all loops stop, and develop and slide become instant. The current step is still shown by its glyph and label.

## Wireframes

### Canvas (1440 wide)

```
+--------------------------------------------------------------------------------------+
| (glyph) Chimera Lab          Untitled canvas · saved            [Mock mode] [◐] [?]  |  top bar 52px
+----+---------------------------------------------------------------------------------+
| +  |  . . . . . . . . . . . graph paper . . . . . . . . . . . . . . . . . . . . . .  |
| ⊕  |   +-------------+                                                               |
| ⤢  |   | No.01 Image |o----.        +------------------+        +-----------------+   |
| ↶  |   | [ photo   ] |      `----◇a | No.03 Fusion     |◆-----◇ | No.04 Result    |   |
| ↷  |   | Lion  ✓     |      .----◇b | A lion  B tiger  |        | [  plate      ] |   |
| ▦  |   +-------------+     /        | ● Identify  2.1s |        | Generated fusion|   |
|    |   +-------------+    /         | [ Fuse ]         |        | v1 v2  [How…]   |   |
|    |   | No.02 Image |o--'          +------------------+        +-----------------+   |
|    |   +-------------+                                                               |
| tool rail 48px                                              [minimap]  [- 100% +]    |
+--------------------------------------------------------------------------------------+
```

### Node card (Fusion, running)

```
+--------------------------------------+
| No.03  Fusion                ● Running|  header: mono catalog no., serif title, status word + glyph
|--------------------------------------|
| A  Lion        Panthera leo          |  inputs as read (binomial in italic serif)
| B  Tiger       Panthera tigris       |
|--------------------------------------|
| ✓ Load images                 0.1s   |  step list, mono timings
| ✓ Identify animals            1.6s   |
| ◉ Match field data            …      |  current step: pulse marker
| ○ Check real hybrids                 |
|  … 4 more                            |
|--------------------------------------|
| Still working: image generation can  |  long-wait note (after 20s), ochre rule
| take up to 2 minutes.                |
| [ Cancel ]                  00:24    |
+--------------------------------------+
```

### Result node

```
+--------------------------------------+
| No.04  Result          ▲ 1 warning   |
|  +--------------------------------+  |
|  |                                |  |
|  |        generated image         |  |  square plate, 1px ink frame
|  |                                |  |
|  +--------------------------------+  |
|  Plate 2 · Generated fusion          |  always-visible provenance caption
|  Leotigris  — Real hybrid exists ◆   |
|  ‹ v1  [v2]  ›        How this was made |
+--------------------------------------+
```

### "How this was made" panel (right drawer, 420px)

```
+--------------------------------------------+
| How this was made                      [×] |
| Leotigris · version 2 of 2                 |
|--------------------------------------------|
| Parents as read                            |
|  A  Lion  Panthera leo   94%  matched (T1) |
|  B  Tiger Panthera tigris 91% matched (T1) |
| Real hybrid                                |
|  ◆ Liger: male lion × female tiger; ...    |
| Body plan & part donors                    |
|  head A · body B · limbs B · covering A    |
| Field notes (rules)                        |
|  ▲ R-A1-01 Parents have different body...  |
| Prompt                         [Copy]      |
|  > Reference image 1 shows a lion. ...     |
| Models: mock-muse-spark · mock-muse-image  |
+--------------------------------------------+
```

## Review against generic AI-tool defaults

The first draft was checked against the usual defaults. What changed:

- **Near-black with one neon accent.** The first idea was a dark default with a single moss accent. Changed to a light paper default: field guides are printed on paper, generated plates read more truthfully on warm paper, and judges have seen a hundred dark neon canvases. Dark mode stays green-black with a full six-role palette, not grey plus one accent.
- **Identical rounded cards with soft grey shadows.** Replaced with flat, ink-ruled cards with a 4px radius and a hard offset shadow only on selection. Each node type has its own header glyph and port shapes, so cards are not interchangeable.
- **Gradient washes.** None. The only texture is the graph-paper grid.
- **All-caps eyebrow labels.** Dropped. Catalog numbers use mono in normal case ("No.03") and section headings are sentence-case serif.
- **Arrow on every button.** None. Buttons are verbs: "Fuse", "Retry fusion", "Add image".
- **Fade-and-slide-up on everything.** Replaced by the purposeful motion table above.
- **Emoji icons.** Replaced with a small hand-drawn SVG icon set (1.5px strokes, square caps) in `ui/Icon.tsx`.

## Theme mechanics

- All values are tokens on `:root` in `frontend/src/styles/theme.css`. A full retheme means editing only the token blocks.
- `[data-theme="dark"]` overrides the tokens. Light is the default on first visit, deliberately, for the reasons above; the user's choice is remembered.
- Fonts are self-hosted from `frontend/public/fonts/` (woff2, latin subset) with system fallbacks, so no network is needed at runtime.
