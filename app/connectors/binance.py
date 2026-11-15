"""Binance-style CSV adapter. Skips a title row and blank trailing rows. Prices are converted to INR."""

from datetime import UTC, datetime
from decimal import Decimal

from app.connectors.base import CanonicalTxDraft, Connector, ImportIssueDraft
from app.connectors.csvutil import find_header, iter_data, read_csv_rows, row_text
from app.parsing import parse_datetime, parse_decimal, split_pair, strip_unit
from app.reconcile.prices import usdt_inr

HEADER = {"Date(UTC)", "Pair", "Side", "Price", "Executed", "Amount", "Fee", "Fee Coin", "TxHash"}


class BinanceConnector(Connector):
    name = "binance"

    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        return "Date(UTC)" in set(headers)

    def parse(
        self, filename: str, text: str
    ) -> tuple[list[CanonicalTxDraft], list[ImportIssueDraft]]:
        rows = read_csv_rows(text)
        header_index = find_header(rows, {"Date(UTC)", "Pair", "Side", "Executed"})
        drafts: list[CanonicalTxDraft] = []
        issues: list[ImportIssueDraft] = []
        if header_index < 0:
            issues.append(ImportIssueDraft("binance", 1, "error", "unparseable date", text[:500]))
            return drafts, issues
        for row_number, data in iter_data(rows, header_index):
            try:
                draft = _parse_row(row_number, data)
            except ValueError as exc:
                issues.append(
                    ImportIssueDraft("binance", row_number, "warning", _reason(exc), row_text(data))
                )
                continue
            drafts.append(draft)
            if draft.fee_missing and draft.kind == "TRADE":
                issues.append(
                    ImportIssueDraft(
                        "binance", row_number, "warning", "missing fee", row_text(data)
                    )
                )
        return drafts, issues


def _reason(exc: ValueError) -> str:
    text = str(exc)
    for known in (
        "unparseable date",
        "non-numeric quantity",
        "unknown side",
        "negative quantity",
        "unknown ticker",
    ):
        if known in text:
            return known
    return text or "unparseable date"


def _price_in_inr(price_quote: Decimal | None, quote: str, ts: datetime) -> Decimal | None:
    if price_quote is None:
        return None
    if quote == "INR":
        return price_quote
    rate = usdt_inr(ts.date())
    if rate is None:
        return None
    return (price_quote * rate).quantize(Decimal("0.00000001"))


def _parse_row(row_number: int, data: dict[str, str]) -> CanonicalTxDraft:
    try:
        ts = parse_datetime(data.get("Date(UTC)", ""), assume_tz=UTC)
    except ValueError as exc:
        raise ValueError("unparseable date") from exc
    side_raw = (data.get("Side") or "").strip().upper()
    try:
        qty, qty_unit = strip_unit(data.get("Executed") or "")
    except ValueError as exc:
        raise ValueError("non-numeric quantity") from exc
    if qty < 0:
        raise ValueError("negative quantity")
    if qty == 0:
        raise ValueError("non-numeric quantity")
    tx_hash = (data.get("TxHash") or "").strip() or None
    fee_raw = (data.get("Fee") or "").strip()
    fee_missing = fee_raw == ""
    if fee_missing:
        fee = Decimal("0")
    else:
        try:
            fee, _fee_unit = (
                strip_unit(fee_raw)
                if any(ch.isalpha() for ch in fee_raw)
                else (parse_decimal(fee_raw), None)
            )
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
    fee_asset_raw = (data.get("Fee Coin") or "").strip()
    try:
        fee_asset = canonical_safe(fee_asset_raw) if fee_asset_raw else None
    except ValueError:
        fee_asset = fee_asset_raw.upper() or None

    if side_raw == "WITHDRAW":
        asset = canonical_safe(qty_unit or "")
        return CanonicalTxDraft(
            source="binance",
            source_row=row_number,
            ts_utc=ts,
            kind="TRANSFER_OUT",
            asset=asset,
            side=None,
            qty=qty,
            price_inr=None,
            fee_qty=fee,
            fee_asset=fee_asset,
            tx_hash=tx_hash,
            raw=dict(data),
            fee_missing=False,
        )
    if side_raw == "DEPOSIT":
        asset = canonical_safe(qty_unit or "")
        return CanonicalTxDraft(
            source="binance",
            source_row=row_number,
            ts_utc=ts,
            kind="TRANSFER_IN",
            asset=asset,
            side=None,
            qty=qty,
            price_inr=None,
            fee_qty=fee,
            fee_asset=fee_asset,
            tx_hash=tx_hash,
            raw=dict(data),
            fee_missing=False,
        )
    if side_raw not in {"BUY", "SELL"}:
        raise ValueError("unknown side")
    try:
        asset, quote = split_pair(data.get("Pair") or "")
    except ValueError as exc:
        raise ValueError("unknown ticker") from exc
    if qty_unit and qty_unit != asset:
        asset = canonical_safe(qty_unit)
    price_raw = (data.get("Price") or "").strip()
    price_quote: Decimal | None
    if price_raw == "":
        price_quote = None
    else:
        try:
            price_quote = parse_decimal(price_raw)
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
    return CanonicalTxDraft(
        source="binance",
        source_row=row_number,
        ts_utc=ts,
        kind="TRADE",
        asset=asset,
        side=side_raw,
        qty=qty,
        price_inr=_price_in_inr(price_quote, quote, ts),
        fee_qty=fee,
        fee_asset=fee_asset,
        tx_hash=tx_hash,
        raw=dict(data),
        fee_missing=fee_missing,
    )


def canonical_safe(token: str) -> str:
    from app.parsing import canonical_asset

    try:
        return canonical_asset(token)
    except ValueError as exc:
        raise ValueError("unknown ticker") from exc
