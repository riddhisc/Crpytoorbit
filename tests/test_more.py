"""Extra branches: CLI, bad rows, webhook delivery, and resolution validation."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from app.cli import cli
from app.config import Settings
from app.connectors.binance import BinanceConnector
from app.connectors.wallet_json import WalletJsonConnector, fetch_etherscan_wallet
from app.connectors.wazirx import WazirxConnector
from app.reconcile.fifo import compute_fifo
from app.reconcile.prices import get_price_inr
from app.services.webhooks import deliver_sync, get_or_create_config
from fastapi.testclient import TestClient
from typer.testing import CliRunner


def test_cli_import_reconcile_export() -> None:
    runner = CliRunner()
    imported = runner.invoke(cli, ["import", "sample-data/wallet_transfers.json"])
    assert imported.exit_code == 0
    assert "Open exceptions" in imported.stdout
    again = runner.invoke(cli, ["reconcile"])
    assert again.exit_code == 0
    exported = runner.invoke(cli, ["export", "--format", "exceptions"])
    assert exported.exit_code == 0
    assert "type" in exported.stdout


def test_adapter_edge_rows() -> None:
    header = "Date(UTC),Pair,Side,Price,Executed,Amount,Fee,Fee Coin,TxHash\n"
    bad = (
        header
        + "nope,ETHUSDT,BUY,1,1ETH,1USDT,0.1,ETH,\n2024-06-01 00:00:00,ETHUSDT,MAYBE,1,1ETH,1,0.1,ETH,\n2024-06-01 00:00:00,ETHUSDT,DEPOSIT,,1ETH,,0,ETH,0x1\n"
    )
    drafts, issues = BinanceConnector().parse("b.csv", bad)
    assert any(issue.reason == "unparseable date" for issue in issues)
    assert any(issue.reason == "unknown side" for issue in issues)
    assert any(row.kind == "TRANSFER_IN" for row in drafts)
    broken = "Date,Market,Side,Price (INR),Volume,Total (INR),Fee,Fee Currency\n2024-06-01 00:00:00,NOTAPAIR,Buy,1,1,1,1,INR\n"
    _rows, wazirx_issues = WazirxConnector().parse("w.csv", broken)
    assert wazirx_issues[0].reason == "unknown ticker"
    wallet_bad, wallet_issues = WalletJsonConnector().parse("w.json", "{")
    assert wallet_issues
    assert wallet_bad == []


@pytest.mark.asyncio
async def test_price_and_etherscan_optional() -> None:
    price = await get_price_inr("SOL", datetime(2024, 6, 8, tzinfo=UTC))
    assert price == Decimal("12500.00")
    assert await fetch_etherscan_wallet("0xabc") is None


def test_resolution_validation_and_bulk(client: TestClient) -> None:
    client.post("/api/v1/demo/load")
    missing = client.patch(
        "/api/v1/exceptions/missing", json={"status": "resolved", "resolution_note": "x"}
    )
    assert missing.status_code == 404
    row = client.get("/api/v1/exceptions", params={"status": "open", "page_size": 1}).json()[
        "items"
    ][0]
    empty = client.patch(
        f"/api/v1/exceptions/{row['id']}", json={"status": "ignored", "resolution_note": "  "}
    )
    assert empty.status_code == 422
    bulk = client.post(
        "/api/v1/exceptions/bulk",
        json={"ids": [row["id"]], "status": "ignored", "resolution_note": "Not mine."},
    )
    assert bulk.status_code == 200
    assert bulk.json()[0]["status"] == "ignored"
    csv_body = client.get("/api/v1/export/exceptions.csv")
    assert "UNMATCHED" in csv_body.text or "type" in csv_body.text


def test_deliver_sync_records_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db import session_scope

    class Broken:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def __enter__(self) -> "Broken":
            return self

        def __exit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

        def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise httpx.ConnectError("down")

    monkeypatch.setattr("app.services.webhooks.httpx.Client", Broken)
    monkeypatch.setattr("app.services.webhooks.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "app.services.webhooks.socket.getaddrinfo",
        lambda *a, **k: [(None, None, None, None, ("1.1.1.1", 0))],
    )
    with session_scope() as session:
        config = get_or_create_config(session)
        config.url = "https://example.com/hook"
        config.secret = "orbit-demo"
        config.enabled = True
        session.add(config)
        session.commit()
        delivery = deliver_sync(session, config, {"event": "x"}, None)
        assert delivery.status == "failed"


def test_fees_as_cost_changes_lot() -> None:
    from app.models import CanonicalTx
    from app.parsing import stable_key

    ts = datetime(2024, 6, 1, tzinfo=UTC)
    tx = CanonicalTx(
        source="wazirx",
        source_row=1,
        import_id="i",
        ts_utc=ts,
        kind="TRADE",
        asset="BTC",
        side="BUY",
        qty=Decimal("1"),
        price_inr=Decimal("100"),
        fee_qty=Decimal("10"),
        fee_asset="INR",
        raw={},
        stable_key="x",
    )
    tx.stable_key = stable_key(
        "wazirx", 1, ts, "TRADE", "BTC", "BUY", Decimal("1"), Decimal("100"), None
    )
    sell = CanonicalTx(
        source="wazirx",
        source_row=2,
        import_id="i",
        ts_utc=datetime(2024, 6, 2, tzinfo=UTC),
        kind="TRADE",
        asset="BTC",
        side="SELL",
        qty=Decimal("1"),
        price_inr=Decimal("100"),
        fee_qty=Decimal("0"),
        raw={},
        stable_key="y",
    )
    settings = Settings(fees_as_cost=True)
    report = compute_fifo([tx, sell], [], settings)
    assert report["BTC"].sales[0].cost == Decimal("110.00")
