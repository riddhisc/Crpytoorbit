"""WazirX-style CSV adapter. Dates are IST and converted to UTC."""

from datetime import UTC
from decimal import Decimal

from app.connectors.base import CanonicalTxDraft, Connector, ImportIssueDraft
from app.connectors.csvutil import find_header, iter_data, read_csv_rows, row_text
from app.parsing import IST, canonical_asset, parse_datetime, parse_decimal, split_pair

HEADER = {"Date", "Market", "Side", "Price (INR)", "Volume", "Total (INR)", "Fee", "Fee Currency"}


class WazirxConnector(Connector):
    name = "wazirx"

    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        labels = set(headers)
        return "Market" in labels and "Fee Currency" in labels

    def parse(
        self, filename: str, text: str
    ) -> tuple[list[CanonicalTxDraft], list[ImportIssueDraft]]:
        rows = read_csv_rows(text)
        header_index = find_header(rows, HEADER)
        drafts: list[CanonicalTxDraft] = []
        issues: list[ImportIssueDraft] = []
        if header_index < 0:
            issues.append(ImportIssueDraft("wazirx", 1, "error", "unparseable date", text[:500]))
            return drafts, issues
        for row_number, data in iter_data(rows, header_index):
            raw_text = row_text(data)
            try:
                draft = _parse_row(row_number, data)
            except ValueError as exc:
                issues.append(
                    ImportIssueDraft("wazirx", row_number, "warning", _reason(exc), raw_text)
                )
                continue
            drafts.append(draft)
            if draft.fee_missing:
                issues.append(
                    ImportIssueDraft("wazirx", row_number, "warning", "missing fee", raw_text)
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


def _parse_row(row_number: int, data: dict[str, str]) -> CanonicalTxDraft:
    try:
        ts = parse_datetime(data.get("Date", ""), assume_tz=IST).astimezone(UTC)
    except ValueError as exc:
        raise ValueError("unparseable date") from exc
    try:
        asset, quote = split_pair(data.get("Market", ""))
    except ValueError as exc:
        raise ValueError("unknown ticker") from exc
    side_raw = (data.get("Side") or "").strip().upper()
    if side_raw not in {"BUY", "SELL"}:
        raise ValueError("unknown side")
    try:
        qty = parse_decimal(data.get("Volume"))
    except ValueError as exc:
        raise ValueError("non-numeric quantity") from exc
    if qty < 0:
        raise ValueError("negative quantity")
    if qty == 0:
        raise ValueError("non-numeric quantity")
    try:
        price = parse_decimal(data.get("Price (INR)"))
    except ValueError as exc:
        raise ValueError("non-numeric quantity") from exc
    if quote != "INR":
        asset = canonical_asset(asset)
    fee_raw = (data.get("Fee") or "").strip()
    fee_missing = fee_raw == ""
    if fee_missing:
        fee = Decimal("0")
    else:
        try:
            fee = parse_decimal(fee_raw)
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
    fee_asset = (data.get("Fee Currency") or "").strip().upper() or None
    return CanonicalTxDraft(
        source="wazirx",
        source_row=row_number,
        ts_utc=ts,
        kind="TRADE",
        asset=asset,
        side=side_raw,
        qty=qty,
        price_inr=price,
        fee_qty=fee,
        fee_asset=fee_asset,
        raw=dict(data),
        fee_missing=fee_missing,
    )
