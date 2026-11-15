"""Persist connector output, then reconcile."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Session, select

from app.config import get_settings
from app.connectors.base import CanonicalTxDraft, ImportIssueDraft
from app.connectors.registry import detect_connector, extract_headers
from app.errors import AppError
from app.logging import get_logger
from app.models import CanonicalTx, ConnectorProfile, ImportBatch, ImportIssue, Job, utcnow
from app.parsing import stable_key
from app.reconcile.service import reconcile

logger = get_logger("ingest")


class _DraftCheck(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    qty: Decimal
    asset: str
    kind: str

    @field_validator("qty")
    @classmethod
    def positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("negative quantity")
        return value


def content_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_text(payload: bytes) -> str:
    return payload.decode("utf-8-sig", errors="replace")


def preflight(files: list[tuple[str, bytes]], session: Session) -> None:
    profiles = list(session.exec(select(ConnectorProfile)).all())
    unknown: list[dict[str, object]] = []
    for filename, payload in files:
        if len(payload) > get_settings().max_upload_bytes:
            raise AppError(413, "FILE_TOO_LARGE", f"{filename} exceeds the upload size limit.")
        text = decode_text(payload)
        connector = detect_connector(filename, text, profiles)
        if connector is None:
            unknown.append({"filename": filename, "headers": extract_headers(filename, text)})
    if unknown:
        raise AppError(
            422,
            "UNSUPPORTED_FILE",
            "No connector recognized this file. Map the columns, save a profile, and upload again.",
            {"files": unknown},
        )


def ingest_files(session: Session, job: Job, files: list[tuple[str, bytes]]) -> dict[str, object]:
    profiles = list(session.exec(select(ConnectorProfile)).all())
    file_results: list[dict[str, object]] = []
    job.status = "running"
    job.progress = 5
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    total = max(len(files), 1)
    for index, (filename, payload) in enumerate(files):
        digest = content_hash(payload)
        existing = session.exec(
            select(ImportBatch).where(ImportBatch.content_sha256 == digest)
        ).first()
        if existing is not None:
            file_results.append(
                {
                    "import_id": existing.id,
                    "filename": filename,
                    "connector": existing.connector,
                    "confidence": existing.confidence,
                    "rows_imported": existing.rows_imported,
                    "rows_skipped": existing.rows_skipped,
                    "duplicate": True,
                }
            )
            job.progress = 10 + int(70 * (index + 1) / total)
            session.add(job)
            session.commit()
            continue
        text = decode_text(payload)
        connector = detect_connector(filename, text, profiles)
        batch = ImportBatch(
            job_id=job.id,
            filename=_safe_name(filename),
            content_sha256=digest,
            connector=connector.name if connector else None,
            confidence=connector.confidence if connector else None,
            status="running",
        )
        session.add(batch)
        session.commit()
        if connector is None:
            batch.status = "failed"
            session.add(batch)
            session.commit()
            raise AppError(
                422,
                "UNSUPPORTED_FILE",
                "No connector recognized this file.",
                {"files": [{"filename": filename, "headers": extract_headers(filename, text)}]},
            )
        started = datetime.now(UTC)
        drafts, issues = connector.parse(filename, text)
        logger.info(
            "parse_done",
            connector=connector.name,
            rows=len(drafts),
            issues=len(issues),
            ms=_ms(started),
        )
        if len(drafts) + len(issues) > get_settings().max_rows:
            raise AppError(413, "FILE_TOO_LARGE", "Row count exceeds the configured cap.")
        imported, skipped = _persist_rows(session, batch, drafts, issues)
        batch.rows_imported = imported
        batch.rows_skipped = skipped
        batch.status = "done"
        session.add(batch)
        session.commit()
        file_results.append(
            {
                "import_id": batch.id,
                "filename": filename,
                "connector": connector.name,
                "confidence": connector.confidence,
                "rows_imported": imported,
                "rows_skipped": skipped,
                "duplicate": False,
            }
        )
        job.progress = 10 + int(70 * (index + 1) / total)
        session.add(job)
        session.commit()
    job.progress = 80
    session.add(job)
    session.commit()
    summary = reconcile(session)
    result: dict[str, object] = {"files": file_results, "reconcile": summary}
    job.status = "done"
    job.progress = 100
    job.result = result
    job.message = "Import complete."
    job.updated_at = utcnow()
    session.add(job)
    session.commit()
    return result


def _persist_rows(
    session: Session,
    batch: ImportBatch,
    drafts: list[CanonicalTxDraft],
    issues: list,
) -> tuple[int, int]:
    imported = 0
    for draft in drafts:
        try:
            _DraftCheck(qty=draft.qty, asset=draft.asset, kind=draft.kind)
        except Exception:
            issues.append(
                ImportIssueDraft(
                    draft.source, draft.source_row, "warning", "negative quantity", str(draft.raw)
                )
            )
            continue
        raw = dict(draft.raw)
        raw["_fee_missing"] = draft.fee_missing
        tx = CanonicalTx(
            source=draft.source,
            source_row=draft.source_row,
            import_id=batch.id,
            ts_utc=draft.ts_utc,
            kind=draft.kind,
            asset=draft.asset,
            side=draft.side,
            qty=draft.qty,
            price_inr=draft.price_inr,
            fee_qty=draft.fee_qty,
            fee_asset=draft.fee_asset,
            tx_hash=draft.tx_hash,
            counterparty=draft.counterparty,
            raw=raw,
            excluded=False,
            stable_key=stable_key(
                draft.source,
                draft.source_row,
                draft.ts_utc,
                draft.kind,
                draft.asset,
                draft.side,
                draft.qty,
                draft.price_inr,
                draft.tx_hash,
            ),
        )
        session.add(tx)
        imported += 1
    for issue in issues:
        if issue is None:
            continue
        session.add(
            ImportIssue(
                import_id=batch.id,
                source=issue.source,
                row_number=issue.row_number,
                severity=issue.severity,
                reason=issue.reason,
                raw_text=issue.raw_text,
            )
        )
    session.commit()
    skipped_reasons = {
        "unparseable date",
        "non-numeric quantity",
        "unknown side",
        "negative quantity",
        "unknown ticker",
    }
    skipped = sum(1 for issue in issues if issue is not None and issue.reason in skipped_reasons)
    return imported, skipped


def _safe_name(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    cleaned = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in name)
    return cleaned[:180] or "upload.csv"


def _ms(started: datetime) -> float:
    return round((datetime.now(UTC) - started).total_seconds() * 1000, 2)
