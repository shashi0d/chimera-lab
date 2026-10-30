"""Modal entrypoint (P7-05: `modal deploy backend/app/modal_app.py`).

Secrets are attached as a Modal secret named `chimera-lab` holding the env vars
from TASKSHEET Section 13 (META_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, ...).
"""

from __future__ import annotations

from pathlib import Path

import modal

BACKEND_DIR = Path(__file__).resolve().parents[1]

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .add_local_dir(str(BACKEND_DIR / "app"), remote_path="/root/app")
    .add_local_dir(str(BACKEND_DIR / "tests" / "fixtures"), remote_path="/root/tests/fixtures")
    .add_local_dir(str(BACKEND_DIR.parent / "data"), remote_path="/root/data")
)

app = modal.App("chimera-lab", image=image)


@app.function(
    secrets=[modal.Secret.from_name("chimera-lab")],
    timeout=600,
    # Runs execute as in-process tasks; keep one warm container so polling hits the same process.
    min_containers=1,
    max_containers=1,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():  # type: ignore[no-untyped-def]
    from app.config import Settings
    from app.main import create_app

    return create_app(Settings(data_path="/root/data/chimera_data.json"))
