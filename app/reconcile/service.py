"""Orchestrate a reconcile run and upsert exceptions by fingerprint."""

import time
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.config import get_settings
from app.logging import get_logger
from app.metrics import record_reconcile_duration
from app.models import (
    CanonicalTx,
    ExceptionRecord,
    ExceptionRelatedTx,
    MatchedTransfer,
    utcnow,
)
from app.parsing import dec_str
from app.reconcile.matcher import match_transfers, tx_id
from app.reconcile.rules import ExceptionDraft, build_exceptions
from app.repositories.analytics import running_balances
from app.services.webhooks import dispatch_new_high

logger = get_logger("reconcile")


def reconcile(session: Session) -> dict[str, int]:
    started = time.perf_counter()
    settings = get_settings()
    txs = list(session.exec(select(CanonicalTx)).all())
    for tx in txs:
        tx.excluded = False
        session.add(tx)
    session.commit()
    txs = list(session.exec(select(CanonicalTx)).all())
    existing = {row.fingerprint: row for row in session.exec(select(ExceptionRecord)).all()}
    resolved = {
        fp
        for fp, row in existing.items()
        if row.status == "resolved" and row.type == "DUPLICATE_TRADE"
    }
    # Duplicate flags are applied before balances so a repeat fill cannot mask a short position.
    from app.reconcile.rules import _duplicates

    duplicate_drafts = _duplicates(txs)
    exclude_ids: set[str] = set()
    for draft in duplicate_drafts:
        if draft.fingerprint in resolved:
            continue
        exclude_ids.update(draft.exclude_tx_ids)
    if exclude_ids:
        for tx in txs:
            if tx.id in exclude_ids:
                tx.excluded = True
                session.add(tx)
        session.commit()
        txs = list(session.exec(select(CanonicalTx)).all())
    active = [tx for tx in txs if not tx.excluded]
    match_started = time.perf_counter()
    matches = match_transfers(active, settings)
    logger.info(
        "match_done", pairs=len(matches), ms=round((time.perf_counter() - match_started) * 1000, 2)
    )
    for old in session.exec(select(MatchedTransfer)).all():
        session.delete(old)
    for match in matches:
        session.add(
            MatchedTransfer(
                out_tx_id=tx_id(match.out_tx),
                in_tx_id=tx_id(match.in_tx),
                asset=match.out_tx.asset,
                sent_qty=match.out_tx.qty,
                received_qty=match.in_tx.qty,
                fee_qty=match.fee_qty,
                match_kind=match.match_kind,
            )
        )
    session.commit()
    balances = running_balances(session)
    rule_started = time.perf_counter()
    drafts = build_exceptions(txs, matches, balances, settings)
    # build_exceptions excludes duplicate secondaries itself; keep those ids aligned with the DB flag.
    logger.info(
        "rules_done",
        exceptions=len(drafts),
        ms=round((time.perf_counter() - rule_started) * 1000, 2),
    )
    seen: set[str] = set()
    created_high: list[ExceptionRecord] = []
    for draft in drafts:
        seen.add(draft.fingerprint)
        current = existing.get(draft.fingerprint)
        if current is None:
            current = ExceptionRecord(
                type=draft.type,
                severity=draft.severity,
                asset=draft.asset,
                source=draft.source,
                ts_utc=draft.ts_utc,
                estimated_value_inr=draft.estimated_value_inr,
                explanation=draft.explanation,
                suggested_fix=draft.suggested_fix,
                status="open",
                fingerprint=draft.fingerprint,
                details=_details(draft),
            )
            session.add(current)
            session.commit()
            session.refresh(current)
            existing[draft.fingerprint] = current
            if draft.severity == "high":
                created_high.append(current)
        elif current.status == "open":
            current.severity = draft.severity
            current.asset = draft.asset
            current.source = draft.source
            current.ts_utc = draft.ts_utc
            current.estimated_value_inr = draft.estimated_value_inr
            current.explanation = draft.explanation
            current.suggested_fix = draft.suggested_fix
            current.details = _details(draft)
            current.updated_at = utcnow()
            session.add(current)
        _replace_links(session, current.id, draft.related_ids)
    for fingerprint, row in list(existing.items()):
        if fingerprint not in seen and row.status == "open":
            for link in session.exec(
                select(ExceptionRelatedTx).where(ExceptionRelatedTx.exception_id == row.id)
            ).all():
                session.delete(link)
            session.delete(row)
    session.commit()
    dispatch_new_high(session, created_high)
    duration = time.perf_counter() - started
    record_reconcile_duration(duration)
    logger.info("reconcile_done", seconds=round(duration, 4), open_new=len(created_high))
    open_count = len(
        list(session.exec(select(ExceptionRecord).where(ExceptionRecord.status == "open")).all())
    )
    return {"matches": len(matches), "open_exceptions": open_count}


def _details(draft: ExceptionDraft) -> dict:
    details = dict(draft.details)
    if draft.estimated_value_inr is not None:
        details["estimated_value_inr"] = dec_str(draft.estimated_value_inr)
    return details


def _replace_links(session: Session, exception_id: str, tx_ids: list[str]) -> None:
    for link in session.exec(
        select(ExceptionRelatedTx).where(ExceptionRelatedTx.exception_id == exception_id)
    ).all():
        session.delete(link)
    for related_id in tx_ids:
        session.add(ExceptionRelatedTx(exception_id=exception_id, tx_id=related_id))


def touch_resolved(when: datetime | None = None) -> datetime:
    return when or datetime.now(UTC)
