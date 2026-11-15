"""Persist exception status changes and the audit trail."""

from sqlmodel import Session, select

from app.errors import AppError
from app.models import CanonicalTx, ExceptionRecord, ExceptionRelatedTx, ResolutionEvent, utcnow

ALLOWED = {"open", "resolved", "ignored"}


def apply_status(
    session: Session, exc: ExceptionRecord, status: str, note: str, actor: str
) -> ExceptionRecord:
    if status not in ALLOWED:
        raise AppError(422, "VALIDATION_ERROR", "Status must be open, resolved, or ignored.")
    if status in {"resolved", "ignored"} and not note.strip():
        raise AppError(
            422, "VALIDATION_ERROR", "A note is required to resolve or ignore an exception."
        )
    previous = exc.status
    exc.status = status
    exc.resolution_note = note.strip() or None
    exc.resolved_at = utcnow() if status != "open" else None
    exc.updated_at = utcnow()
    session.add(exc)
    session.add(
        ResolutionEvent(
            exception_id=exc.id,
            from_status=previous,
            to_status=status,
            note=exc.resolution_note,
            actor=actor,
        )
    )
    if exc.type == "DUPLICATE_TRADE":
        _sync_duplicate_flag(session, exc, status)
    session.commit()
    session.refresh(exc)
    return exc


def _sync_duplicate_flag(session: Session, exc: ExceptionRecord, status: str) -> None:
    links = session.exec(
        select(ExceptionRelatedTx).where(ExceptionRelatedTx.exception_id == exc.id)
    ).all()
    txs = [session.get(CanonicalTx, link.tx_id) for link in links]
    present = [tx for tx in txs if tx is not None]
    if len(present) < 2:
        return
    secondary = sorted(present, key=lambda tx: tx.source_row)[-1]
    secondary.excluded = status != "resolved"
    session.add(secondary)
