# The Lab: one flow from two animals to a final creature

Chimera Lab has one creative flow, modelled on FLORA's canvas: every generated image is a card on the canvas, and
every change is a card between two images. The canvas itself is the record of how a creature was made.

```
[Photo or name A]─┐                 ┌─[Edit · Revise "longer legs"]──[V2]──[Edit · Paint "blue mane"]──[V3 ★ final]
                  ├─[Fusion agent]──[V1]
[Photo or name B]─┘                 └─[Edit · Revise "red fur"]──[V2b]
```

## The flow

1. **Animals.** A photo (drop, paste or pick) or a typed name for each of the two parents. Photos stay on the
   device where they were added; they are identified by the vision model when a run starts and never stored.
2. **Fusion.** The agent run (`/evo/agent/runs`): it plans the anatomy, renders, inspects and finalizes, with its
   live trace beside the canvas. As the run starts, an image card hangs off the Fusion node showing the agent's
   latest attempt; when the run finishes, it becomes **V1** (`POST /evo/lab/versions/from-run`).
3. **Edit cards.** From any image card: **Revise** (the whole image changes as described) or **Paint** (paint an
   area; the model's edit is blended into the painted pixels only, everything else stays exactly as it was).
   Use the card's toolbar, the tools panel, or drag from an image's output onto empty canvas. **Generate** runs the
   edit as a background job; each success adds a new image card after the edit card. Change the text and generate
   again to get a sibling variant. Jobs survive a reload.
4. **Tools for the selected image** (panel beside the canvas):
   - the **path** from V1 to this image (click a step to go to it);
   - **compare** with another version of the same creature;
   - **visual review**: a model describes the image, then suggests next steps (observations can be wrong);
   - **collaborator**: chat about the next step. It can inspect the image once per message and propose a
     revision, which becomes a pre-filled Revise card. It never runs anything itself;
   - **mark as final**, **download**, and **publish to the gallery**.
5. **Gallery.** Publishing puts the image in the gallery with its whole path. A creation opens as a read-only
   canvas: animals → Fusion → every edit → final, with a plain list of the steps. The showcase (benchmark agent
   runs) stays featured. Finished runs are private until a version is published.

## Accounts (Supabase Auth)

- Sign-in is by email magic link. The Lab needs an account; the gallery and creation pages are public.
- The browser gets the project URL and the publishable key from `GET /evo/config`, signs in with supabase-js
  (PKCE), and sends `Authorization: Bearer <access token>` on every API call.
- The backend verifies the token locally against the project's signing keys (ES256 JWKS, cached): audience
  `authenticated`, issuer, expiry; anonymous users are refused (`backend/app/auth.py`).
- The user id owns everything: runs, versions, edit jobs, the workspace, the daily caps.

## Where data lives (Supabase)

| What | Where |
|---|---|
| The canvas (workspace) | `graphs` table, key `workspace:<user id>` (last write wins); a copy per user in IndexedDB |
| Agent runs and their events | `agent_runs` |
| Run creatures, published creations | `creatures` (`kind` `evo_agent` or `lab_publication`) |
| Lab versions and edit jobs | `assets` (`kind` `lab_version` or `lab_job`, `owner`) |
| Daily caps | `counters` through `incr_counter` (service role only) |
| Generated images | public bucket `chimera-public` (`runs/…`, `lab/…`, `showcase/…`) |

Row level security is on for every table with no policies, and only `service_role` has table privileges: the
publishable key can read or write nothing (migrations `002`, `003`).

## Daily limits

- Fusion runs: 50 per day in total, 3 per user (`EVO_DAILY_RUNS`, `EVO_VISITOR_DAILY_RUNS`).
- Lab actions (each edit, review or collaborator message): 100 per day in total, 20 per user
  (`LAB_DAILY_ACTIONS`, `LAB_USER_DAILY_ACTIONS`). A failed action is refunded.

## Setup

1. `.env` at the repo root: `META_API_KEY`, `BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26`, `SUPABASE_URL`,
   `SUPABASE_SECRET_KEY`, `SUPABASE_PUBLISHABLE_KEY` (see `.env.example`).
2. Supabase SQL: run `backend/app/adapters/supabase/schema.sql`, then `001` to `004` in order.
3. Supabase dashboard → Authentication → URL Configuration: set the **Site URL** to the app's address and add
   `<address>/**` to the **Redirect URLs** (for development: `http://localhost:5173` and `http://localhost:5173/**`).
   Without this, magic links return to Supabase's default address.
4. Email: Supabase's built-in email service only delivers to the project team's addresses, a few per hour. Set up
   custom SMTP (Authentication → Emails) before inviting anyone else.
5. `scripts/dev.sh`, then open <http://localhost:5173> (Vite proxies `/evo` to the backend: one origin).

## Decisions

- **Live only.** No mock mode in the app. Tests use fakes injected at test time (`backend/tests/fakes`,
  `frontend/tests/fakes`) and never read `.env`, so they never call a paid model or touch the live project.
- **Photos stay on the device.** Only the identified species names reach the server. A canvas opened on another
  device shows its photo cards as missing their local copy; the rest of the path (from V1) is on the server.
- **Image URLs are unlisted, not private.** Lab images go to the public bucket under random ids, so cards and the
  gallery load them without signed URLs.

## Next improvements

- Remix: start your own Lab path from a gallery creation.
- Several workspaces (projects) per user, and a conflict check between two open tabs (today: last write wins).
- Store input photos privately (signed URLs), so a canvas is complete on every device.
- Custom SMTP and a production Site URL when hosting.
- Edit cards with more operations (upscale, variations of the whole image, style), each a card in the path.
