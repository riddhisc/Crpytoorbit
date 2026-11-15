"""Liveness, readiness, and Prometheus metrics."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from app.deps import DbSession
from app.errors import AppError
from app.metrics import render_metrics
from app.schemas import HealthOut, ReadyOut

router = APIRouter(tags=["health"])
HEAD_REVISION = "0001_initial"


@router.get("/health", response_model=HealthOut, summary="Liveness")
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/ready", response_model=ReadyOut, summary="Database and migrations")
def ready(session: DbSession) -> ReadyOut:
    try:
        session.execute(text("SELECT 1"))
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:  # noqa: BLE001
        raise AppError(503, "NOT_READY", "Database is not ready.", {"reason": str(exc)}) from exc
    if revision != HEAD_REVISION:
        raise AppError(503, "NOT_READY", "Migrations are not at head.", {"revision": revision})
    return ReadyOut(status="ready", revision=str(revision))


@router.get("/metrics", summary="Prometheus metrics", response_class=PlainTextResponse)
def metrics(session: DbSession) -> PlainTextResponse:
    return PlainTextResponse(render_metrics(session), media_type="text/plain; version=0.0.4")
