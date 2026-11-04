# Chimera Lab

Make new creatures by fusing two animals, then shape them on a canvas.

Give Chimera Lab two animals (a photo, a name, or a creature you made earlier) and an art style; it draws one hybrid
creature, names it and writes its field-guide entry. From there you iterate on a FLORA-style canvas where every
change is a card between two images, so the path from the two animals to the final creature stays visible.

Every creature is generated. Chimera Lab never presents one as a real animal.

## What it does

- **Workspaces.** The home page lists your workspaces (canvases). Create, open, rename or delete one; deleting a
  workspace deletes its images.
- **Fusion.** Two animals → one image from Muse Image, in one of five art styles (real, drawing, anime, comic,
  cartoon) on a white background. Photos and earlier creatures are sent as reference images ("blend the animals, not
  the art styles"). Typed names and edit text must be about creating animal chimeras (a topic check refuses the rest;
  photos of people are refused).
- **A named creature.** Right after each image, Muse Spark reads it and writes the creature's profile: a name, length,
  weight, habitat, explorer's notes and its defining trait. The name becomes the image's title.
- **Edits.** From any image: **Revise** (describe a change), **Paint** (mark an area; it is filled with parts of the
  creature's parent animals) or **Draw** (sketch what you want; the marks become body parts). Each result is a new
  image after the edit card.
- **Chimeras and animal cards.** **Save** any creature to the Chimeras page. Its animal card (a field-guide page with
  four more angles: front, side, back, above) is drawn in the background. Cards show small and open in a modal; their
  text can be edited.
- **Library.** Add image opens everything you have made, your photos on this device, and upload.

## Models

| Model | Used for |
|---|---|
| **Muse Image 1.0** (Meta API) | every image: Fusion, Revise, Paint, Draw, card angles |
| **Muse Spark 1.3** (Meta API) | identifying photos, the topic check, the creature profile |

The history of how the app got here (an anatomy-planning agent that was benchmarked and then replaced by this
prompt-first flow) is in [`docs/HISTORY.md`](docs/HISTORY.md).

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd frontend && npm install && cd ..
cp .env.example .env        # then fill in META_API_KEY and the Supabase keys
scripts/dev.sh
```

Open <http://localhost:5173>. Vite proxies `/evo` and `/health` to the backend on port 8000, so the browser sees one
origin, as in production (where the backend serves the built frontend at `/`).

### Supabase

1. Create a project; put its URL and secret key in `.env`.
2. In the SQL editor run `backend/app/adapters/supabase/schema.sql`, then `001` to `004` in order.

There is no sign-in: each browser makes a random visitor id on its first visit, keeps it in localStorage and sends it
as `X-Visitor-Id`. Workspaces, creatures and the per-visitor caps belong to that id; clearing site data starts over.

### The tutorial

A first visit opens a hands-on tutorial in the real Lab: add a Fusion node (prefilled Tiger + Bat, anime), press Make
creature, save the result, open Chimeras, then create a workspace. The glowing element is the next thing to click;
Skip goes to the workspace list. Its calls are answered in the browser (`frontend/src/tutorial/sandbox.ts`): the run
is a replay of a creature made once with the live models (`frontend/public/example/`), so the tutorial costs no
model calls and never reaches the server.

### The Garden

Share to Garden (on a saved creature in Chimeras) makes it visible to everyone at `/?view=garden`; only its card is
shown, never who made it. Optional index: `backend/app/adapters/supabase/005_garden_index.sql`.

## Tests

| Command | What |
|---|---|
| `.venv/bin/python -m pytest backend` | backend with fake models: no paid call, never reads `.env` |
| `cd frontend && npm test` | frontend unit and component tests |
| `scripts/check-css.sh` | one stylesheet, no inline styles, colours only from tokens |

CI runs all of them on every push and pull request (`.github/workflows/ci.yml`).

## Deploy

Pushing to `main` deploys to Modal after the checks pass: one app serves the site at `/` and the API at `/evo`.
Setup, secrets and rollback: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Repository map

```
backend/app/
  agentapi/      the API: Fusion runs (routes, jobs, uploads, caps), the Lab (versions, edits, cards),
                 the library (workspaces, chimeras, deletes), creature profiles and the topic check
  adapters/      Meta (models), Supabase (database, storage), local SQLite and files, retries
  main.py        the FastAPI app; modal_app.py deploys it to Modal
backend/tests/   API tests on fake models
frontend/src/
  screens/       home (workspaces), Lab, Chimeras
  canvas/        the node canvas, drop menu, add-image library
  nodes/         node types: image input, Fusion, image, edit, animal card
  lab/           Lab API client, animal card, tools panel, paint and draw editor
docs/            ARCHITECTURE.md, DEPLOY.md, HISTORY.md, design-system/
scripts/         dev.sh, modal-setup.sh, CSS and bundle checks, type generation
```
