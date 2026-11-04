"""One origin: the built frontend (FRONTEND_DIST, default frontend/dist) at / with an SPA fallback for client routes.

- A GET or HEAD whose path is a file in dist is served before routing (a middleware), because Vite's bundle lives in
  dist/assets/ and the v1 API owns /assets/{asset_id}. Hashed files under assets/ are cached for a year.
- After every API route, a catch-all GET returns index.html for client routes (never cached). Paths under an API
  prefix keep their JSON 404.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response

from app.errors import ChimeraError
from app.models.schemas import ErrorCode

log = logging.getLogger(__name__)
# First path segments owned by the API (v1 and /evo); they never fall back to index.html.
API_PREFIXES = ("evo", "health", "runs", "graphs", "assets", "docs", "redoc", "openapi.json")


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    index = dist / "index.html"
    if not index.is_file():
        log.info("No built frontend at %s: serving the API only", dist)
        return False
    root = dist.resolve()

    def file_for(path: str) -> Path | None:
        rel = path.lstrip("/")
        if not rel or rel.startswith("evo/"):
            return None
        target = (root / rel).resolve()
        return target if root in target.parents and target.is_file() else None

    @app.middleware("http")
    async def static_files(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method in ("GET", "HEAD") and (target := file_for(request.url.path)) is not None:
            hashed = request.url.path.startswith("/assets/")
            return FileResponse(target, headers={
                "Cache-Control": "public, max-age=31536000, immutable" if hashed else "public, max-age=300"})
        return await call_next(request)

    def index_response() -> Response:
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    async def home() -> Response:
        return index_response()

    async def client_route(full_path: str) -> Response:
        if full_path.split("/", 1)[0] in API_PREFIXES:
            raise ChimeraError(ErrorCode.NOT_FOUND, "Not found.")
        return index_response()

    app.add_api_route("/", home, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route("/{full_path:path}", client_route, methods=["GET", "HEAD"], include_in_schema=False)
    log.info("Serving the frontend from %s", dist)
    return True
