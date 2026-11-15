"""Load the bundled sample and reset the desk in demo mode."""

from pathlib import Path

from fastapi import APIRouter
from sqlmodel import SQLModel

from app.deps import Actor, AppSettings, DbSession
from app.errors import AppError
from app.models import Job
from app.schemas import DemoResult, ImportFileStatus
from app.services.ingest import ingest_files

router = APIRouter(prefix="/api/v1", tags=["demo"])
SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample-data"
SAMPLE_FILES = ("wazirx_trades.csv", "binance_trades.csv", "wallet_transfers.json")


@router.post("/demo/load", response_model=DemoResult, summary="Load bundled sample files")
def load_demo(session: DbSession, _actor: Actor) -> DemoResult:
    files: list[tuple[str, bytes]] = []
    for name in SAMPLE_FILES:
        path = SAMPLE_DIR / name
        if not path.exists():
            raise AppError(500, "INTERNAL", f"Sample file {name} is missing.")
        files.append((name, path.read_bytes()))
    job = Job(kind="demo", status="queued", message="Loading sample data")
    session.add(job)
    session.commit()
    session.refresh(job)
    result = ingest_files(session, job, files)
    raw_files = result.get("files", [])
    raw_reconcile = result.get("reconcile", {})
    file_rows = raw_files if isinstance(raw_files, list) else []
    reconcile = raw_reconcile if isinstance(raw_reconcile, dict) else {}
    return DemoResult(
        job_id=job.id,
        files=[ImportFileStatus.model_validate(item) for item in file_rows],
        open_exceptions=int(reconcile.get("open_exceptions", 0)),
        matches=int(reconcile.get("matches", 0)),
    )


@router.post("/reset", summary="Erase desk data (demo mode only)")
def reset_desk(session: DbSession, settings: AppSettings, _actor: Actor) -> dict[str, str]:
    if not settings.demo_mode:
        raise AppError(403, "DEMO_DISABLED", "Reset is available only when DEMO_MODE is true.")
    for table in reversed(SQLModel.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    return {"status": "reset"}
