"""Exception list, detail, and resolution."""

from datetime import datetime

from fastapi import APIRouter, Query
from sqlmodel import col, select

from app.deps import Actor, DbSession
from app.errors import AppError
from app.models import ExceptionRecord, ResolutionEvent
from app.schemas import (
    BulkUpdate,
    EvidenceRow,
    ExceptionDetail,
    ExceptionItem,
    HistoryEvent,
    Page,
    StatusUpdate,
)
from app.services.read import evidence_for, exception_counts, list_exceptions
from app.services.resolve import apply_status

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


def _item(row: ExceptionRecord) -> ExceptionItem:
    return ExceptionItem.model_validate(row)


@router.get("", response_model=Page[ExceptionItem], summary="Filter exceptions")
def get_exceptions(
    session: DbSession,
    type: str | None = None,
    severity: str | None = None,
    asset: str | None = None,
    source: str | None = None,
    status: str | None = Query(default=None, pattern="^(open|resolved|ignored)$"),
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    q: str | None = None,
    sort: str = Query(default="ts_desc", pattern="^(ts_asc|ts_desc|value_asc|value_desc)$"),
    page: int = 1,
    page_size: int = 50,
) -> Page[ExceptionItem]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    rows, total = list_exceptions(
        session,
        exc_type=type,
        severity=severity,
        asset=asset,
        source=source,
        status=status,
        start=start,
        end=end,
        q=q,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page(items=[_item(row) for row in rows], total=total, page=page, page_size=page_size)


@router.get("/counts", summary="Status tab counts")
def counts(session: DbSession) -> dict[str, int]:
    return exception_counts(session)


@router.post(
    "/bulk", response_model=list[ExceptionItem], summary="Resolve or ignore several exceptions"
)
def bulk(body: BulkUpdate, session: DbSession, actor: Actor) -> list[ExceptionItem]:
    updated: list[ExceptionItem] = []
    for exc_id in body.ids:
        row = session.get(ExceptionRecord, exc_id)
        if row is None:
            raise AppError(404, "NOT_FOUND", f"Exception {exc_id} was not found.")
        updated.append(_item(apply_status(session, row, body.status, body.resolution_note, actor)))
    return updated


@router.get(
    "/{exception_id}", response_model=ExceptionDetail, summary="Exception evidence and history"
)
def detail(exception_id: str, session: DbSession) -> ExceptionDetail:
    row = session.get(ExceptionRecord, exception_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Exception not found.")
    history = session.exec(
        select(ResolutionEvent)
        .where(ResolutionEvent.exception_id == row.id)
        .order_by(col(ResolutionEvent.created_at))
    ).all()
    base = _item(row).model_dump()
    return ExceptionDetail(
        **base,
        evidence=[EvidenceRow.model_validate(item) for item in evidence_for(session, row)],
        history=[HistoryEvent.model_validate(event) for event in history],
        details=row.details or {},
    )


@router.patch(
    "/{exception_id}",
    response_model=ExceptionItem,
    summary="Resolve, ignore, or reopen an exception",
)
def patch_exception(
    exception_id: str, body: StatusUpdate, session: DbSession, actor: Actor
) -> ExceptionItem:
    row = session.get(ExceptionRecord, exception_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Exception not found.")
    return _item(apply_status(session, row, body.status, body.resolution_note, actor))
