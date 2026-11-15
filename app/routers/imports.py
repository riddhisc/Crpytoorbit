"""Upload endpoints, import jobs, issues, and column-mapping flow."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Header, Request, UploadFile
from fastapi.responses import Response

from app.connectors.generic_mapped import GenericMappedConnector
from app.connectors.registry import header_signature
from app.deps import Actor, AppSettings, DbSession
from app.errors import AppError
from app.limiter import limiter
from app.models import ConnectorProfile, Job
from app.schemas import (
    ImportIssueOut,
    JobCreated,
    JobStatus,
    MappingPreviewRequest,
    MappingPreviewResponse,
    MappingProfileOut,
    MappingProfileRequest,
    MappingSuggestion,
    MappingSuggestRequest,
    MappingSuggestResponse,
    Page,
    PreviewRow,
)
from app.services.export import issues_csv
from app.services.ingest import content_hash, ingest_files, preflight
from app.services.jobs import start_job
from app.services.mapping import suggest_mapping, suggest_with_llm
from app.services.read import list_issues

router = APIRouter(prefix="/api/v1", tags=["imports"])
_ALLOWED_EXT = {".csv", ".json", ".txt"}
_ALLOWED_MIME = {
    "",
    "text/csv",
    "application/json",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "text/json",
}


def _check_upload(upload: UploadFile, payload: bytes, settings_max: int) -> None:
    name = upload.filename or "upload.csv"
    ext = Path(name).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise AppError(
            422, "UNSUPPORTED_FILE", f"{name} must be a CSV or JSON file.", {"filename": name}
        )
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_MIME:
        raise AppError(
            422,
            "UNSUPPORTED_FILE",
            f"MIME type {mime or 'unknown'} is not allowed.",
            {"filename": name},
        )
    if len(payload) > settings_max:
        raise AppError(413, "FILE_TOO_LARGE", f"{name} exceeds the upload size limit.")


@router.post(
    "/imports",
    status_code=202,
    response_model=JobCreated,
    summary="Upload one or more exchange files",
)
@limiter.limit("30/minute")
async def create_import(
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    settings: AppSettings,
    _actor: Actor,
    files: list[UploadFile] = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobCreated:
    payloads: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        _check_upload(upload, content, settings.max_upload_bytes)
        payloads.append((upload.filename or "upload.csv", content))
    if not payloads:
        raise AppError(422, "VALIDATION_ERROR", "Attach at least one file.")
    preflight(payloads, session)
    job, replayed = start_job(
        session, "import", [content_hash(item[1]) for item in payloads], idempotency_key
    )
    if not replayed:
        background.add_task(_run_import, job.id, payloads)
    return JobCreated(job_id=job.id)


def _run_import(job_id: str, files: list[tuple[str, bytes]]) -> None:
    from app.db import session_scope

    with session_scope() as session:
        job = session.get(Job, job_id)
        if job is None:
            return
        try:
            ingest_files(session, job, files)
        except Exception as exc:  # noqa: BLE001 — job row must record the failure
            job.status = "failed"
            job.error = str(exc)
            job.progress = 100
            session.add(job)
            session.commit()


@router.get("/imports/{job_id}", response_model=JobStatus, summary="Poll an import job")
def get_import(job_id: str, session: DbSession) -> JobStatus:
    job = session.get(Job, job_id)
    if job is None:
        raise AppError(404, "NOT_FOUND", "Import job not found.")
    files = job.result.get("files", []) if isinstance(job.result, dict) else []
    return JobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        files=files,
        error=job.error,
    )


@router.get(
    "/import-issues",
    response_model=Page[ImportIssueOut],
    summary="Rows skipped or warned during import",
)
def import_issues(session: DbSession, page: int = 1, page_size: int = 100) -> Page[ImportIssueOut]:
    rows = list_issues(session)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 500)
    start = (page - 1) * page_size
    window = rows[start : start + page_size]
    return Page(
        items=[ImportIssueOut.model_validate(item) for item in window],
        total=len(rows),
        page=page,
        page_size=page_size,
    )


@router.get("/import-issues.csv", summary="Download import issues as CSV")
def import_issues_csv(session: DbSession) -> Response:
    from app.models import ImportIssue

    class _View:
        def __init__(self, row: dict) -> None:
            self.source = row["source"]
            self.row_number = row["row_number"]
            self.severity = row["severity"]
            self.reason = row["reason"]
            self.raw_text = row["raw_text"]

    del ImportIssue
    text = issues_csv([_View(row) for row in list_issues(session)])
    return Response(
        content=text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=import-issues.csv"},
    )


@router.post(
    "/mapping/suggest", response_model=MappingSuggestResponse, summary="Suggest a column mapping"
)
@limiter.limit("30/minute")
async def mapping_suggest(
    request: Request, body: MappingSuggestRequest, settings: AppSettings, _actor: Actor
) -> MappingSuggestResponse:
    fuzzy = suggest_mapping(body.headers, body.sample_rows)
    llm = await suggest_with_llm(body.headers, body.sample_rows, settings)
    suggestions = llm or fuzzy
    return MappingSuggestResponse(
        suggestions=[MappingSuggestion.model_validate(item) for item in suggestions],
        llm_used=bool(llm),
    )


@router.post(
    "/mapping/preview",
    response_model=MappingPreviewResponse,
    summary="Preview 10 rows for a mapping",
)
async def mapping_preview(body: MappingPreviewRequest, _actor: Actor) -> MappingPreviewResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=body.headers)
    writer.writeheader()
    for row in body.rows:
        writer.writerow({header: row.get(header, "") for header in body.headers})
    connector = GenericMappedConnector(body.mapping, source_name=body.source_name)
    drafts, issues = connector.parse("preview.csv", buffer.getvalue())
    return MappingPreviewResponse(
        rows=[
            PreviewRow(
                source_row=draft.source_row,
                ts_utc=draft.ts_utc,
                kind=draft.kind,
                asset=draft.asset,
                side=draft.side,
                qty=draft.qty,
                price_inr=draft.price_inr,
            )
            for draft in drafts[:10]
        ],
        issues=[
            {"row_number": issue.row_number, "reason": issue.reason, "raw_text": issue.raw_text}
            for issue in issues
        ],
    )


@router.post(
    "/mapping/profiles", response_model=MappingProfileOut, summary="Save a connector profile"
)
def save_profile(
    body: MappingProfileRequest, session: DbSession, _actor: Actor
) -> MappingProfileOut:
    signature = header_signature(body.headers)
    from sqlmodel import select

    existing = session.exec(
        select(ConnectorProfile).where(ConnectorProfile.header_signature == signature)
    ).first()
    if existing is None:
        existing = ConnectorProfile(
            name=body.name, header_signature=signature, mapping=body.mapping
        )
    else:
        existing.name = body.name
        existing.mapping = body.mapping
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return MappingProfileOut(
        id=existing.id,
        name=existing.name,
        header_signature=existing.header_signature,
        mapping=existing.mapping,
    )
