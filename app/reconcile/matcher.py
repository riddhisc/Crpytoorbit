"""Pair TRANSFER_OUT with TRANSFER_IN. Each transaction is used at most once."""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from app.config import Settings
from app.connectors.base import CanonicalTxDraft
from app.models import CanonicalTx
from app.parsing import as_utc


@dataclass
class TransferMatch:
    out_tx: CanonicalTx | CanonicalTxDraft
    in_tx: CanonicalTx | CanonicalTxDraft
    match_kind: str
    fee_qty: Decimal


def _qty(tx: CanonicalTx | CanonicalTxDraft) -> Decimal:
    return Decimal(str(tx.qty))


def _hash(tx: CanonicalTx | CanonicalTxDraft) -> str:
    return (tx.tx_hash or "").strip().lower()


def tx_id(tx: CanonicalTx | CanonicalTxDraft) -> str:
    value = getattr(tx, "id", None)
    if not isinstance(value, str):
        raise RuntimeError("transfer row is missing an id")
    return value


def _within_tolerance(sent: Decimal, received: Decimal, tolerance_pct: Decimal) -> bool:
    if sent <= 0 or received <= 0 or received > sent:
        return False
    gap = (sent - received) / sent * Decimal("100")
    return gap <= tolerance_pct


def match_transfers(
    txs: list[CanonicalTx] | list[CanonicalTxDraft],
    settings: Settings,
) -> list[TransferMatch]:
    outs = [tx for tx in txs if tx.kind == "TRANSFER_OUT" and not getattr(tx, "excluded", False)]
    ins = [tx for tx in txs if tx.kind == "TRANSFER_IN" and not getattr(tx, "excluded", False)]
    used_out: set[int] = set()
    used_in: set[int] = set()
    matches: list[TransferMatch] = []

    for i, out_tx in enumerate(outs):
        digest = _hash(out_tx)
        if not digest:
            continue
        for j, in_tx in enumerate(ins):
            if j in used_in or i in used_out:
                continue
            if _hash(in_tx) == digest and out_tx.asset == in_tx.asset:
                used_out.add(i)
                used_in.add(j)
                sent, received = _qty(out_tx), _qty(in_tx)
                matches.append(
                    TransferMatch(
                        out_tx, in_tx, "hash", sent - received if sent >= received else Decimal("0")
                    )
                )
                break

    window = timedelta(hours=settings.transfer_window_hours)
    candidates: list[tuple[Decimal, Decimal, int, int]] = []
    for i, out_tx in enumerate(outs):
        if i in used_out:
            continue
        for j, in_tx in enumerate(ins):
            if j in used_in or out_tx.asset != in_tx.asset:
                continue
            delta = abs(as_utc(out_tx.ts_utc) - as_utc(in_tx.ts_utc))
            if delta > window:
                continue
            sent, received = _qty(out_tx), _qty(in_tx)
            if not _within_tolerance(sent, received, settings.transfer_tolerance_pct):
                continue
            hours = Decimal(str(delta.total_seconds())) / Decimal("3600")
            qty_gap = sent - received
            candidates.append((hours, qty_gap, i, j))
    candidates.sort()
    for _hours, _gap, i, j in candidates:
        if i in used_out or j in used_in:
            continue
        out_tx, in_tx = outs[i], ins[j]
        sent, received = _qty(out_tx), _qty(in_tx)
        used_out.add(i)
        used_in.add(j)
        matches.append(TransferMatch(out_tx, in_tx, "heuristic", sent - received))
    return matches
