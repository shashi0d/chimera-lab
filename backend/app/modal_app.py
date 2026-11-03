"""Modal entrypoint (P7-05: `modal deploy backend/app/modal_app.py`). One host option among several (D-096); the app
itself is plain FastAPI + uvicorn and uses no Modal-only feature (docs/r1/deploy_checklist.md).

Secrets are attached as a Modal secret named `chimera-lab` holding the env vars from docs/r1/deploy_checklist.md
(META_API_KEY, BASETEN_API_KEY_MODEL_MUSE_SPARK_OPEN_26, SUPABASE_URL, SUPABASE_SECRET_KEY, SUPABASE_PUBLISHABLE_KEY, the caps, ...).
The built frontend (frontend/dist) and the S5 showcase outputs are added when they exist.
"""

from __future__ import annotations

from pathlib import Path

import modal

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO = BACKEND_DIR.parent
OPTIONAL = {"frontend_dist": (REPO / "frontend" / "dist", "/root/frontend/dist"),
            "evo_showcase_dir": (REPO / "docs" / "evolution" / "live" / "s5", "/root/s5")}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .add_local_dir(str(BACKEND_DIR / "app"), remote_path="/root/app")
    .add_local_dir(str(BACKEND_DIR / "tests" / "fixtures"), remote_path="/root/tests/fixtures")
    .add_local_dir(str(REPO / "data"), remote_path="/root/data")
)
for _src, _dst in OPTIONAL.values():
    if _src.exists():
        image = image.add_local_dir(str(_src), remote_path=_dst)

app = modal.App("chimera-lab", image=image)


@app.function(
    secrets=[modal.Secret.from_name("chimera-lab")],
    # An agent run lasts up to 15 minutes (EVO_RUN_HARD_SECONDS) and its SSE stream stays open as long.
    timeout=1200,
    # Runs execute as in-process tasks (D-016); keep one warm container so streams and polls hit the same process.
    min_containers=1,
    max_containers=1,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():  # type: ignore[no-untyped-def]
    from app.config import Settings
    from app.main import create_app

    paths = {k: dst for k, (_src, dst) in OPTIONAL.items() if Path(dst).exists()}
    return create_app(Settings(**paths))
