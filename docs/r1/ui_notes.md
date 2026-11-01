# R1 Stream B notes: the UI on the agent API (branch r1-ui)

## CONTRACT CHANGE REQUEST

None. The client implements `docs/api_contract.md` v1 as written.

Fixture request (not a contract change, nothing blocked): no fixture has `finalChoice.agree: false`, so the
mock adds one creature, `crt_mock_b10_split`, built from the b10 creature with the agent's pick moved to img3.
Its agent reason says it is constructed for the UI mock. A real disagreeing creature in `docs/api_fixtures/`
would let the both-picks view be shown with real data.

## What was built

- **Agent API client** (`src/evo/`): every endpoint in the contract. `http.ts` is the real transport: relative
  `/evo/...` URLs (same origin), `X-Session-Id` on every request, the error envelope, and the event stream read
  with `fetch` (EventSource can't send `X-Session-Id`). The stream resumes with `Last-Event-ID` and `?after=`,
  reconnects with backoff (1, 2, 4, 8, 15 s), treats 45 s of silence as a dead connection (the server pings every
  15 s), never delivers an event id twice, stops at `finalize`/`error`, and stops on 404.
- **Mock transport** (`src/evo/mock.ts`): fixture-backed and dev/test only. It imports `docs/api_fixtures/*.json`
  and replays a run's events on a compressed clock that is kept in `localStorage`, so reload and resume work.
  Choose a scenario with `?mock=<scenario>` (plus `?mockStep=<ms>` and `?mockHold=<event id>`) or
  `window.__chimera.mock.*` in test mode. The scenarios: success, host_tie, cap, error, queued, identify_choice,
  refused_human, refused_type, refused_size, refused_animal, refused_corrupt, cap_daily, limits_capped and
  rate_limited. A fixture run id opened directly (`?run=run_fx_success`) replays as a finished run. The Vite dev
  server serves the fixture images at `/__fixtures/` (`vite.config.ts`, `apply: "serve"`), so nothing is copied.
  `VITE_EVO_TRANSPORT=http` in dev uses the real backend and forwards `?mock=` as `X-Mock-Scenario`.
- **Production builds** always use the http transport. The mock, the fixtures and `X-Mock-Scenario` are
  dead-code-eliminated: `dist` contains no `run_fx`, `__fixtures` or `mockConfig`. `check-bundle.sh` passes.
- **Gallery is the first screen** (`/`), with one action, "Make a new creature". The limits line ("38 of 50 live
  runs left today…", "about 5 minutes") comes from `GET /evo/agent/limits`. When runs are capped, the cap card and
  a disabled action show before anything is uploaded.
- **Lab** (`/?view=lab`): the U1 canvas. Two photos or two typed names go into a Fusion node; the mode is a
  Realistic / Speculative / Mythic segmented control; the one primary action is "Make creature".
- **Live trace** (`/?run=<id>`): docked beside the canvas, and full screen under 1024 px.
  - "Now" card: queued position and runs ahead, running with tool calls and renders against the caps, the
    5-minute expectation, and a reconnecting notice.
  - The host-tie question card (answer buttons and an expiry countdown) sits above the log.
  - The log shows every step as it streams: a plain verb for the tool, the agent's reason in its own words, a
    smaller summary, renders as thumbnails captioned "Generated fusion" with their verdict, and inspections with
    their failures and hidden-check count. The ask, the cap notice, the final pick and the error are rows too.
  - Finished: the creature leads (image, Generated fusion, host and who chose it, Can-it-live summary, failing and
    hidden checks, "Open creature card"). Failed: the error in plain words, with Try again or Make a new creature.
- **Resume**: events are cached per run in `localStorage` (a gap-free prefix only). After a reload, the cached trace
  shows at once and the stream continues from `?after=<last id>`. With no cache (another device) it replays from 0.
  A finished run that is fully cached doesn't open a stream at all.
- **Creature card** (`/?creature=<id>`):
  - The hero image, with "Generated fusion" and "Not a real animal".
  - The anatomy map switch swaps in `overlayUrl`, cropped to the same square so nothing moves. The legend lists
    role, parent and parts, plus the parts that were not located, and its swatches use the API's own `colors`.
  - Real hybrid gets a separate info pill and note.
  - Host, with who chose it, the tie note and the reason.
  - Can it live: functions with pass/fail glyph and word, and licenses.
  - Failing checks by kind, and "N checks hidden until reviewed" with the reason.
  - Both picks, the agent's first, only when `agree` is false.
  - Every image the agent made, the stats, and links to the trace and to make a new creature.
- **needs_choice**:
  - Identify: a modal dialog from the POST response with the photo, the options with confidence, "Something
    else" with a name field, and Cancel. Confirming posts again with names only.
  - Host tie: the question card, `POST /choice`, a countdown to `expiresAt`. A 409 says the agent decided itself.
- **Refusals** (HUMAN_DETECTED, NOT_AN_ANIMAL, UNSUPPORTED_FILE, FILE_TOO_LARGE, IMAGE_CORRUPT) show their own
  title and fix on the Fusion node, flag the photo named by `details.slot`, and also toast on narrow screens.
  `429 CAP_REACHED` switches the whole app to the capped state, with the reset time in UTC. `RATE_LIMITED` counts
  down and retries. The per-run `cap_reached` event is a notice, not an end.
- **Result node** shows the latest attempt while the agent works ("Latest attempt · img2 · Generated fusion"),
  then the finished creature with its pills, the Can-it-live line, the versions and "Open creature card".
- **v1 fusion path removed from the UI**:
  - The v1 run store and polling transport, the asset upload queue, the "How this was made" drawer, the anatomy
    pin diagram, the Field card node and the server graph save are gone.
  - Photos stay on the device until a run starts, and are sent once with the POST.
  - Saved canvases migrate: images keep their local copy, and v1 runs and versions are dropped. Old Field card
    nodes show the "unsupported" placeholder.
- **Mobile**: the gallery, trace and creature card are laid out for 390 px; the canvas stays desktop-first and no
  longer forces `min-width: 1024px`.

## Files

- New:
  - `src/evo/{types,transport,http,sse,mock,index,runs,data}.ts`
  - `src/app/route.ts`
  - `src/screens/{GalleryPage,CreaturePage,LabView}.tsx`
  - `src/trace/{TracePanel,TraceLog,ChoiceCard,time}.tsx|ts`
  - `src/nodes/fusion/{start.ts,IdentifyDialog.tsx}`
  - `tests/unit/evo.test.ts`
  - `tests/component/screens.test.tsx`
  - `tests/e2e/{fixtures,resume}.spec.ts`
  - `tests/visual/capture.ts`, rewritten as the R1 matrix
- Rewritten:
  - `src/app/{App,TopBar}.tsx`, `src/api/{client,errorMessages}.ts`
  - The Fusion, Result and image-input nodes
  - `src/copy.ts`, `src/test-hooks/install.ts`, `src/main.tsx`
  - `tests/e2e/{a11y,resilience,helpers}.ts`, `tests/component/flows.test.tsx`
  - `playwright.config.ts` (Vite only, no backend), `vite.config.ts` (the fixture image middleware)
- Removed:
  - `src/runs/`, `src/app/SidePanel.tsx`, `src/nodes/field-card/`
  - `src/nodes/result/{Panel,summary}.tsx|ts`, `src/nodes/fusion/{BodyDiagram,bodyRegions}`
  - `src/nodes/image-input/uploads.ts`, `src/ui/{Timeline,Section}.tsx`
  - The v1 e2e specs (happy, faults, visual), the 4 v1 baselines, `tests/visual/liveSeed.ts`, and the v1-only
    component and unit tests
- `src/styles/theme.css`: the R1 screens section, with no new colour tokens and the ZD block untouched. The only new
  tokens are layout ones: `--trace-w` and `--gutter`.

## Decisions

1. **Query-string routes on `/`** (`?view=lab`, `?run=`, `?creature=`). The backend serves the SPA at `/` and owns
   the `/evo`, `/health`, `/runs`, `/graphs` and `/assets` prefixes, so no client path can collide with the API.
2. **Read the event stream with `fetch` rather than EventSource**, because EventSource can't send `X-Session-Id`.
   Both `Last-Event-ID` and `?after=` are sent.
3. **Cache the trace locally and resume with `?after=`**, so a reload shows the trace instantly and costs one short
   replay. Only a gap-free prefix is trusted.
4. **Pick the mock transport in the client**, not with a mock backend. It needs no server, every fixture is
   reachable, and e2e runs only Vite (port 5174). The dev mode can still point at Stream A's mock backend.
5. **Serve fixture images with a Vite dev middleware.** They never enter the production bundle.
6. **Photos are not uploaded until a run starts.** The contract discards images after identification, and the v1
   asset store would have kept them. HEIC is converted in the browser when possible and refused otherwise, because
   the API takes JPEG, PNG or WebP. PNGs over 8 MB are re-encoded as JPEG.
7. **Name fallback lives on the Fusion node**: a slot with no photo shows a name field. This is a small deviation
   from U1's "no form fields on the card", because the name is the action's input and has to work by keyboard.
8. **Parent slots are stacked** (A above B), so long names and inputs fit in the 320 px node. The ports were moved
   to match.
9. **The trace is docked as a grid column**, not an overlay drawer, so the canvas stays visible beside it. Under
   1024 px it takes the screen and "Hide trace" returns to the canvas.
10. **The Now card and the question stay pinned above the scrolling log.** Following new steps never hides the
    status or the question. When the run ends, the log scrolls back to the creature.
11. **Legend swatches use the API's `anatomyMap.colors` as SVG `fill`**, with no hex in CSS and no inline style, so
    they always match the overlay image. Every swatch also has a role word and a parent name.
12. **The overlay is cropped to the creature's square** (`object-position: top`). The overlay image carries a
    baked-in legend strip below; the UI draws its own readable legend instead, so toggling never shifts the layout.
13. **Error and cap wording follows the contract**, kept in `errorMessages.ts` and `copy.ts`. Raw server text is
    never shown. `CAP_REACHED` shows the reset time from `details.resetsAt`.
14. **Refusals also toast on viewports under 1024 px**, where the zoomed-out canvas makes the node text too small.
15. **The mock adds one constructed both-picks creature** (`crt_mock_b10_split`), labelled as constructed. See the
    fixture request above.
16. **The mock rebases event times to the replay clock**, so elapsed times and the host-tie expiry are real.
    `expiresAt` keeps the fixture's offset of about 120 s.

## Defects found in screenshot review, and fixes

| # | Screen | Severity | Defect | Fix |
|---|---|---|---|---|
| 1 | Trace mid-run (1440) | Major | Auto-follow scrolled the status card out of view | Now card and question pinned above the log |
| 2 | Trace finished | Major | Panel stayed scrolled to the bottom, so the creature was hidden | Scroll to top when the run ends |
| 3 | Fusion node with names | Major | Side-by-side name fields truncated "Indian p…" | Slots stacked; ports re-aligned |
| 4 | Lab mid-run | Major | Result hero was a blank grey square for the whole run | Shows the latest attempt, labelled Generated fusion |
| 5 | Daily cap (lab) | Minor | Cap said twice (hint plus error) and "tomorrow" was vague | Hint hidden when the error says it; reset time in UTC |
| 6 | Creature card host block | Minor | Flex lead broke "Host: horse." onto its own line | Block text |
| 7 | Host-tie buttons, identify options | Minor | Forced capitalisation ("Domestic Goat") | Names shown as the API gives them |
| 8 | Lab empty (390) | Major | Empty-state card under the tool rail | Card offset past the rail on narrow screens |
| 9 | Fit to view | Minor | Zoomed a lone node to 159% | `maxZoom: 1` |
| 10 | Refused upload (390) | Major | The node's error was unreadable at 53% zoom | Toast on narrow viewports |
| 11 | axe: trace | Serious | `role="log"` on the `<ol>` broke list semantics; scroll regions not focusable | Log role on a wrapper; regions are focusable and labelled |
| 12 | Queued (mock) | Blocker for the shot | The snapshot said "running" before the first event | Mock snapshot uses the POST status until the first event |

Open minors, not fixed:
- At 390 px, fit-to-view can leave the Fusion node's left edge under the floating tool rail. The canvas is
  desktop-first by design; the gallery, trace and card are the mobile path.
- In mock mode, the elapsed timer reads 00:00 to 00:05 because the replay clock is compressed.

## Screenshots (reviewed)

All files are in `docs/r1/ui_shots/<viewport>/<theme>/`, at 1440x900 and 390x844 in light and dark, 60 PNGs in all.
They were shrunk with `scripts/shrink_shots.py` (19.5 to 7.1 MB); the list is in `manifest.json`.

| Shot | State |
|---|---|
| 01 | gallery |
| 02 | new creature (photos) |
| 03 | new creature (names) |
| 04 | queued |
| 05 | trace mid-run |
| 06 | host tie |
| 07 | identify |
| 08 | refused (HUMAN_DETECTED) |
| 09 | daily cap (POST 429) |
| 10 | capped gallery (limits) |
| 11 | error |
| 12 | trace finished |
| 13 | card, overlay off |
| 14 | card, overlay on |
| 15 | both picks |

Regenerate them from `frontend/` with `npm run shots`. It uses Vite on port 5175 and the mock, with no backend.

## Tests

| Suite | Result | Notes |
|---|---|---|
| `npx vitest run` | **189 passed** (14 files) | Baseline 193; v1-only tests removed, R1 tests added |
| `npx playwright test` | **40 passed** | Mock transport, no backend |
| `npx tsc --noEmit` | clean | |
| `check-css.sh` | passes | |
| `check-bundle.sh` | passes | |

New vitest coverage:
- SSE parsing.
- The http stream: Last-Event-ID and `?after=`, reconnect without duplicates, 404, a finished run that replays
  nothing.
- `deriveRun` for every run fixture.
- The mock: replay, host tie answer and timeout, hold, direct fixture ids, identify, every refusal and cap, limits,
  gallery and creatures.
- Routes.
- The start flow: names, photos, refusals with flags, the cap, identify, double click.
- Gallery, creature card, trace panel and Fusion node components.

Playwright:
- One test per fixture: gallery, limits, creature_b09, run_success, run_host_tie, identify_choice (confirm and
  cancel), run_cap, run_queued, upload_refused (5 codes), cap_daily, run_error, unknown run, both picks.
- Resume: reload mid-run with no duplicate rows, coming back to a finished run, a fixture run on another device,
  the host-tie question surviving a reload, the top-bar link back to a run.
- axe with 0 serious or critical issues in light and dark on these states: gallery, card with overlay, both
  picks, empty lab, queued, host tie, finished trace, identify dialog, refused, error, capped gallery, offline.
- A keyboard-only walkthrough from the gallery through the host-tie answer to the card's anatomy toggle.
- Hit targets.
- No overflow or clipping at 390, 1024 and 1440 px.
- Resilience: offline, unreachable, corrupt or broken saves, read-only, crash boundaries, client file checks,
  same photo twice, rate limit with retry.

## Not done or blocked

- Not run against Stream A's backend. The client follows the contract, and `VITE_EVO_TRANSPORT=http` with
  `VITE_API_BASE_URL` points dev at it.
- No new visual baselines (`toHaveScreenshot`). The v1 ones no longer applied, and the lead plans a recolour, which
  would invalidate new ones at once. The reviewed screenshot matrix stands in for now.
- The colour palette is unchanged, as the lead asked.
