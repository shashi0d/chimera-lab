# Chimera Lab U1 design: ZD

U1 replaces the "Field paper" identity (docs/DESIGN.md, kept for history) with the ZD design system (`docs/design-system/ZD.md`, `zd-tokens.css`). The visual language changes, the behaviour doesn't:
- **Unchanged:** backend, API contracts, node registry, test hooks and the state matrix.
- **Changed:** what a node is, where controls live, and how a result explains itself.

## Principles

1. **The photo is the node.** Inputs and results lead with their image, edge to edge. Text describes the image; it doesn't wrap it in a form.
2. **The result is the hero.** The creature card is the biggest thing on the canvas, about 2× an input card. Its name is in `--type-h2`, and two pills say what it is (generated) and what it resembles (a real hybrid).
3. **Controls on demand.** Nothing interactive sits permanently on a card except the one primary action (Fuse). Everything else lives in a glass contextual toolbar that appears on hover, selection or keyboard focus.
4. **Explain, then evidence.** The drawer opens with a plain summary written from structured fields. Numbers and sources follow in stat cards and collapsible sections. The planner's prose is a footnote.
5. **One gradient.** `--gradient-mark` is used on the brand mark and nowhere else (ZD §3.6). Every action is a solid fill that passes 4.5:1.

## Token usage

`theme.css` section 1 is `zd-tokens.css` verbatim (light `:root`, dark `[data-theme="dark"]`, base rules, keyframes). Section 1b holds Chimera tokens: layout sizes plus the four `-aa` deviations, all defined by reference to ZD tokens except where a darker value is required.

| Need | Token |
|---|---|
| App ground / canvas | `--ground-app`; dot grid `--line-strong` at 28px |
| Cards (all nodes) | `--surface-card`, `--radius-2xl`, `--border-card`, `--shadow-card` (hover `--shadow-card-hover`); selected adds `--focus-ring` + 1px `--accent` |
| Glass (tool rail, contextual toolbar, zoom) | `--surface-glass-strong`, `--blur-glass`, `--shadow-glass` / `--shadow-popover` |
| Header | `--header-h`, `--surface-header`, `--blur-header`, hairline `--line-strong` |
| Drawer | `--drawer-w`, `--surface-modal`, `--shadow-modal`, `--radius-3xl`, `--ease-spring` `--dur-slow`. No scrim: the drawer is non-modal and the node it explains stays in view (D-048). The modal shortcuts dialog uses `--scrim` + `--blur-scrim`. |
| Titles | `--type-card-title` (nodes), `--type-h2` (creature name), `--type-page` (canvas name), `--type-h1` (empty state) |
| Body | `--type-body` / `--type-body-sm`; captions `--type-caption` (12px, the floor) |
| Kickers | `--type-kicker` + `--tracking-kicker`, uppercase, **always `--text-muted` on a card** |
| Meta, timers, counts | `--type-meta` (12px mono) |
| Primary action (Fuse) | solid `--indigo-600`, white `--type-button-lg`, `--radius-md`, `--shadow-primary` (5.5:1). Hover lifts the button and keeps the fill; dark `--indigo-700` would be 2.2:1 (D-046). |
| Ports | image: `--info` circle; creature: `--accent` diamond |
| Edges | 1.5px `--ink-300`; active: `--accent`, dashed and animated (stops under reduced motion) |
| Status | `LiveIndicator`: running `--tint-indigo`/`--accent`; done `--tint-success`/`--success-text-aa`; waiting `--tint-warning`/`--warning-text`; error `--tint-danger`/`--danger-text-aa`. Every state has a word. |
| Donor identity A/B | `--cat-blue` (A) and `--cat-teal` (B). Always paired with the letter A/B and the parent's portrait, never colour alone. |

### Deviations (`-aa`, see DECISIONS D-045)

| Token | Light | Dark | Why |
|---|---|---|---|
| `--success-text-aa` | `#147a52` | `var(--success-text)` | ZD success text is 4.35:1 on white and 3.9:1 on its own tint |
| `--danger-text-aa` | `#bf3b45` (4.87:1 on its tint) | `var(--danger-text)` | ZD danger text is 4.43:1 on its tint |
| `--toast-bg-aa` / `--toast-text-aa` | `var(--ink-900)` / `var(--white)` | `var(--surface-modal)` / `var(--text-strong)` | ZD's dark ink-900 is near-white, so white toast text would be 1.1:1 |

## Components (new or rebuilt, `frontend/src/ui/`)

| Component | ZD source | Used for |
|---|---|---|
| `Card` | Card | every node, drawer stat cards, empty state |
| `BrandMark` | BrandMark | top bar: gradient rounded square with Chimera's own glyph (two joined forms), "Chimera Lab", kicker "FUSION LAB" |
| `SegmentedTabs` | SegmentedTabs | Result versions (v1 / v2 / v3), as a radiogroup |
| `LiveIndicator` | LiveIndicator | run and upload status on nodes and in the top bar |
| `Timeline` | Timeline (`dense`) | pipeline steps in the Fusion node and the drawer, with per-step duration |
| `StatCard` | dashboard stat pattern | drawer: kicker, display number, meta line; shows "unknown", never 0, when missing |
| `Pill` | tags | "Generated fusion", "Real hybrid: tigon", "Unverified", warnings |
| `Section` | n/a (`<details>`) | collapsible drawer sections |
| `ContextToolbar` | popover | glass toolbar above a selected or hovered node |
| `BodyDiagram` | n/a (Chimera) | anatomy pins on a silhouette drawn from a region list |

## Canvas

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│ [◆] Chimera Lab        Untitled canvas · saved          ● Running 00:12   ◐   ?   │ glass header 64
│     FUSION LAB                                                                     │
├──┬─────────────────────────────────────────────────────────────────────────────────┤
│▣ │   ·     ·     ·     ·     ·     ·  (sparse dots)  ·     ·     ·     ·           │
│◎ │  ┌─────────┐                                                                    │
│──│  │ [photo] │●─╮      ┌───────────────┐       ┌──────────────────────────┐      │
│↶ │  │ INPUT A │  ╰─────◇│ FUSION        │◆─────◇│ [         creature        ]│     │
│↷ │  │ Lion    │         │ (A)Lion (B)Tig│       │ [          image          ]│     │
│──│  └─────────┘  ╭─────◇│ [body diagram]│       │ RESULT · V2               │      │
│⤢ │  ┌─────────┐  │      │ ● Done · 29s  │       │ Maned Striped Panther      │ h2   │
│▦ │  │ [photo] │●─╯      │ [   Fuse    ] │       │ (Generated fusion)(Real hybrid: tigon) │
│  │  │ INPUT B │         └───────────────┘       │ [v1|v2]      How this was made │   │
│  │  │ Tiger   │                                 └──────────────────────────┘      │
│  │  └─────────┘                                                     [- 100% +]   │
└──┴─────────────────────────────────────────────────────────────────────────────────┘
  glass tool rail                                                     glass zoom
```

## Nodes

```
Input (240w)              Fusion (300w)                    Result (≥ 2× input: 500w)
┌──────────────┐          ┌──────────────────────────┐     ┌──────────────────────────────────┐
│              │          │ FUSION          ● Ready  │     │                                  │
│   photo      │          │ Fusion                   │     │                                  │
│  (4:3, bleeds│          │ (A)◉ Lion   (B)◉ Tiger   │     │        creature (1:1, bleeds)    │
│  to radius)  │          │ ┌──────────────────────┐ │     │                                  │
│ [Uploading ▬]│          │ │   body diagram       │ │     │                                  │
├──────────────┤          │ └──────────────────────┘ │     ├──────────────────────────────────┤
│ INPUT A      │          │ Timeline (while running) │     │ RESULT · V2                      │
│ Lion         │ ← species│ ● Done · 8 steps · 29s   │     │ Maned Striped Panther      (h2)  │
│ 1600 × 1600  │          │ [        Fuse          ] │     │ (Generated fusion) (Real hybrid…)│
└──────────────┘          └──────────────────────────┘     │ [v1 | v2]       How this was made│
                                                           └──────────────────────────────────┘
```

- **Input title:** the species identified in the latest run (looked up by asset id in run specs), else "Animal photo". The filename is never the title; it moves to the photo's alt text. The kicker names the slot it feeds ("INPUT A").
- **Fusion inputs:** small circular portraits with species names, not dropdowns. Reassignment lives in the contextual toolbar.
- **The Fusion node has no result thumbnail.** It shows status, the Timeline (open while running or failed, behind "Show steps" when done) and Fuse.

## Contextual toolbar

```
          ┌────────────────────────────────────────────┐
          │ A [Lion ▾]  B [Tiger ▾]  ⇄   ⤓card  🗑     │   glass, zdPopIn, above the node
          └────────────────────────────────────────────┘
          ┌──────────────────────────┐
          │ FUSION …                 │
```

- **Contents per node:**
  - Input: Replace, Remove.
  - Fusion: slot selectors "Connect image A/B" (the keyboard path), Swap A and B, Reset to Auto.
  - Result: Make field card.
- **Stays on the card:** each node's one primary action: Fuse (Fusion), How this was made (Result), Write card / Download PNG (Field card). See D-047.
- **When it shows:** visible on hover, when the node is selected, and on `:focus-within` (so it is reachable by Tab). Hidden with opacity and a transform, never `display:none`, so it stays in the accessibility tree.

## Body diagram

```
             ┌──(Head)──┐
     tail ~~ │  ◯  head │      each region: role=button, aria-label "Head from A",
   ┌─(Tail)─ ├──────────┤      fill: Auto = dashed well; A = cat-blue tint; B = cat-teal tint
   │         │  covering│ ← dorsal band
   │         │   body   │      pinned regions show the donor's circular portrait + letter
   │         └┬──┬──┬──┬┘
   │          │  │  │  │  ← limbs
   └──────────┴──┴──┴──┘
   Auto · A · B   (legend)
```

Regions come from `BODY_REGIONS` (id, outline path, optional hit path, label point, badge point). Adding wings in L2 means one new entry plus a path, not a redraw. Click, Enter or Space cycles Auto → A → B. The diagram is hidden while a run is active, since pins can't change then.

## Drawer: "How this was made"

```
┌─────────────────────────────────────────── 440 ┐
│ HOW THIS WAS MADE                          [×] │
│ Maned Striped Panther                  v2 of 2 │
│ (Generated fusion)                             │
│                                                │
│ A tiger body and coat with a lion's head and   │  ← summary (frontend-built)
│ tail. Real hybrids of these parents exist      │
│ (liger, tigon). No anatomy warnings.           │
│                                                │
│ ┌───────────┐ ┌───────────┐                    │
│ │MATCH · A  │ │MATCH · B  │                    │  ← stat cards
│ │100%       │ │99%        │                    │
│ │Lion · T1  │ │Tiger · T1 │                    │
│ ├───────────┤ ├───────────┤                    │
│ │RULES      │ │WARNINGS   │                    │
│ │44 / 130   │ │0          │                    │
│ ├───────────┤ └───────────┘                    │
│ │TOKENS     │                                  │
│ │28,641 / unknown                              │
│ └───────────┘                                  │
│ ▸ Pipeline (8 steps · 29s)                     │  ← <details> sections
│ ▸ Real hybrids (2)                             │
│ ▸ Rules and warnings (5)                       │
│ ▸ Mythology resemblances (1)                   │  "Resembles griffin (Greek) [Unverified]"
│ ▸ Body plan and donors                         │
│ ▸ Planner notes                                │
│ ▸ Prompt and sources                           │
└────────────────────────────────────────────────┘
```

## Motion

The ZD keyframes, used as follows:
- `zdPopIn`: contextual toolbar, popovers
- `zdToastIn`: toasts
- `zdPulseDot`: LiveIndicator dot
- `zdShimmer`: image skeletons
- `zdIndeterminate`: unknown-length progress
- `zdSpin`: small inline spinners

Reveals are transform only. Under `prefers-reduced-motion`, every loop stops and every reveal is instant.

## Room for L2 (not built now)

- **Wings slot:** `BODY_REGIONS` and the anatomy pin map are keyed by region id. The drawer's donor list iterates the regions.
- **Short plan summary:** `summarize(spec)` lives in `nodes/result/summary.ts`. A backend summary field, when it exists, replaces its output in one place.
- **Cost:** the stats grid takes an optional cost card that shows "unknown" until a field exists.
