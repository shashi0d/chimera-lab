"""FastAPI app factory. Run with `uvicorn app.main:app` (any host); Modal wraps it in modal_app.py.

One origin (D-096): the API under /evo (plus /health) and, when it is built, the frontend at / with an SPA
fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agentapi.files import build_public_files
from app.agentapi.routes import AgentApi
from app.agentapi.routes import router as agent_router
from app.agentapi.static import mount_frontend
from app.config import APP_VERSION, Settings, get_settings
from app.errors import ChimeraError
from app.models.schemas import ApiError, ErrorCode, ErrorEnvelope
from app.services import Services, build_services

log = logging.getLogger("chimera")


def _envelope(err: ApiError, status: int, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(ErrorEnvelope(error=err).dump(), status_code=status, headers=headers)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = services or build_services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if svc.local_backend:
            n = await app.state.agent.store.interrupt_orphans()
            if n:
                log.warning("Marked %d orphaned run(s) as interrupted", n)
        yield
        await app.state.lab.shutdown()
        await app.state.agent.runner.shutdown()

    app = FastAPI(title="Chimera Lab API", version=APP_VERSION, lifespan=lifespan)
    app.state.services = svc
    app.state.agent = AgentApi(svc, build_public_files(settings))  # the Fusion API under /evo
    from app.auth import Auth

    app.state.auth = Auth(settings)
    from app.agentapi.lab import LabCaps, LabState

    app.state.lab = LabState(LabCaps(svc.db, settings), asyncio.Semaphore(settings.lab_max_concurrent_actions))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Session-Id", "Last-Event-ID"],
        expose_headers=["ETag"],
        max_age=600,
    )

    @app.exception_handler(ChimeraError)
    async def chimera_error(_: Request, exc: ChimeraError) -> JSONResponse:
        headers = {"Retry-After": str(max(1, exc.retry_after_ms // 1000))} if exc.retry_after_ms else None
        return _envelope(exc.to_api(), exc.status, headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()][:10]
        err = ApiError(code=ErrorCode.VALIDATION_FAILED, message="The request was not valid.", details={"fields": fields})
        return _envelope(err, 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.VALIDATION_FAILED
        return _envelope(ApiError(code=code, message=str(exc.detail)), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", exc_info=exc)
        return _envelope(ChimeraError(ErrorCode.INTERNAL).to_api(), 500)

    @app.get("/health", response_model=None)
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION}

    app.include_router(agent_router)
    from app.agentapi.lab import router as lab_router

    app.include_router(lab_router)
    from app.agentapi.library import router as library_router

    app.include_router(library_router)
    mount_frontend(app, settings.repo_path(settings.frontend_dist))  # last: the SPA fallback
    return app


def __getattr__(name: str) -> object:
    # `uvicorn app.main:app` builds the app lazily so importing this module stays side-effect free.
    if name == "app":
        return create_app()
    raise AttributeError(name)
