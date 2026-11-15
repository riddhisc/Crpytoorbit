"""Crypto Orbit FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import get_settings
from app.db import run_migrations
from app.errors import register_exception_handlers
from app.limiter import limiter
from app.logging import RequestIdMiddleware, setup_logging
from app.routers import demo, exceptions, export, health, imports, ledger, tax, webhooks

DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    run_migrations()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        summary="Normalize exchange exports, reconcile them, and estimate India crypto tax.",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    register_exception_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, imports, ledger, exceptions, tax, export, demo, webhooks):
        app.include_router(module.router)
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        reserved = {"docs", "redoc", "openapi.json", "health", "ready", "metrics"}
        if full_path.startswith("api/") or full_path in reserved:
            raise HTTPException(status_code=404, detail="Not found.")
        if not DIST.exists():
            raise HTTPException(status_code=404, detail="Frontend bundle is not built yet.")
        candidate = (DIST / full_path).resolve()
        root = DIST.resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(root)):
            return FileResponse(candidate)
        index = DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend bundle is not built yet.")

    return app


app = create_app()
