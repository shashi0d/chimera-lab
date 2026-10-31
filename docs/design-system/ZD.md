# ZD design system for Chimera Lab

Source: `ZeroDistance_Dashboard.html`, exported from the Claude Design project `ZeroDistanceCMSDesignSystem_3e5a47`. All token values are in `zd-tokens.css`, copied verbatim (183 tokens, light theme plus `[data-theme="dark"]` overrides, base element rules and motion keyframes). This file explains how to use them and how they map onto Chimera Lab.

What the export contains and what it does not:

- **Contains:** every token, the fonts, the motion keyframes, the dark theme, and the names and props of the system's components.
- **Does not contain:** component source code. The page references components from a shared library that was not bundled into the export. Rebuild them in React from the descriptions below, styled only through `theme.css`.

## 1. Foundations

### Color

- **Ink ramp** (`--ink-900` to `--ink-050`): a cool neutral used for all text, lines and wells. Lines and wells are `rgba(var(--ink-rgb), alpha)`, so they flip automatically in dark mode.
- **Accent:** indigo (`--indigo-500` `#6a63f5`). Use `--accent` for fills, `--accent-hover` for hover and `--accent-text` for indigo text.
- **Status:** `--info`, `--warning`, `--success`, `--danger`. Each has a `*-text` variant for text and a `--tint-*` background for pills and banners.
- **Categories:** `--cat-*`, six colors for charts and category tags.
- **Grounds and surfaces:**
  - `--ground-app` is the app background, a soft cool gradient.
  - `--surface-card` is solid white (dark: `#1b1d2e`) for cards.
  - `--surface-glass`, `--surface-sidebar` and `--surface-header` are translucent, used with `backdrop-filter: blur(var(--blur-*))`.
  - `--surface-modal` is for drawers and dialogs, over `--scrim`.
- **Gradients:** `--gradient-cta` and `--gradient-mark` (indigo to violet), and `--ground-brand` (deep navy).

### Type

| Token | Spec | Use |
|---|---|---|
| `--font-display` | Space Grotesk | headings, card titles, big numbers, creature names |
| `--font-ui` | Hanken Grotesk | all UI text |
| `--font-mono` | JetBrains Mono | kickers, meta, counts, ids, timers |
| `--type-hero` / `-h1` / `-h2` / `-h3` | 600 33/27/21/20px display | page and empty-state headings |
| `--type-page` | 600 17px display | header page title |
| `--type-card-title` | 600 16px display | node and card titles |
| `--type-body-lg` / `-body` / `-body-sm` | 400 14.5/14/13px UI | body text |
| `--type-label` | 600 11.5px UI | form labels |
| `--type-button` / `-button-lg` | 600 13/14px UI | buttons |
| `--type-caption` | 400 12px UI | captions |
| `--type-kicker` | 400 10px mono, uppercase, `--tracking-kicker` .16em | small labels above values ("TOTAL ITEMS") |
| `--type-meta` / `-meta-sm` / `-count` | mono 12/11.5/10.5px | metadata, counts |

Display text uses `--tracking-display` (-.01em), and the hero uses `--tracking-hero`.

All three fonts are SIL Open Font License faces. Self-host them, because the app must not load fonts from the network at runtime. The `@fontsource` npm packages for each face are one way to do this; check the exact package names before installing.

### Spacing, size, radius

- **Spacing:** `--space-1` to `--space-11` = 3, 6, 8, 10, 13, 16, 18, 20, 24, 28, 30px.
- **Layout:** `--header-h` 64px, `--sidebar-w` 248px, `--drawer-w` 440px, `--page-max` 1140px.
- **Radius:** generous. `--radius-xs` 7 to `--radius-3xl` 22px, plus `--radius-pill`.
  - Cards use `--radius-2xl` (18px).
  - Buttons and inputs use `--radius-md` (11px).
  - Tags and status pills use `--radius-pill`.

### Elevation and motion

- **Shadows:** soft and layered. `--shadow-card` and `--shadow-card-hover` for cards, `--shadow-popover`, `--shadow-modal`, `--shadow-toast`.
  - Colored shadows (`--shadow-cta`, `--shadow-primary`, `--shadow-success`, `--shadow-danger`) go only under a filled button of that color.
- **Motion tokens:** `--ease-spring`, with `--dur-fast` .15s, `--dur-base` .18s and `--dur-slow` .32s.
- **Keyframes:** `zdPulseDot`, `zdExpandIn`, `zdPopIn`, `zdToastIn`, `zdSpin`, `zdIndeterminate`, `zdShimmer`.
- **The system's own rule:** reveal animations use transform only, never opacity from 0.
- **Reduced motion:** honor `prefers-reduced-motion` by stopping loops and making reveals instant.

### Theme switching

- Light is the default.
- Dark mode is `<html data-theme="dark">`, which keeps the same hues, inverts the ink ramp and uses deep indigo-black grounds.

## 2. Components in the system

The export names these components. Props are as referenced in the export.

| Component | Props | What it is |
|---|---|---|
| `BrandMark` | none | rounded-square mark in `--gradient-mark` with a white ring glyph, product name in display type, mono kicker below |
| `NavGroupLabel` | children | mono kicker heading for a nav group |
| `NavItem` | `icon`, `label`, `active`, `badge` | sidebar row; active state uses `--tint-indigo` and `--accent-text` |
| `Card` | `variant`, `padding` | white card, `--radius-2xl`, `--shadow-card`, `--border-card` |
| `SegmentedTabs` | `items`, `value`, `on-change` | pill segments in a `--well` track; the active segment is a white raised chip |
| `LiveIndicator` | `label`, `pill` | `--tint-success` pill with a dot pulsing via `zdPulseDot`, label in mono `--success-text` |
| `Timeline` | `items`, `dense` | vertical event list |
| `LineChart`, `BarChart` | `series`, `labels`, `width`, `height` | charts in `--cat-*` colors |
| `DonutChart` | `data`, `label`, `legend`, `size`, `thickness` | ring chart |

The stat cards on the dashboard follow one consistent pattern:

1. a mono kicker
2. a large display number
3. a mono meta line in a status `*-text` color

## 3. Accessibility: measured, not assumed

Contrast was computed against white cards and the darkest stop of the app ground (`#e8eaf4`, dark `#191b2e`).

| Text token | Light, on card | Light, on ground | Dark, on card |
|---|---|---|---|
| `--text-strong` | 16.7 | 14.0 | 14.7 |
| `--text-body` | 8.3 | 6.9 | 8.8 |
| `--text-muted` | 5.0 | **4.2 fail** | 6.2 |
| `--text-subtle` | **3.2 fail** | **2.6 fail** | 4.6 |
| `--text-faint` | **2.4 fail** | **2.0 fail** | **2.9 fail** |
| `--success-text` | **4.35 fail** | **3.6 fail** | 8.8 |
| `--danger-text` | 4.9 | **4.1 fail** | 6.7 |
| `--warning-text` | 5.3 | **4.4 fail** | 9.0 |
| `--accent-text` | 7.0 | 5.9 | 7.6 |

Filled buttons with white text:

| Fill | Contrast |
|---|---|
| `--indigo-500` | 4.45 (fails just under 4.5) |
| the light end of `--gradient-cta` | 3.4 |
| `--success` | 3.45 |

Chimera Lab keeps its existing bar of 4.5:1 for all essential text. The ZD values stay as they are, and these usage rules apply:

1. Essential text sits on cards (`--surface-card`), not directly on `--ground-app`. Anything that must be read on the ground uses `--text-strong` or `--text-body`.
2. Kickers and meta text use `--text-muted` on cards. ZD's dashboard uses `--text-subtle` for kickers, which fails; do not copy that.
3. `--text-subtle` and `--text-faint` are only for disabled states, placeholders and decoration that carries no information.
4. **Success text in the light theme** needs a decision:
   - Use one Chimera deviation token, `--success-text-aa`, darkened only until it reaches 4.5:1 on white. Light theme only; dark keeps ZD's value. Log it in DECISIONS.md.
   - Or pair the success color with a glyph and put the words in `--text-body`.
5. **Filled indigo buttons** use `--indigo-600` or darker behind white text. Check the exact ratio in `contrast.test.ts`.
6. **The gradient** appears on the brand mark and nowhere else.
   - The gradient is decoration; the Fuse button is a solid fill that passes contrast.
   - Blue-violet gradients are the most common "generic AI tool" signal. Keeping the gradient to one spot is what stops this system from reading as a template.

Every deviation from ZD values gets a token whose name ends in `-aa` and a DECISIONS.md entry. Never edit `zd-tokens.css`.

## 4. Mapping onto Chimera Lab

| Chimera element | ZD treatment |
|---|---|
| App background | `--ground-app`. The canvas grid is a sparse dot grid in `--line-strong`, not graph paper. |
| Top bar | `--header-h`, `--surface-header` with `--blur-header`, bottom hairline `--line-strong`. Left: Chimera mark in the `BrandMark` style, with Chimera's own glyph and name, never the ZeroDistance name. Middle: canvas name in `--type-page`. Right: run status and theme toggle. |
| Tool rail | A floating vertical panel: `--surface-glass-strong`, `--blur-glass`, `--radius-2xl`, `--shadow-glass`. Icon buttons are 36px with `--radius-md`; the active one is `--tint-indigo` with `--accent-text`. |
| Nodes | `Card`: `--surface-card`, `--radius-2xl`, `--border-card`, `--shadow-card`, and `--shadow-card-hover` on hover. Selected adds `--focus-ring` and a 1px `--accent` border. Node chrome is a mono kicker (`INPUT A`, `FUSION`, `RESULT · V2`) plus a `--type-card-title` title. The image fills the card edge to edge at the top, clipped to the card radius. |
| Ports | Image ports are `--info` circles; creature ports are `--accent` diamonds. Keep shape coding, so meaning never depends on color alone. Edges are 1.5px `--ink-300`; an active edge is `--accent` with a dash animation that stops under reduced motion. |
| Fuse button | The single primary action: solid `--indigo-600` (or darker, see section 3), white `--type-button-lg`, `--radius-md`, `--shadow-primary`. |
| Run status | `LiveIndicator` pattern: running is a `--tint-indigo` pill with the pulse in `--accent`; done is `--tint-success`; long wait is `--tint-warning`; error is `--tint-danger`. Every state has a word, not just a color. |
| Pipeline steps | `Timeline` (`dense`) inside the Fusion node when expanded and in the drawer. The step name is in `--type-body-sm`; the duration is in `--type-meta`. |
| Versions | `SegmentedTabs` on the Result node (v1, v2, v3). |
| Result plate | The largest card on the canvas, with the image at full card width. The creature name is in `--type-h2`. The "Generated fusion" label is a pill: `--tint-indigo` with `--accent-text`. A real hybrid gets an `--info` pill. |
| Stats in the drawer | Stat-card pattern: kicker, display number, meta line. For example, match confidence, rules checked, warnings, tokens used. |
| Drawer ("How this was made") | `--drawer-w`, `--surface-modal`, `--shadow-modal`, `--scrim` with `--blur-scrim`, slide in with `--ease-spring` `--dur-slow`. |
| Popovers and contextual toolbar | `--surface-glass-strong`, `--blur-glass`, `--radius-lg`, `--shadow-popover`, `zdPopIn`. |
| Toasts | `--ink-900` ground with white text, `--radius-lg`, `--shadow-toast`, `zdToastIn`. |
| Loading | `zdShimmer` skeletons on image areas, `zdIndeterminate` for progress without a known length, `zdSpin` only for small inline spinners. |
| Tags and warnings | pill tags: `--tint-*` background with `--*-text` (see section 3 for the light-theme success rule). |

## 5. Implementation notes

- Copy `zd-tokens.css` into the `:root` and `[data-theme="dark"]` sections of `frontend/src/styles/theme.css`, unchanged. Add Chimera tokens after them, in a clearly labelled block that references ZD tokens rather than raw values.
- `scripts/check-css.sh` allows hex only in tokens. The ZD block counts as tokens.
- The `/* @kind ... */` comments are Claude Design metadata. Keep them; they are harmless.
