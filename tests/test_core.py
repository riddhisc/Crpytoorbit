"""Adapters, registry, matcher, rules, FIFO, and prices."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from app.config import Settings, get_settings
from app.connectors.binance import BinanceConnector
from app.connectors.registry import detect_connector, extract_headers
from app.connectors.wallet_json import WalletJsonConnector
from app.connectors.wazirx import WazirxConnector
from app.models import CanonicalTx
from app.parsing import parse_datetime, parse_decimal, stable_key
from app.reconcile.fifo import compute_fifo
from app.reconcile.matcher import match_transfers
from app.reconcile.prices import _memory, fallback_price, get_price_inr_sync
from app.reconcile.rules import build_exceptions

ROOT = Path(__file__).resolve().parents[1] / "sample-data"
UTC = UTC


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_parse_decimal_formats() -> None:
    assert parse_decimal("1,234.56") == Decimal("1234.56")
    assert parse_decimal("1.234,56") == Decimal("1234.56")
    assert parse_decimal("83,50") == Decimal("83.50")
    assert parse_decimal("56,00,000") == Decimal("5600000")
    assert parse_decimal("₹ 10") == Decimal("10")
    with pytest.raises(ValueError):
        parse_decimal("abc")


def test_parse_dates() -> None:
    ist = parse_datetime("12/07/2024 09:30:00", assume_tz=timezone(timedelta(hours=5, minutes=30)))
    assert ist == datetime(2024, 7, 12, 4, 0, tzinfo=UTC)
    assert parse_datetime("1719907200") == datetime(2024, 7, 2, 8, 0, tzinfo=UTC)
    with pytest.raises(ValueError):
        parse_datetime("not-a-date")


def test_wazirx_sample() -> None:
    drafts, issues = WazirxConnector().parse("wazirx_trades.csv", _read("wazirx_trades.csv"))
    reasons = [issue.reason for issue in issues]
    assert "missing fee" in reasons
    assert "unparseable date" in reasons
    assert len(drafts) == 12
    assert all(draft.ts_utc.tzinfo is not None for draft in drafts)
    assert drafts[0].ts_utc.hour == 4 and drafts[0].ts_utc.minute == 45


def test_binance_skips_title_and_blank() -> None:
    drafts, issues = BinanceConnector().parse("binance_trades.csv", _read("binance_trades.csv"))
    assert issues == []
    assert len(drafts) == 19
    withdraws = [row for row in drafts if row.kind == "TRANSFER_OUT"]
    assert len(withdraws) == 2
    assert withdraws[0].qty == Decimal("1")
    assert withdraws[0].tx_hash.startswith("0xaaa")
    assert drafts[0].price_inr is not None
    assert abs(drafts[0].price_inr - Decimal("280000")) < Decimal("5")


def test_wallet_sample() -> None:
    drafts, issues = WalletJsonConnector().parse(
        "wallet_transfers.json", _read("wallet_transfers.json")
    )
    assert issues == []
    assert [row.kind for row in drafts] == ["TRANSFER_IN", "TRANSFER_IN"]
    assert drafts[0].qty == Decimal("0.9985")


def test_bad_row_is_issue_not_crash() -> None:
    text = "Date,Market,Side,Price (INR),Volume,Total (INR),Fee,Fee Currency\n2024-06-01 00:00:00,BTC/INR,Hold,1,-2,1,1,INR\n"
    _drafts, issues = WazirxConnector().parse("bad.csv", text)
    assert issues[0].reason == "unknown side"


def test_registry_detects_known_and_rejects_unknown() -> None:
    wazirx = _read("wazirx_trades.csv")
    binance = _read("binance_trades.csv")
    wallet = _read("wallet_transfers.json")
    unknown = _read("unknown_exchange.csv")
    assert detect_connector("a.csv", wazirx).name == "wazirx"
    assert detect_connector("b.csv", binance).name == "binance"
    assert detect_connector("c.json", wallet).name == "wallet"
    assert detect_connector("d.csv", unknown) is None
    assert "Trade Time" in extract_headers("d.csv", unknown)


def test_matcher_hash_heuristic_and_window() -> None:
    settings = get_settings()
    now = datetime(2024, 6, 19, 4, 0, tzinfo=UTC)

    def draft(**kwargs):  # type: ignore[no-untyped-def]
        base = dict(
            source="binance",
            source_row=1,
            ts_utc=now,
            kind="TRANSFER_OUT",
            asset="ETH",
            side=None,
            qty=Decimal("1"),
            price_inr=None,
            tx_hash=None,
        )
        base.update(kwargs)
        from app.connectors.base import CanonicalTxDraft

        return CanonicalTxDraft(**base)

    out_tx = draft(tx_hash="0xABC", source_row=1)
    in_tx = draft(
        source="wallet", kind="TRANSFER_IN", qty=Decimal("0.9985"), tx_hash="0xabc", source_row=2
    )
    matches = match_transfers([out_tx, in_tx], settings)
    assert len(matches) == 1 and matches[0].match_kind == "hash"
    assert matches[0].fee_qty == Decimal("0.0015")

    late = draft(
        source="wallet",
        kind="TRANSFER_IN",
        qty=Decimal("0.999"),
        tx_hash=None,
        ts_utc=now + timedelta(hours=7),
        source_row=3,
    )
    early = draft(tx_hash=None, qty=Decimal("1"), source_row=4)
    assert match_transfers([early, late], settings) == []

    near = draft(
        source="wallet",
        kind="TRANSFER_IN",
        qty=Decimal("0.997"),
        tx_hash=None,
        ts_utc=now + timedelta(hours=1),
        source_row=5,
    )
    heuristic = match_transfers([early, near], settings)
    assert len(heuristic) == 1 and heuristic[0].match_kind == "heuristic"

    other = draft(
        source="wallet",
        kind="TRANSFER_IN",
        qty=Decimal("0.998"),
        tx_hash=None,
        ts_utc=now + timedelta(minutes=5),
        source_row=6,
    )
    paired = match_transfers([early, near, other], settings)
    assert len(paired) == 1


def _tx(**kwargs) -> CanonicalTx:  # type: ignore[no-untyped-def]
    ts = kwargs.pop("ts_utc", datetime(2024, 6, 10, tzinfo=UTC))
    data = dict(
        source="wazirx",
        source_row=1,
        import_id="imp",
        ts_utc=ts,
        kind="TRADE",
        asset="BTC",
        side="BUY",
        qty=Decimal("1"),
        price_inr=Decimal("5600000"),
        fee_qty=Decimal("1"),
        raw={},
    )
    data.update(kwargs)
    data["stable_key"] = stable_key(
        data["source"],
        data["source_row"],
        data["ts_utc"],
        data["kind"],
        data["asset"],
        data["side"],
        data["qty"],
        data["price_inr"],
        data.get("tx_hash"),
    )
    return CanonicalTx(**data)


def test_each_rule_and_sample_counts(client) -> None:  # type: ignore[no-untyped-def]
    from collections import Counter

    loaded = client.post("/api/v1/demo/load")
    assert loaded.status_code == 200
    payload = client.get("/api/v1/exceptions", params={"page_size": 100}).json()
    counts = Counter(item["type"] for item in payload["items"])
    assert counts == {
        "UNMATCHED_WITHDRAWAL": 1,
        "UNMATCHED_DEPOSIT": 1,
        "DUPLICATE_TRADE": 1,
        "NEGATIVE_BALANCE": 1,
        "PRICE_DEVIATION": 1,
        "MISSING_FEE": 1,
    }
    sell = _tx(
        id="s", side="SELL", asset="SOL", qty=Decimal("2"), price_inr=Decimal("12500"), source_row=2
    )
    drafts = build_exceptions([sell], [], {"s": Decimal("-0.8")}, get_settings())
    assert any(item.type == "NEGATIVE_BALANCE" for item in drafts)
    huge = _tx(
        id="h",
        kind="TRANSFER_OUT",
        side=None,
        asset="BTC",
        qty=Decimal("1"),
        price_inr=None,
        source="binance",
        source_row=3,
    )
    huge_drafts = build_exceptions([huge], [], {}, get_settings())
    assert any(item.type == "LARGE_TRANSFER_UNEXPLAINED" for item in huge_drafts)
    assert any(item.type == "UNMATCHED_WITHDRAWAL" for item in huge_drafts)


def test_fifo_to_the_paisa() -> None:
    buy_a = _tx(
        id="a",
        source_row=1,
        qty=Decimal("1"),
        price_inr=Decimal("100.00"),
        ts_utc=datetime(2024, 6, 1, tzinfo=UTC),
    )
    buy_b = _tx(
        id="b",
        source_row=2,
        qty=Decimal("1"),
        price_inr=Decimal("200.00"),
        ts_utc=datetime(2024, 6, 2, tzinfo=UTC),
    )
    sell = _tx(
        id="c",
        source_row=3,
        side="SELL",
        qty=Decimal("1.5"),
        price_inr=Decimal("400.00"),
        ts_utc=datetime(2024, 6, 3, tzinfo=UTC),
    )
    report = compute_fifo([buy_a, buy_b, sell], [], Settings())
    sale = report["BTC"].sales[0]
    assert sale.cost == Decimal("200.00")
    assert sale.proceeds == Decimal("600.00")
    assert sale.gain == Decimal("400.00")
    assert report["BTC"].estimated_tax == Decimal("120.00")
    assert report["BTC"].tds == Decimal("6.00")
    assert len(sale.lots) == 2


def test_fallback_price_and_online_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    assert fallback_price("BTC", datetime(2024, 6, 20).date()) == Decimal("5600000.00")
    _memory.clear()
    monkeypatch.setenv("PRICES_ONLINE", "true")
    get_settings.cache_clear()

    async def boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr("app.reconcile.prices._coingecko", boom)
    price = get_price_inr_sync("ETH", datetime(2024, 6, 2, tzinfo=UTC))
    assert price == Decimal("280000.00")
    monkeypatch.setenv("PRICES_ONLINE", "false")
    get_settings.cache_clear()
