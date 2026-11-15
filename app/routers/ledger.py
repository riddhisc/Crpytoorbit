"""Ledger, summary, and audit log."""

from datetime import datetime

from fastapi import APIRouter, Query

from app.deps import DbSession
from app.schemas import AuditEvent, LedgerRow, Page, Summary
from app.services.read import audit_log, list_ledger, summary

router = APIRouter(prefix="/api/v1", tags=["ledger"])


@router.get("/ledger", response_model=Page[LedgerRow], summary="Normalized ledger")
def ledger(
    session: DbSession,
    asset: str | None = None,
    source: str | None = None,
    kind: str | None = Query(default=None, pattern="^(TRADE|TRANSFER_IN|TRANSFER_OUT)$"),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    page: int = 1,
    page_size: int = 50,
    sort: str = Query(default="ts_desc", pattern="^(ts_asc|ts_desc|asset|qty)$"),
) -> Page[LedgerRow]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    items, total = list_ledger(
        session,
        asset=asset,
        source=source,
        kind=kind,
        start=start,
        end=end,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page(
        items=[LedgerRow.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=Summary, summary="Desk summary")
def desk_summary(session: DbSession) -> Summary:
    return Summary(**summary(session))


@router.get("/audit-log", response_model=Page[AuditEvent], summary="Exception status changes")
def get_audit(session: DbSession, page: int = 1, page_size: int = 50) -> Page[AuditEvent]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    items, total = audit_log(session, page, page_size)
    return Page(
        items=[AuditEvent.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )
