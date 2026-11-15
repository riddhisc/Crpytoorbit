"""FIFO cost basis in INR. Realized gain is computed per SELL. Losses are not offset."""

from collections import deque
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.config import Settings
from app.models import CanonicalTx
from app.parsing import as_utc
from app.reconcile.matcher import TransferMatch, tx_id
from app.reconcile.prices import get_price_inr_sync

PAISA = Decimal("0.01")


@dataclass
class Lot:
    tx_id: str
    ts_utc: str
    qty: Decimal
    unit_cost: Decimal


@dataclass
class LotUse:
    acquired_ts: str
    qty: Decimal
    unit_cost: Decimal
    cost: Decimal


@dataclass
class SaleResult:
    tx_id: str
    asset: str
    ts_utc: str
    qty: Decimal
    proceeds: Decimal
    cost: Decimal
    gain: Decimal
    lots: list[LotUse] = field(default_factory=list)


@dataclass
class TaxSummary:
    sales: list[SaleResult]
    taxable_gain: Decimal
    net_gain: Decimal
    estimated_tax: Decimal
    tds: Decimal


def _q(value: Decimal) -> Decimal:
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def compute_fifo(
    txs: list[CanonicalTx], matches: list[TransferMatch], settings: Settings
) -> dict[str, TaxSummary]:
    matched_out = {tx_id(match.out_tx): match for match in matches}
    matched_in = {tx_id(match.in_tx) for match in matches}
    lots: dict[str, deque[Lot]] = {}
    sales: dict[str, list[SaleResult]] = {}
    ordered = sorted(
        [tx for tx in txs if not tx.excluded],
        key=lambda tx: (as_utc(tx.ts_utc), 0 if tx.kind == "TRANSFER_OUT" else 1, tx.source_row),
    )
    for tx in ordered:
        asset = tx.asset
        book = lots.setdefault(asset, deque())
        if tx.kind == "TRADE" and tx.side == "BUY":
            book.append(_buy_lot(tx, settings))
        elif tx.kind == "TRANSFER_IN" and tx.id not in matched_in:
            price = get_price_inr_sync(asset, as_utc(tx.ts_utc)) or Decimal("0")
            book.append(Lot(tx.id, as_utc(tx.ts_utc).isoformat(), _d(tx.qty), price))
        elif tx.kind == "TRANSFER_OUT":
            match = matched_out.get(tx.id)
            if match is not None:
                _consume(book, _d(match.fee_qty))
            else:
                _consume(book, _d(tx.qty))
        elif tx.kind == "TRADE" and tx.side == "SELL":
            sales.setdefault(asset, []).append(_sell(tx, book))
    result: dict[str, TaxSummary] = {}
    rate = settings.tax_rate_pct / Decimal("100")
    tds_rate = settings.tds_rate_pct / Decimal("100")
    for asset, asset_sales in sales.items():
        taxable = sum((sale.gain for sale in asset_sales if sale.gain > 0), Decimal("0"))
        net = sum((sale.gain for sale in asset_sales), Decimal("0"))
        proceeds = sum((sale.proceeds for sale in asset_sales), Decimal("0"))
        result[asset] = TaxSummary(
            sales=asset_sales,
            taxable_gain=_q(taxable),
            net_gain=_q(net),
            estimated_tax=_q(taxable * rate),
            tds=_q(proceeds * tds_rate),
        )
    return result


def _buy_lot(tx: CanonicalTx, settings: Settings) -> Lot:
    unit = _d(tx.price_inr or 0)
    qty = _d(tx.qty)
    if settings.fees_as_cost and qty > 0:
        fee = _d(tx.fee_qty or 0)
        if (tx.fee_asset or "").upper() == "INR":
            unit = unit + (fee / qty)
        elif (tx.fee_asset or "").upper() == tx.asset and tx.price_inr is not None:
            unit = unit + (fee * _d(tx.price_inr) / qty)
    return Lot(tx.id, as_utc(tx.ts_utc).isoformat(), qty, unit)


def _consume(book: deque[Lot], qty: Decimal) -> list[LotUse]:
    left = qty
    used: list[LotUse] = []
    while left > 0 and book:
        lot = book[0]
        take = lot.qty if lot.qty <= left else left
        used.append(LotUse(lot.ts_utc, take, lot.unit_cost, take * lot.unit_cost))
        lot.qty -= take
        left -= take
        if lot.qty <= 0:
            book.popleft()
    if left > 0:
        used.append(LotUse("", left, Decimal("0"), Decimal("0")))
    return used


def _sell(tx: CanonicalTx, book: deque[Lot]) -> SaleResult:
    qty = _d(tx.qty)
    price = _d(tx.price_inr or 0)
    uses = _consume(book, qty)
    cost = sum((item.cost for item in uses), Decimal("0"))
    proceeds = qty * price
    return SaleResult(
        tx_id=tx.id,
        asset=tx.asset,
        ts_utc=as_utc(tx.ts_utc).isoformat(),
        qty=qty,
        proceeds=_q(proceeds),
        cost=_q(cost),
        gain=_q(proceeds - cost),
        lots=uses,
    )
