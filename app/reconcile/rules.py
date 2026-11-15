"""Exception rules. Every flag explains itself in plain English."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from app.config import Settings
from app.models import CanonicalTx
from app.parsing import as_utc, dec_str
from app.reconcile.matcher import TransferMatch, tx_id
from app.reconcile.prices import get_price_inr_sync


@dataclass
class ExceptionDraft:
    type: str
    severity: str
    asset: str | None
    source: str | None
    ts_utc: datetime | None
    estimated_value_inr: Decimal | None
    explanation: str
    suggested_fix: str
    fingerprint: str
    related_ids: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    exclude_tx_ids: list[str] = field(default_factory=list)


def fingerprint(exc_type: str, keys: list[str]) -> str:
    payload = exc_type + "|" + ",".join(sorted(keys))
    return hashlib.sha256(payload.encode()).hexdigest()


def _money(qty: Decimal, price: Decimal | None) -> Decimal | None:
    if price is None:
        return None
    return (qty * price).quantize(Decimal("0.01"))


def _fmt_qty(qty: Decimal) -> str:
    return dec_str(qty).rstrip("0").rstrip(".") or "0"


def build_exceptions(
    txs: list[CanonicalTx],
    matches: list[TransferMatch],
    balances: dict[str, Decimal],
    settings: Settings,
) -> list[ExceptionDraft]:
    by_id = {tx.id: tx for tx in txs}
    matched_ids = set()
    for match in matches:
        matched_ids.add(tx_id(match.out_tx))
        matched_ids.add(tx_id(match.in_tx))
    drafts: list[ExceptionDraft] = []
    drafts.extend(_duplicates(txs))
    excluded = {tx_id for draft in drafts for tx_id in draft.exclude_tx_ids}
    active = [tx for tx in txs if tx.id not in excluded and not tx.excluded]
    drafts.extend(_unmatched(active, matched_ids, settings))
    drafts.extend(_negative_balances(active, balances))
    drafts.extend(_price_and_fees(active, settings))
    drafts.extend(_large_unexplained(active, matched_ids, by_id, settings))
    return drafts


def _duplicates(txs: list[CanonicalTx]) -> list[ExceptionDraft]:
    groups: dict[tuple[Any, ...], list[CanonicalTx]] = {}
    for tx in txs:
        if tx.kind != "TRADE":
            continue
        key = (
            tx.source,
            as_utc(tx.ts_utc).isoformat(),
            tx.asset,
            tx.side,
            dec_str(Decimal(str(tx.qty))),
            dec_str(Decimal(str(tx.price_inr)) if tx.price_inr is not None else None),
        )
        groups.setdefault(key, []).append(tx)
    drafts: list[ExceptionDraft] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: item.source_row)
        if len(ordered) < 2:
            continue
        for extra in ordered[1:]:
            keys = [ordered[0].stable_key, extra.stable_key]
            price = Decimal(str(extra.price_inr)) if extra.price_inr is not None else None
            drafts.append(
                ExceptionDraft(
                    type="DUPLICATE_TRADE",
                    severity="medium",
                    asset=extra.asset,
                    source=extra.source,
                    ts_utc=as_utc(extra.ts_utc),
                    estimated_value_inr=_money(Decimal(str(extra.qty)), price),
                    explanation=(
                        f"{extra.source.title()} lists the same {extra.side} of {_fmt_qty(Decimal(str(extra.qty)))} "
                        f"{extra.asset} twice at {as_utc(extra.ts_utc).strftime('%Y-%m-%d %H:%M')} UTC. "
                        "The first row is kept; the repeat is held out of the ledger and tax estimate until you resolve it."
                    ),
                    suggested_fix="Confirm the second row is a duplicate export. Resolve to keep it out, or reopen if both fills were real.",
                    fingerprint=fingerprint("DUPLICATE_TRADE", keys),
                    related_ids=[ordered[0].id, extra.id],
                    exclude_tx_ids=[extra.id],
                )
            )
    return drafts


def _unmatched(
    txs: list[CanonicalTx], matched_ids: set[str], settings: Settings
) -> list[ExceptionDraft]:
    drafts: list[ExceptionDraft] = []
    window = timedelta(hours=settings.transfer_window_hours)
    for tx in txs:
        if tx.id in matched_ids:
            continue
        if tx.kind == "TRANSFER_OUT" and tx.source != "wallet":
            closest = _closest(tx, txs, "TRANSFER_IN")
            price = get_price_inr_sync(tx.asset, as_utc(tx.ts_utc))
            drafts.append(
                ExceptionDraft(
                    type="UNMATCHED_WITHDRAWAL",
                    severity="high",
                    asset=tx.asset,
                    source=tx.source,
                    ts_utc=as_utc(tx.ts_utc),
                    estimated_value_inr=_money(Decimal(str(tx.qty)), price),
                    explanation=(
                        f"{tx.source.title()} shows a withdrawal of {_fmt_qty(Decimal(str(tx.qty)))} {tx.asset} "
                        f"on {as_utc(tx.ts_utc).strftime('%Y-%m-%d')} but no matching deposit appears in the wallet "
                        f"within {settings.transfer_window_hours} hours."
                    ),
                    suggested_fix=(
                        "Check the destination address on the exchange. The funds may have gone to another wallet. "
                        "If so, import that wallet too."
                    ),
                    fingerprint=fingerprint("UNMATCHED_WITHDRAWAL", [tx.stable_key]),
                    related_ids=[tx.id] + ([closest.id] if closest else []),
                    details={
                        "candidate_tx_id": closest.id if closest else None,
                        "window_hours": settings.transfer_window_hours,
                    },
                )
            )
        elif tx.kind == "TRANSFER_IN" and tx.source == "wallet":
            closest = _closest(tx, txs, "TRANSFER_OUT")
            price = get_price_inr_sync(tx.asset, as_utc(tx.ts_utc))
            outside = ""
            if closest is not None and abs(as_utc(closest.ts_utc) - as_utc(tx.ts_utc)) > window:
                outside = " The nearest exchange withdrawal is outside the matching window."
            drafts.append(
                ExceptionDraft(
                    type="UNMATCHED_DEPOSIT",
                    severity="high",
                    asset=tx.asset,
                    source=tx.source,
                    ts_utc=as_utc(tx.ts_utc),
                    estimated_value_inr=_money(Decimal(str(tx.qty)), price),
                    explanation=(
                        f"The wallet received {_fmt_qty(Decimal(str(tx.qty)))} {tx.asset} on "
                        f"{as_utc(tx.ts_utc).strftime('%Y-%m-%d')} but no exchange withdrawal matches it."
                        + outside
                    ),
                    suggested_fix="Import the exchange withdrawal that funded this deposit, or ignore it if it came from outside this portfolio.",
                    fingerprint=fingerprint("UNMATCHED_DEPOSIT", [tx.stable_key]),
                    related_ids=[tx.id] + ([closest.id] if closest else []),
                    details={"candidate_tx_id": closest.id if closest else None},
                )
            )
    return drafts


def _closest(tx: CanonicalTx, txs: list[CanonicalTx], kind: str) -> CanonicalTx | None:
    pool = [
        other
        for other in txs
        if other.kind == kind and other.asset == tx.asset and other.id != tx.id
    ]
    if not pool:
        return None
    return min(pool, key=lambda other: abs(as_utc(other.ts_utc) - as_utc(tx.ts_utc)))


def _negative_balances(
    txs: list[CanonicalTx], balances: dict[str, Decimal]
) -> list[ExceptionDraft]:
    """`balances` maps tx id -> running balance AFTER that row."""
    drafts: list[ExceptionDraft] = []
    for tx in txs:
        if tx.kind not in {"TRADE", "TRANSFER_OUT"}:
            continue
        if tx.kind == "TRADE" and tx.side != "SELL":
            continue
        balance = balances.get(tx.id)
        if balance is None or balance >= 0:
            continue
        price = (
            Decimal(str(tx.price_inr))
            if tx.price_inr is not None
            else get_price_inr_sync(tx.asset, as_utc(tx.ts_utc))
        )
        drafts.append(
            ExceptionDraft(
                type="NEGATIVE_BALANCE",
                severity="high",
                asset=tx.asset,
                source=tx.source,
                ts_utc=as_utc(tx.ts_utc),
                estimated_value_inr=_money(abs(balance), price),
                explanation=(
                    f"Selling or sending {_fmt_qty(Decimal(str(tx.qty)))} {tx.asset} on "
                    f"{as_utc(tx.ts_utc).strftime('%Y-%m-%d')} takes the running balance to "
                    f"{_fmt_qty(balance)} {tx.asset}. Earlier buys or deposits look missing."
                ),
                suggested_fix="Import the earlier buy or deposit for this asset. Until then the tax estimate treats the missing quantity as zero cost.",
                fingerprint=fingerprint("NEGATIVE_BALANCE", [tx.stable_key]),
                related_ids=[tx.id],
                details={"balance_after": dec_str(balance)},
            )
        )
    return drafts


def _price_and_fees(txs: list[CanonicalTx], settings: Settings) -> list[ExceptionDraft]:
    drafts: list[ExceptionDraft] = []
    for tx in txs:
        if tx.kind != "TRADE":
            continue
        fee = Decimal(str(tx.fee_qty or 0))
        missing = bool((tx.raw or {}).get("_fee_missing")) or fee == 0
        if missing:
            price = Decimal(str(tx.price_inr)) if tx.price_inr is not None else None
            drafts.append(
                ExceptionDraft(
                    type="MISSING_FEE",
                    severity="low",
                    asset=tx.asset,
                    source=tx.source,
                    ts_utc=as_utc(tx.ts_utc),
                    estimated_value_inr=_money(Decimal(str(tx.qty)), price),
                    explanation=(
                        f"The {tx.side} of {_fmt_qty(Decimal(str(tx.qty)))} {tx.asset} on "
                        f"{tx.source.title()} has a blank or zero fee."
                    ),
                    suggested_fix="Check the exchange fill. A missing fee slightly changes cost basis if you later treat fees as cost.",
                    fingerprint=fingerprint("MISSING_FEE", [tx.stable_key]),
                    related_ids=[tx.id],
                )
            )
        if tx.price_inr is None:
            continue
        market = get_price_inr_sync(tx.asset, as_utc(tx.ts_utc))
        if market is None or market == 0:
            continue
        trade_price = Decimal(str(tx.price_inr))
        deviation = abs(trade_price - market) / market * Decimal("100")
        if deviation > settings.price_deviation_pct:
            drafts.append(
                ExceptionDraft(
                    type="PRICE_DEVIATION",
                    severity="medium",
                    asset=tx.asset,
                    source=tx.source,
                    ts_utc=as_utc(tx.ts_utc),
                    estimated_value_inr=_money(Decimal(str(tx.qty)), abs(trade_price - market)),
                    explanation=(
                        f"The {tx.side} price of ₹{dec_str(trade_price)} per {tx.asset} on "
                        f"{as_utc(tx.ts_utc).strftime('%Y-%m-%d')} is {deviation.quantize(Decimal('0.1'))}% away from "
                        f"the day's market price of ₹{dec_str(market)}."
                    ),
                    suggested_fix="Confirm the fill price and quote currency. A wrong price flows straight into the tax estimate.",
                    fingerprint=fingerprint("PRICE_DEVIATION", [tx.stable_key]),
                    related_ids=[tx.id],
                    details={
                        "trade_price": dec_str(trade_price),
                        "market_price": dec_str(market),
                        "deviation_pct": dec_str(deviation.quantize(Decimal("0.01"))),
                    },
                )
            )
    return drafts


def _large_unexplained(
    txs: list[CanonicalTx],
    matched_ids: set[str],
    by_id: dict[str, CanonicalTx],
    settings: Settings,
) -> list[ExceptionDraft]:
    del by_id
    drafts: list[ExceptionDraft] = []
    for tx in txs:
        if tx.kind not in {"TRANSFER_IN", "TRANSFER_OUT"} or tx.id in matched_ids:
            continue
        price = get_price_inr_sync(tx.asset, as_utc(tx.ts_utc))
        value = _money(Decimal(str(tx.qty)), price)
        if value is None or value < settings.large_transfer_inr:
            continue
        drafts.append(
            ExceptionDraft(
                type="LARGE_TRANSFER_UNEXPLAINED",
                severity="medium",
                asset=tx.asset,
                source=tx.source,
                ts_utc=as_utc(tx.ts_utc),
                estimated_value_inr=value,
                explanation=(
                    f"A {tx.kind.replace('_', ' ').lower()} of {_fmt_qty(Decimal(str(tx.qty)))} {tx.asset} "
                    f"is worth about ₹{dec_str(value)} and has no counterpart."
                ),
                suggested_fix="Match this movement to the other venue, or add a note explaining why it stands alone.",
                fingerprint=fingerprint("LARGE_TRANSFER_UNEXPLAINED", [tx.stable_key]),
                related_ids=[tx.id],
            )
        )
    return drafts
