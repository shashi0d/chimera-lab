# Chimera Lab agent API contract (R1)

Version 1, 2026-11-01. Owner: the lead agent. A stream that needs a change stops and reports to the lead; the lead
updates this file and `docs/api_fixtures/`, and the other streams pull.

## Basics

- **One origin.** The backend is one FastAPI app (uvicorn). It serves the built frontend at `/` and the API under
  `/evo`. The frontend calls relative URLs (`/evo/...`), so no CORS setup is needed in production. The
  CORS middleware stays for local dev with two ports.
- **Session.** Every request carries `X-Session-Id` (a random id kept in localStorage; D-017). The visitor
  identity for caps is that id plus the client IP. It is not authentication.
- **Field names.** API-level fields are camelCase. Objects copied from the engine (`card`, `plan`) keep the engine's
  snake_case. The UI reads only the derived camelCase fields documented here; it never parses `card` or `plan`
  internals.
- **Errors.** Every non-2xx response uses the existing envelope:
  `{"error": {"code", "message", "retryable", "retryAfterMs"?, "details", "errorId"?}}`. The codes are the
  existing `ErrorCode` list, plus one new code, `CAP_REACHED`.
- **Image URLs.** These are strings the browser can load directly: a Supabase public URL, or a path under
  `/evo/files/...` served by the backend from local storage. In fixtures, image URLs are relative to
  `docs/api_fixtures/`, for example `images/b09_img1.jpg`.
- **Generated fusion.** Every creature is generated. Responses carry `generatedLabel: "Generated fusion"`, and
  `realHybrid: true` when the pair is a documented real hybrid (labelled separately in the UI).

## Endpoints

### POST /evo/agent/runs

Starts an agent run. The body is `multipart/form-data`:

| field | type | notes |
|---|---|---|
| `mode` | `realistic` \| `speculative` \| `mythic` | required |
| `sireImage`, `damImage` | file | JPEG, PNG or WebP, at most 8 MB each |
| `sireName`, `damName` | string | used when no image is sent for that slot, and to confirm an identify choice |

Each slot needs an image or a name. Images are checked (type, size, decodable), resized before any model call,
identified with the v1 identify step, and then discarded: they are never stored. Only the identified names go to
the job.

Responses:

- `202 Accepted`, the run was created:
  `{"runId", "status": "queued"|"running", "position": int|null, "eventsUrl", "runUrl", "sire": Parent, "dam": Parent, "mode"}`.
  - `Parent` is `{"commonName", "scientificName"|null, "source": "image"|"name", "confidence"|null}`.
  - `position` is the 1-based place in the queue (null when running).
- `200 OK` with `"status": "needs_choice"` when identification is not confident:
  `{"status": "needs_choice", "choice": {"kind": "identify", "slot": "sire"|"dam", "question", "options": [{"commonName", "scientificName", "confidence"}], "allowOther": true}, "identified": {"sire": Parent|null, "dam": Parent|null}}`.
  No run is created. The client posts again with `sireName` / `damName` set to the chosen or confirmed names (no
  images needed).
- `422`, a refused upload:
  - `HUMAN_DETECTED`: "This looks like a photo of a person. Chimera Lab only uses animal photos."
  - `NOT_AN_ANIMAL`: "We couldn't find an animal in this image."
  - `UNSUPPORTED_FILE`: "Use a JPEG, PNG or WebP image."
  - `IMAGE_CORRUPT`
  - `VALIDATION_FAILED`: missing slot or bad mode.
  - `details.slot` names the slot.
- `413 FILE_TOO_LARGE`: "Images must be 8 MB or smaller." (`details.slot`, `details.maxBytes`)
- `429 CAP_REACHED`: `details: {"scope": "daily_total"|"visitor_daily", "limit", "resetsAt"}`. The message is plain:
  "Today's live creature runs are used up. The gallery is still open; new runs open again at <time> UTC."
- `429 RATE_LIMITED`, the per-IP rate limit (`Retry-After` header, `retryAfterMs`).

Mock mode only: the header `X-Mock-Scenario` selects what the run does, so the UI can be tested end to end against
every fixture:
- `success` (the default)
- `host_tie`: the agent asks the user to choose the host
- `cap`: the run stops at the render cap
- `error`: the run fails mid-way
- `queued`: the run waits in the queue behind 2 runs before starting
- `identify_choice`: the POST returns needs_choice
- `refused_human`, `refused_type`, `refused_size`: the POST returns the refusal

### GET /evo/agent/runs/{runId}

A snapshot of the run:
`{"runId", "status", "position", "sire", "dam", "mode", "createdAt", "updatedAt", "lastEventId", "creatureId"|null, "error"|null, "pendingChoice"|null}`.

- `status` is one of `queued`, `running`, `needs_choice`, `succeeded`, `failed`, `interrupted`.
- `404 RUN_NOT_FOUND` when the run does not exist.

### GET /evo/agent/runs/{runId}/events

Server-sent events (`text/event-stream`):

- **Resuming.** The stream starts after `Last-Event-ID` (header) or `?after=<id>` (query; the header wins). It first
  replays every stored event with a larger id, then streams new events live.
- **Keep-alive.** A comment line (`: ping`) is sent every 15 s.
- **End.** The stream closes after a terminal event (`finalize` or `error`). A client that reconnects after the end
  gets the replay and an immediate close.

### POST /evo/agent/runs/{runId}/choice

Answers a pending `needs_choice` event. The body is `{"choiceId", "answer"}`, where `answer` is one of the options.

- `200`: `{"accepted": true}`.
- `409 VALIDATION_FAILED`: the choice was already answered or has expired. When a choice expires, the agent decides
  itself and says why.

### GET /evo/agent/limits

`{"liveRuns": "open"|"capped", "dailyTotal": {"used", "limit", "resetsAt"}, "visitor": {"used", "limit"}, "concurrent": {"running", "limit", "queued"}}`.
The UI uses it to show the capped state before the user uploads anything.

### GET /evo/creatures/{creatureId}

Returns a `Creature`:

```
{
  "creatureId", "createdAt", "title", "sire": Parent, "dam": Parent, "mode",
  "generatedLabel": "Generated fusion", "realHybrid": bool, "showcase": bool,
  "imageUrl",
  "host": {"commonName", "reason", "tie": bool, "chosenBy": "agent"|"user"|"code"},
  "canItLive": {"summary", "functions": [{"function", "result", "detail"}], "licenses": [{"rule", "compensation"}]},
  "remainingFailures": [{"key", "kind": "structural"|"covering", "text"}],
  "hiddenChecks": int,
  "finalChoice": {"shownFirst": "agent", "agree": bool,
                  "agentPick": Pick, "codePick": Pick},
  "anatomyMap": {"overlayUrl", "colors": {"host", "donor", "blend"},
                 "parts": [{"part", "parent", "parentRole": "host"|"donor"|"blend", "status": "found"|"not located", "color"|null, "maskArea"}]},
  "images": [{"imageId", "url", "kind": "render"|"edit"|"growth_host"|"growth", "verdict": "pass"|"fail"|null}],
  "runId"|null, "stats": {"renders", "edits", "toolCalls", "seconds"},
  "card": {...engine card...}, "plan": {...engine plan...}
}
```

- `Pick` is `{"imageId", "imageUrl", "rank", "of", "structural", "failures", "reason"}`. The UI shows both picks,
  the agent's first, only when `agree` is false.
- `hiddenChecks` counts the material-only critic checks (`material_look`, `host_cover_kept`, `donor_pieces`). They
  are removed from `remainingFailures` and from the card until those items have owner labels.

### GET /evo/gallery

`?limit=24&cursor=<opaque>` returns `{"items": [GalleryItem], "nextCursor"|null}`.

- `GalleryItem` is `{"creatureId", "title", "sire", "dam", "mode", "imageUrl", "showcase": bool, "createdAt"}`.
- Showcase creatures come first, in their configured order, then the newest runs.
- The gallery works when live runs are capped.

### GET /evo/files/{key}

Local storage only: serves a stored image (`Cache-Control: public, max-age=31536000, immutable`). With Supabase,
image URLs point at the public bucket instead.

## Server-sent event schema

Every event is one SSE message:

```
id: <int>
event: <type>
data: <json>
```

The JSON always has `{"id", "type", "runId", "at"}` (`at` is an ISO 8601 UTC time) plus the payload below.

- **Ids.** They start at 1 and increase by 1 within a run, with no gaps. They are stored with the run, so a replay
  is identical.
- **Pairing.** For one tool call, the `step` event comes first. A `render` or `inspect` event with the same `n`
  follows it and carries the richer payload.

| type | payload | when |
|---|---|---|
| `queued` | `position` (1-based), `ahead` (runs before this one) | at creation when the concurrent limit is full, and each time the position changes |
| `started` | `sire`, `dam` (`Parent`), `mode`, `caps: {"renders", "toolCalls", "seconds"}` | the run leaves the queue |
| `step` | `n`, `tool`, `args` (short: each value cut to 120 characters), `summary`, `reason`, `cards` (e.g. `["RC-R10-01"]`), `ok`, `error`\|null (a refusal code) | after every tool call |
| `render` | `n`, `imageId`, `url`, `kind`, `parent`\|null, `method`, `rendersUsed`, `rendersLeft` | after a render or edit adds an image (a growth render sends two: the host image, then the grown one) |
| `inspect` | `n`, `imageId`, `verdict`, `failures: [{"key", "kind", "text"}]`, `hiddenChecks`, `bestSoFar`, `rule`\|null | after an inspect (material-only checks are removed as on the card) |
| `needs_choice` | `n`, `choiceId`, `kind: "host_tie"`, `question`, `options: [string]`, `expiresAt` | the agent called `ask_user`; the run waits until answered or expired (default 120 s). The `ask_user` `step` event (with the answer in `summary`) follows `choice_resolved` |
| `choice_resolved` | `choiceId`, `answer`\|null, `by: "user"\|"timeout"` | the choice is answered or expires |
| `cap_reached` | `scope: "renders"\|"tool_calls"\|"time"`, `limit`, `message` | a per-run cap is reached. Not terminal: the run then finalizes its best image. `time` fires at 14 minutes, and the runner stops the run at 15. |
| `finalize` | `creatureId`, `imageId`, `imageUrl`, `remainingFailures`, `hiddenChecks`, `agree`, `stop` (who finalized and why) | terminal, success |
| `error` | `code`, `message`, `retryable` | terminal, failure (an upstream error, a budget stop, an interruption) |

Daily and visitor caps are refused at `POST` (`429 CAP_REACHED`); they are never an event.

## Caps (configurable; defaults)

| setting | default | env |
|---|---|---|
| agent runs per day, all visitors | 50 | `EVO_DAILY_RUNS` |
| agent runs per visitor per day | 3 | `EVO_VISITOR_DAILY_RUNS` |
| concurrent runs (more are queued) | 3 | `EVO_MAX_CONCURRENT_RUNS` |
| POST /evo/agent/runs per IP per minute | 5 | `EVO_RUNS_PER_MINUTE_PER_IP` |
| per-run renders / tool calls / edits | 4 / 30 / 6 | `evo_config.json` `agent` (S3c) |
| agent finalizes its best image at | 14 min | `EVO_RUN_SOFT_SECONDS` (840) |
| runner stops the run at | 15 min | `EVO_RUN_HARD_SECONDS` (900) |
| identify-choice and host-tie choice wait | 120 s | `EVO_CHOICE_SECONDS` |
| showcase creatures | b09, b01, b03, b08, b11, b05 (S5 agent images) | `EVO_SHOWCASE` (comma-separated case ids) |

## Fixtures (`docs/api_fixtures/`)

Each fixture is one JSON file of the form `{"name", "description", "request", "response": {"status", "body"}, "events": [...], "creature"?, "snapshot"?}`.
The events are exactly what the SSE stream sends (the `data` objects, in order). The images are in `images/`.

| file | scenario |
|---|---|
| `run_success.json` | a full successful run, converted from the real S5 trace of b09 Indian pangolin × horse, with every image and the anatomy map |
| `run_host_tie.json` | a host tie: the agent asks the user (`needs_choice`), the user picks, and the run finishes (built from S5 b10 tortoise × domestic goat, with the ask added) |
| `identify_choice.json` | `POST` returns needs_choice for a low-confidence identification |
| `run_cap.json` | a run that reaches the render cap (`cap_reached`), then finalizes its best image (S5 b06 common octopus × horse) |
| `run_queued.json` | the run waits in the queue (positions 2, then 1), then starts and finishes (S5 b03) |
| `upload_refused.json` | the refused uploads: a person, an unsupported type, a too-large file |
| `cap_daily.json` | `POST` refused by the daily cap |
| `run_error.json` | the run fails mid-way with `UPSTREAM_ERROR` |
| `gallery.json` | `GET /evo/gallery` with the six showcase creatures |
| `creature_b09.json` | `GET /evo/creatures/{id}` for the success fixture |
| `limits.json` | `GET /evo/agent/limits`, open and capped |
