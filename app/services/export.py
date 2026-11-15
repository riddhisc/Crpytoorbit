"""CSV and PDF exports. Cells that start with = + - @ are prefixed to block spreadsheet formulas."""

from __future__ import annotations

import csv
import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlmodel import Session, col, select

from app.models import CanonicalTx, ExceptionRecord


def csv_safe(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if text[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text


def _to_csv(records: list[dict[str, str]], columns: list[str]) -> str:
    """Prefer pandas so exports stay a DataFrame operation; fall back if the native build is blocked."""
    try:
        import pandas as pd

        frame = pd.DataFrame(records, columns=columns)
        return frame.to_csv(index=False)
    except (ImportError, OSError):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in columns})
        return buffer.getvalue()


def ledger_csv(session: Session) -> str:
    rows = list(session.exec(select(CanonicalTx).order_by(col(CanonicalTx.ts_utc))).all())
    columns = [
        "id",
        "source",
        "ts_utc",
        "kind",
        "asset",
        "side",
        "qty",
        "price_inr",
        "fee_qty",
        "tx_hash",
        "excluded",
    ]
    records = [
        {
            "id": csv_safe(tx.id),
            "source": csv_safe(tx.source),
            "ts_utc": csv_safe(tx.ts_utc.isoformat()),
            "kind": csv_safe(tx.kind),
            "asset": csv_safe(tx.asset),
            "side": csv_safe(tx.side),
            "qty": csv_safe(tx.qty),
            "price_inr": csv_safe(tx.price_inr),
            "fee_qty": csv_safe(tx.fee_qty),
            "tx_hash": csv_safe(tx.tx_hash),
            "excluded": csv_safe(tx.excluded),
        }
        for tx in rows
    ]
    return _to_csv(records, columns)


def exceptions_csv(session: Session) -> str:
    rows = list(session.exec(select(ExceptionRecord).order_by(col(ExceptionRecord.ts_utc))).all())
    columns = [
        "id",
        "type",
        "severity",
        "asset",
        "status",
        "explanation",
        "suggested_fix",
        "estimated_value_inr",
    ]
    records = [
        {
            "id": csv_safe(row.id),
            "type": csv_safe(row.type),
            "severity": csv_safe(row.severity),
            "asset": csv_safe(row.asset),
            "status": csv_safe(row.status),
            "explanation": csv_safe(row.explanation),
            "suggested_fix": csv_safe(row.suggested_fix),
            "estimated_value_inr": csv_safe(row.estimated_value_inr),
        }
        for row in rows
    ]
    return _to_csv(records, columns)


def issues_csv(issues: list[Any]) -> str:
    columns = ["source", "row_number", "severity", "reason", "raw_text"]
    records = [
        {
            "source": csv_safe(issue.source),
            "row_number": csv_safe(issue.row_number),
            "severity": csv_safe(issue.severity),
            "reason": csv_safe(issue.reason),
            "raw_text": csv_safe(issue.raw_text),
        }
        for issue in issues
    ]
    return _to_csv(records, columns)


def report_pdf(session: Session, summary: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 20 * mm
    pdf.setTitle("Crypto Orbit estimate")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, y, "Crypto Orbit — reconciliation report")
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        20 * mm, y, "ESTIMATE, not tax advice. Verify figures with a chartered accountant."
    )
    y -= 10 * mm
    pdf.setFont("Helvetica", 11)
    for label, key in (
        ("Transactions", "total_tx"),
        ("Matched transfers %", "matched_pct"),
        ("Open exceptions", "open_exceptions"),
        ("Value at risk INR", "value_at_risk_inr"),
    ):
        pdf.drawString(20 * mm, y, _pdf_safe(f"{label}: {summary.get(key, '')}"))
        y -= 6 * mm
    y -= 4 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(20 * mm, y, "Open exceptions")
    y -= 7 * mm
    pdf.setFont("Helvetica", 8)
    exceptions = session.exec(select(ExceptionRecord).where(ExceptionRecord.status == "open")).all()
    for exc in exceptions:
        if y < 20 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica", 8)
        line = _pdf_safe(f"{exc.severity.upper()} {exc.type} {exc.asset or ''} — {exc.explanation}")
        pdf.drawString(20 * mm, y, line[:140])
        y -= 5 * mm
    pdf.save()
    return buffer.getvalue()


def _pdf_safe(text: str) -> str:
    cleaned = text.replace("\n", " ")
    if cleaned[:1] in {"=", "+", "-", "@"}:
        return "'" + cleaned
    return cleaned
