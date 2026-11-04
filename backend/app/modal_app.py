"""Modal entrypoint: `modal deploy backend/app/modal_app.py` (CI does this on every push to main: docs/DEPLOY.md).

One app serves everything: the built frontend (frontend/dist) at / and the API under /evo, so there is one URL and
no CORS setup. Build the frontend first (`cd frontend && npm run build`); deploying without it fails, so the site
can never go live as an API without its pages.

The app's settings come from a Modal secret named `chimera-lab` (META_API_KEY, SUPABASE_*, EVO_*; see .env.example).
Fusion runs, edits and animal cards run inside the web process (D-016), so the app keeps exactly one warm container.
"""

from __future__ import annotations

import os
from pathlib import Path

import modal

BACKEND_DIR = Path(__file__).resolve().parents[1]
DIST = BACKEND_DIR.parent / "frontend" / "dist"
REMOTE_DIST = "/root/frontend/dist"
SECRET_NAME = os.environ.get("CHIMERA_MODAL_SECRET", "chimera-lab")

# Only the deploying machine checks for the build (inside the container the repo is not there).
if modal.is_local() and not (DIST / "index.html").exists():
    raise SystemExit("frontend/dist is missing: run `cd frontend && npm ci && npm run build` before deploying.")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .add_local_dir(str(BACKEND_DIR / "app"), remote_path="/root/app")
    .add_local_dir(str(DIST), remote_path=REMOTE_DIST)
)

app = modal.App("chimera-lab", image=image)


@app.function(
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    # A Fusion run is capped at 15 minutes (EVO_RUN_HARD_SECONDS); Modal cuts a web request at 150 s, and the live
    # stream reconnects and resumes from the last event.
    timeout=1200,
    # Jobs run as in-process tasks (D-016): one warm container, so every request reaches the process that owns them.
    min_containers=1,
    max_containers=1,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():  # type: ignore[no-untyped-def]
    from app.config import Settings
    from app.main import create_app

    return create_app(Settings(frontend_dist=REMOTE_DIST))
