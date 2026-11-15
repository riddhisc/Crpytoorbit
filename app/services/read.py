"""Read models for ledger, exceptions, summary, and tax."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, func, select

from app.config import get_settings
from app.models import (
    CanonicalTx,
    ExceptionRecord,
    ExceptionRelatedTx,
    ImportBatch,
    ImportIssue,
    MatchedTransfer,
    ResolutionEvent,
)
from app.parsing import as_utc, dec_str
from app.reconcile.fifo import compute_fifo
from app.reconcile.matcher import TransferMatch
from app.reconcile.prices import get_price_inr_sync
from app.repositories.analytics import holdings, running_balances


def _match_notes(session: Session) -> dict[str, tuple[str, str]]:
    notes: dict[str, tuple[str, str]] = {}
    for match in session.exec(select(MatchedTransfer)).all():
        fee = dec_str(Decimal(str(match.fee_qty))).rstrip("0").rstrip(".") or "0"
        note = f"matched, network fee {fee}"
        notes[match.out_tx_id] = (match.in_tx_id, note)
        notes[match.in_tx_id] = (match.out_tx_id, note)
    return notes


def list_ledger(
    session: Session,
    *,
    asset: str | None,
    source: str | None,
    kind: str | None,
    start: datetime | None,
    end: datetime | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    query = select(CanonicalTx)
    if asset:
        query = query.where(CanonicalTx.asset == asset.upper())
    if source:
        query = query.where(CanonicalTx.source == source)
    if kind:
        query = query.where(CanonicalTx.kind == kind)
    if start:
        query = query.where(col(CanonicalTx.ts_utc) >= start)
    if end:
        query = query.where(col(CanonicalTx.ts_utc) <= end)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    order_map: dict[str, Any] = {
        "ts_asc": col(CanonicalTx.ts_utc).asc(),
        "ts_desc": col(CanonicalTx.ts_utc).desc(),
        "asset": col(CanonicalTx.asset).asc(),
        "qty": col(CanonicalTx.qty).desc(),
    }
    rows = session.exec(
        query.order_by(order_map.get(sort, col(CanonicalTx.ts_utc).desc()))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    balances = running_balances(session)
    notes = _match_notes(session)
    items = []
    for tx in rows:
        matched = notes.get(tx.id)
        items.append(
            {
                "id": tx.id,
                "source": tx.source,
                "source_row": tx.source_row,
                "ts_utc": as_utc(tx.ts_utc),
                "kind": tx.kind,
                "asset": tx.asset,
                "side": tx.side,
                "qty": Decimal(str(tx.qty)),
                "price_inr": Decimal(str(tx.price_inr)) if tx.price_inr is not None else None,
                "fee_qty": Decimal(str(tx.fee_qty or 0)),
                "fee_asset": tx.fee_asset,
                "tx_hash": tx.tx_hash,
                "counterparty": tx.counterparty,
                "excluded": tx.excluded,
                "running_balance": balances.get(tx.id),
                "matched_tx_id": matched[0] if matched else None,
                "match_note": matched[1] if matched else None,
                "raw": tx.raw or {},
            }
        )
    return items, int(total)


def list_exceptions(
    session: Session,
    *,
    exc_type: str | None,
    severity: str | None,
    asset: str | None,
    source: str | None,
    status: str | None,
    start: datetime | None,
    end: datetime | None,
    q: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[ExceptionRecord], int]:
    query = select(ExceptionRecord)
    if exc_type:
        types = [part.strip() for part in exc_type.split(",") if part.strip()]
        query = query.where(col(ExceptionRecord.type).in_(types))
    if severity:
        levels = [part.strip() for part in severity.split(",") if part.strip()]
        query = query.where(col(ExceptionRecord.severity).in_(levels))
    if asset:
        query = query.where(ExceptionRecord.asset == asset.upper())
    if source:
        query = query.where(ExceptionRecord.source == source)
    if status:
        query = query.where(ExceptionRecord.status == status)
    if start:
        query = query.where(col(ExceptionRecord.ts_utc) >= start)
    if end:
        query = query.where(col(ExceptionRecord.ts_utc) <= end)
    if q:
        query = query.where(col(ExceptionRecord.explanation).contains(q))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    order: Any
    if sort == "value_desc":
        order = col(ExceptionRecord.estimated_value_inr).desc()
    elif sort == "value_asc":
        order = col(ExceptionRecord.estimated_value_inr).asc()
    elif sort == "ts_asc":
        order = col(ExceptionRecord.ts_utc).asc()
    else:
        order = col(ExceptionRecord.ts_utc).desc()
    rows = session.exec(query.order_by(order).offset((page - 1) * page_size).limit(page_size)).all()
    return list(rows), int(total)


def exception_counts(session: Session) -> dict[str, int]:
    rows = session.exec(
        select(ExceptionRecord.status, func.count()).group_by(ExceptionRecord.status)
    ).all()
    counts = {"open": 0, "resolved": 0, "ignored": 0}
    for status, count in rows:
        counts[str(status)] = int(count)
    return counts


def summary(session: Session) -> dict:
    settings = get_settings()
    total_tx = session.exec(
        select(func.count()).select_from(CanonicalTx).where(CanonicalTx.excluded == False)  # noqa: E712
    ).one()
    transfers = session.exec(
        select(func.count())
        .select_from(CanonicalTx)
        .where(
            CanonicalTx.excluded == False,  # noqa: E712
            col(CanonicalTx.kind).in_(["TRANSFER_IN", "TRANSFER_OUT"]),
        )
    ).one()
    matched_rows = session.exec(select(func.count()).select_from(MatchedTransfer)).one()
    matched_legs = int(matched_rows) * 2
    matched_pct = Decimal("0")
    if transfers:
        matched_pct = (Decimal(matched_legs) / Decimal(int(transfers)) * Decimal("100")).quantize(
            Decimal("0.01")
        )
    open_rows = list(
        session.exec(select(ExceptionRecord).where(ExceptionRecord.status == "open")).all()
    )
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    value = Decimal("0")
    per_asset: dict[str, int] = {}
    for row in open_rows:
        by_type[row.type] = by_type.get(row.type, 0) + 1
        by_severity[row.severity] = by_severity.get(row.severity, 0) + 1
        if row.asset:
            per_asset[row.asset] = per_asset.get(row.asset, 0) + 1
        if row.estimated_value_inr is not None:
            value += Decimal(str(row.estimated_value_inr))
    latest_by_asset: dict[str, datetime] = {}
    for tx in session.exec(select(CanonicalTx).where(CanonicalTx.excluded == False)).all():  # noqa: E712
        current = latest_by_asset.get(tx.asset)
        ts = as_utc(tx.ts_utc)
        if current is None or ts > current:
            latest_by_asset[tx.asset] = ts
    held = []
    for item in holdings(session):
        asset = str(item["asset"])
        qty = Decimal(str(item["qty"]))
        priced_on = latest_by_asset.get(asset, datetime(2024, 7, 31))
        price = get_price_inr_sync(asset, priced_on) or Decimal("0")
        worth = qty * price if qty > 0 else Decimal("0")
        held.append(
            {
                "asset": asset,
                "qty": qty,
                "value_inr": worth.quantize(Decimal("0.01")),
                "open_exceptions": per_asset.get(asset, 0),
            }
        )
    return {
        "total_tx": int(total_tx),
        "matched_pct": matched_pct,
        "open_exceptions": len(open_rows),
        "value_at_risk_inr": value.quantize(Decimal("0.01")),
        "by_type": by_type,
        "by_severity": by_severity,
        "holdings": held,
        "demo_mode": settings.demo_mode,
    }


def tax_report(session: Session) -> dict:
    settings = get_settings()
    txs = list(session.exec(select(CanonicalTx)).all())
    matches = []
    by_id = {tx.id: tx for tx in txs}
    for row in session.exec(select(MatchedTransfer)).all():
        out_tx = by_id.get(row.out_tx_id)
        in_tx = by_id.get(row.in_tx_id)
        if out_tx and in_tx:
            matches.append(TransferMatch(out_tx, in_tx, row.match_kind, Decimal(str(row.fee_qty))))
    computed = compute_fifo(txs, matches, settings)
    assets = []
    for asset, report in sorted(computed.items()):
        assets.append(_asset_payload(asset, report))
    all_sales = [sale for report in computed.values() for sale in report.sales]
    taxable = sum((item["taxable_gain_inr"] for item in assets), Decimal("0"))
    net = sum((item["realized_gain_inr"] for item in assets), Decimal("0"))
    tax = sum((item["estimated_tax_inr"] for item in assets), Decimal("0"))
    tds = sum((item["tds_inr"] for item in assets), Decimal("0"))
    totals = {
        "asset": "ALL",
        "realized_gain_inr": net,
        "taxable_gain_inr": taxable,
        "estimated_tax_inr": tax,
        "tds_inr": tds,
        "sales": [_sale_payload(sale) for sale in all_sales],
    }
    return {
        "assets": assets,
        "totals": totals,
        "tax_rate_pct": settings.tax_rate_pct,
        "tds_rate_pct": settings.tds_rate_pct,
        "fees_as_cost": settings.fees_as_cost,
        "disclaimer": "ESTIMATE, not tax advice. Verify against current Income Tax rules / consult a CA.",
    }


def _asset_payload(asset: str, report) -> dict:  # type: ignore[no-untyped-def]
    return {
        "asset": asset,
        "realized_gain_inr": report.net_gain,
        "taxable_gain_inr": report.taxable_gain,
        "estimated_tax_inr": report.estimated_tax,
        "tds_inr": report.tds,
        "sales": [_sale_payload(sale) for sale in report.sales],
    }


def _sale_payload(sale) -> dict:  # type: ignore[no-untyped-def]
    return {
        "tx_id": sale.tx_id,
        "ts_utc": sale.ts_utc,
        "qty": sale.qty,
        "proceeds": sale.proceeds,
        "cost": sale.cost,
        "gain": sale.gain,
        "lots": [
            {
                "acquired_ts": lot.acquired_ts,
                "qty": lot.qty,
                "unit_cost": lot.unit_cost,
                "cost": lot.cost,
            }
            for lot in sale.lots
        ],
    }


def list_issues(session: Session) -> list[dict]:
    filenames = {row.id: row.filename for row in session.exec(select(ImportBatch)).all()}
    issues = session.exec(select(ImportIssue).order_by(col(ImportIssue.row_number))).all()
    return [
        {
            "id": issue.id,
            "import_id": issue.import_id,
            "source": issue.source,
            "filename": filenames.get(issue.import_id),
            "row_number": issue.row_number,
            "severity": issue.severity,
            "reason": issue.reason,
            "raw_text": issue.raw_text,
        }
        for issue in issues
    ]


def audit_log(session: Session, page: int, page_size: int) -> tuple[list[dict], int]:
    total = session.exec(select(func.count()).select_from(ResolutionEvent)).one()
    events = session.exec(
        select(ResolutionEvent)
        .order_by(col(ResolutionEvent.created_at).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    types = {row.id: row.type for row in session.exec(select(ExceptionRecord)).all()}
    items = [
        {
            "id": event.id,
            "exception_id": event.exception_id,
            "exception_type": types.get(event.exception_id),
            "from_status": event.from_status,
            "to_status": event.to_status,
            "note": event.note,
            "actor": event.actor,
            "created_at": event.created_at,
        }
        for event in events
    ]
    return items, int(total)


def evidence_for(session: Session, exc: ExceptionRecord) -> list[dict]:
    links = session.exec(
        select(ExceptionRelatedTx).where(ExceptionRelatedTx.exception_id == exc.id)
    ).all()
    rows = []
    for link in links:
        tx = session.get(CanonicalTx, link.tx_id)
        if tx is None:
            continue
        role = "related"
        if exc.type.startswith("UNMATCHED") and tx.id != links[0].tx_id:
            role = "closest_candidate"
        rows.append(
            {
                "id": tx.id,
                "source": tx.source,
                "ts_utc": as_utc(tx.ts_utc),
                "kind": tx.kind,
                "asset": tx.asset,
                "side": tx.side,
                "qty": Decimal(str(tx.qty)),
                "price_inr": Decimal(str(tx.price_inr)) if tx.price_inr is not None else None,
                "tx_hash": tx.tx_hash,
                "raw": tx.raw or {},
                "role": role,
            }
        )
    return rows
