"""Column-mapping connector for exchange files we have not seen before."""

from datetime import UTC
from decimal import Decimal

from app.connectors.base import CanonicalTxDraft, Connector, ImportIssueDraft
from app.connectors.csvutil import iter_data, read_csv_rows, row_text
from app.parsing import canonical_asset, parse_datetime, parse_decimal

CANONICAL_FIELDS = ("ts", "asset", "side", "qty", "price", "fee", "fee_asset", "tx_hash", "pair")


class GenericMappedConnector(Connector):
    name = "generic"

    def __init__(self, mapping: dict[str, str], source_name: str = "custom") -> None:
        self.mapping = mapping
        self.source_name = source_name
        self.name = source_name
        self.confidence = "medium"

    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        return False

    def parse(
        self, filename: str, text: str
    ) -> tuple[list[CanonicalTxDraft], list[ImportIssueDraft]]:
        rows = read_csv_rows(text)
        if not rows:
            return [], [ImportIssueDraft(self.source_name, 1, "error", "unparseable date", "")]
        header_index = 0
        drafts: list[CanonicalTxDraft] = []
        issues: list[ImportIssueDraft] = []
        for row_number, data in iter_data(rows, header_index):
            try:
                drafts.append(self._parse_row(row_number, data))
            except ValueError as exc:
                reason = str(exc)
                for known in (
                    "unparseable date",
                    "non-numeric quantity",
                    "unknown side",
                    "negative quantity",
                    "unknown ticker",
                ):
                    if known in reason:
                        reason = known
                        break
                issues.append(
                    ImportIssueDraft(
                        self.source_name, row_number, "warning", reason, row_text(data)
                    )
                )
        return drafts, issues

    def _cell(self, data: dict[str, str], field: str) -> str:
        header = self.mapping.get(field) or ""
        if not header:
            return ""
        if header in data:
            return data[header]
        for key, value in data.items():
            if key.strip().lower() == header.strip().lower():
                return value
        return ""

    def _parse_row(self, row_number: int, data: dict[str, str]) -> CanonicalTxDraft:
        try:
            ts = parse_datetime(self._cell(data, "ts"), assume_tz=UTC)
        except ValueError as exc:
            raise ValueError("unparseable date") from exc
        pair = self._cell(data, "pair")
        asset_raw = self._cell(data, "asset")
        try:
            if pair and "/" in pair:
                asset = canonical_asset(pair.split("/", 1)[0])
            else:
                asset = canonical_asset(asset_raw)
        except ValueError as exc:
            raise ValueError("unknown ticker") from exc
        side_raw = self._cell(data, "side").strip().upper()
        kind = "TRADE"
        side: str | None
        if side_raw in {"BUY", "SELL"}:
            side = side_raw
        elif side_raw in {"WITHDRAW", "OUT", "SEND"}:
            kind = "TRANSFER_OUT"
            side = None
        elif side_raw in {"DEPOSIT", "IN", "RECEIVE"}:
            kind = "TRANSFER_IN"
            side = None
        else:
            raise ValueError("unknown side")
        try:
            qty = parse_decimal(self._cell(data, "qty"))
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
        if qty < 0:
            raise ValueError("negative quantity")
        if qty == 0:
            raise ValueError("non-numeric quantity")
        price_raw = self._cell(data, "price").strip()
        fee_raw = self._cell(data, "fee").strip()
        fee_missing = fee_raw == ""
        try:
            price = parse_decimal(price_raw) if price_raw else None
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
        try:
            fee = Decimal("0") if fee_missing else parse_decimal(fee_raw)
        except ValueError as exc:
            raise ValueError("non-numeric quantity") from exc
        fee_asset_raw = self._cell(data, "fee_asset").strip().upper() or None
        tx_hash = self._cell(data, "tx_hash").strip() or None
        return CanonicalTxDraft(
            source=self.source_name,
            source_row=row_number,
            ts_utc=ts,
            kind=kind,
            asset=asset,
            side=side,
            qty=qty,
            price_inr=price if kind == "TRADE" else None,
            fee_qty=fee,
            fee_asset=fee_asset_raw,
            tx_hash=tx_hash,
            raw=dict(data),
            fee_missing=fee_missing and kind == "TRADE",
        )
