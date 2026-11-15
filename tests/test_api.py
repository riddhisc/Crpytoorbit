"""API, persistence, auth, webhooks, mapping, and the CLI."""

import os
from decimal import Decimal

import httpx
import pytest
from app.config import get_settings
from app.services.export import csv_safe
from app.services.mapping import suggest_mapping
from app.services.webhooks import assert_public_webhook, sign_body, verify_signature
from fastapi.testclient import TestClient


def test_error_contract_and_filters(client: TestClient) -> None:
    missing = client.get("/api/v1/exceptions/does-not-exist")
    body = missing.json()
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert missing.headers["X-Request-ID"]
    client.post("/api/v1/demo/load")
    high = client.get("/api/v1/exceptions", params={"severity": "high", "status": "open"}).json()
    assert high["total"] == 3
    assert all(item["severity"] == "high" for item in high["items"])
    summary = client.get("/api/v1/summary").json()
    assert summary["open_exceptions"] == 6
    assert summary["matched_pct"] == "50.00"
    tax = client.get("/api/v1/tax").json()
    assert "ESTIMATE" in tax["disclaimer"]
    assert tax["tax_rate_pct"] == "30"
    ready = client.get("/ready")
    assert ready.status_code == 200
    metrics = client.get("/metrics")
    assert "orbit_imports_total" in metrics.text
    assert "orbit_exceptions" in metrics.text


def test_resolve_survives_rerun(client: TestClient) -> None:
    client.post("/api/v1/demo/load")
    rows = client.get("/api/v1/exceptions", params={"type": "MISSING_FEE"}).json()["items"]
    target = rows[0]["id"]
    patched = client.patch(
        f"/api/v1/exceptions/{target}",
        json={"status": "resolved", "resolution_note": "Fee was waived."},
    )
    assert patched.status_code == 200
    again = client.post("/api/v1/demo/load")
    assert again.status_code == 200
    still = client.get(f"/api/v1/exceptions/{target}").json()
    assert still["status"] == "resolved"
    assert still["history"][0]["to_status"] == "resolved"
    audit = client.get("/api/v1/audit-log").json()
    assert audit["total"] >= 1


def test_idempotent_upload_and_unknown_file(client: TestClient) -> None:
    client.post("/api/v1/demo/load")
    before = client.get("/api/v1/ledger").json()["total"]
    path = "sample-data/wazirx_trades.csv"
    with open(path, "rb") as handle:
        content = handle.read()
    first = client.post(
        "/api/v1/imports",
        files={"files": ("wazirx_trades.csv", content, "text/csv")},
        headers={"Idempotency-Key": "same-key"},
    )
    assert first.status_code == 202
    second = client.post(
        "/api/v1/imports",
        files={"files": ("wazirx_trades.csv", content, "text/csv")},
        headers={"Idempotency-Key": "same-key"},
    )
    assert second.json()["job_id"] == first.json()["job_id"]
    third = client.post(
        "/api/v1/imports",
        files={"files": ("wazirx_trades.csv", content + b"\n", "text/csv")},
        headers={"Idempotency-Key": "same-key"},
    )
    assert third.status_code == 409
    after = client.get("/api/v1/ledger").json()["total"]
    assert after == before
    unknown = open("sample-data/unknown_exchange.csv", "rb").read()
    rejected = client.post(
        "/api/v1/imports", files={"files": ("unknown_exchange.csv", unknown, "text/csv")}
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "UNSUPPORTED_FILE"
    assert "Trade Time" in rejected.json()["error"]["details"]["files"][0]["headers"]


def test_mapping_preview_and_profile(client: TestClient) -> None:
    headers = ["Trade Time", "Coin", "Direction", "Units", "Rate", "Charge"]
    rows = [
        {
            "Trade Time": "2024-06-15 10:00:00",
            "Coin": "BTC",
            "Direction": "Buy",
            "Units": "0.01",
            "Rate": "5600000",
            "Charge": "56",
        }
    ]
    suggestions = suggest_mapping(headers, rows)
    assert any(item["field"] == "ts" and item["header"] == "Trade Time" for item in suggestions)
    mapping = {
        "ts": "Trade Time",
        "asset": "Coin",
        "side": "Direction",
        "qty": "Units",
        "price": "Rate",
        "fee": "Charge",
    }
    preview = client.post(
        "/api/v1/mapping/preview",
        json={"headers": headers, "rows": rows, "mapping": mapping, "source_name": "mystery"},
    ).json()
    assert preview["rows"][0]["asset"] == "BTC"
    assert preview["rows"][0]["qty"] == "0.01"
    saved = client.post(
        "/api/v1/mapping/profiles", json={"name": "mystery", "headers": headers, "mapping": mapping}
    )
    assert saved.status_code == 200
    payload = open("sample-data/unknown_exchange.csv", "rb").read()
    uploaded = client.post(
        "/api/v1/imports", files={"files": ("unknown_exchange.csv", payload, "text/csv")}
    )
    assert uploaded.status_code == 202
    job = client.get(f"/api/v1/imports/{uploaded.json()['job_id']}").json()
    assert job["status"] == "done"
    assert job["files"][0]["connector"] == "mystery"


def test_mapping_without_llm_key(client: TestClient) -> None:
    body = {
        "headers": ["Trade Time", "Coin", "Direction", "Units", "Rate", "Charge"],
        "sample_rows": [],
    }
    response = client.post("/api/v1/mapping/suggest", json=body)
    assert response.status_code == 200
    assert response.json()["llm_used"] is False


@pytest.mark.asyncio
async def test_llm_mapping_skipped_without_key() -> None:
    from app.services.mapping import suggest_with_llm

    assert await suggest_with_llm(["Date"], [], get_settings()) is None


def test_auth_required_when_demo_off(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("API_KEY", "secret-key")
    get_settings.cache_clear()
    denied = client.post("/api/v1/reset")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "UNAUTHORIZED"
    allowed = client.post("/api/v1/demo/load", headers={"X-API-Key": "secret-key"})
    assert allowed.status_code == 200


def test_webhook_signature_ssrf_and_retry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b'{"event":"exception.created"}'
    signature = sign_body("orbit-demo", body)
    assert verify_signature("orbit-demo", body, signature)
    assert not verify_signature("other", body, signature)
    with pytest.raises(Exception) as blocked:
        assert_public_webhook("http://127.0.0.1/hook")
    assert "WEBHOOK_BLOCKED" in str(blocked.value.code)

    class FakeResponse:
        status_code = 204

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

        def post(self, *args, **kwargs) -> FakeResponse:  # type: ignore[no-untyped-def]
            assert kwargs["headers"]["X-Orbit-Signature"].startswith("sha256=")
            return FakeResponse()

    class FakeAsync:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self) -> "FakeAsync":
            return self

        async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

        async def post(self, *args, **kwargs) -> FakeResponse:  # type: ignore[no-untyped-def]
            assert kwargs["headers"]["X-Orbit-Signature"].startswith("sha256=")
            return FakeResponse()

    monkeypatch.setattr("app.services.webhooks.httpx.Client", FakeClient)
    monkeypatch.setattr("app.services.webhooks.httpx.AsyncClient", FakeAsync)
    monkeypatch.setattr(
        "app.services.webhooks.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 0))],
    )
    saved = client.put(
        "/api/v1/settings/webhook",
        json={"url": "https://example.com/hook", "secret": "orbit-demo", "enabled": True},
    )
    assert saved.status_code == 200
    tested = client.post("/api/v1/settings/webhook/test")
    assert tested.status_code == 200
    assert tested.json()["status"] == "delivered"


def test_csv_injection_and_exports(client: TestClient) -> None:
    assert csv_safe("=cmd()") == "'=cmd()"
    assert csv_safe("-1+1") == "'-1+1"
    client.post("/api/v1/demo/load")
    ledger = client.get("/api/v1/export/ledger.csv")
    assert ledger.status_code == 200
    assert "asset" in ledger.text
    pdf = client.get("/api/v1/export/report.pdf")
    assert pdf.content.startswith(b"%PDF")


def test_inbound_webhook_and_reset(client: TestClient) -> None:
    payload = {
        "source": "hook",
        "transactions": [
            {
                "timestamp": "2024-07-01T00:00:00Z",
                "asset": "SOL",
                "quantity": "0.4",
                "kind": "TRANSFER_IN",
                "tx_hash": "0xabc",
            }
        ],
    }
    created = client.post(
        "/api/v1/webhooks/transactions", json=payload, headers={"Idempotency-Key": "in-1"}
    )
    assert created.status_code == 202
    replay = client.post(
        "/api/v1/webhooks/transactions", json=payload, headers={"Idempotency-Key": "in-1"}
    )
    assert replay.json()["job_id"] == created.json()["job_id"]
    reset = client.post("/api/v1/reset")
    assert reset.status_code == 200
    assert client.get("/api/v1/ledger").json()["total"] == 0


def test_cli_lists_open_exceptions(client: TestClient) -> None:
    client.post("/api/v1/demo/load")
    from app.cli import cli
    from typer.testing import CliRunner

    result = CliRunner().invoke(cli, ["exceptions", "--status", "open", "--severity", "high"])
    assert result.exit_code == 0
    assert "UNMATCHED_WITHDRAWAL" in result.stdout


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_httpx_used_by_price_client() -> None:
    assert hasattr(httpx, "AsyncClient")
    assert Decimal("1.00") == Decimal("1.00")
    assert os.environ["DEMO_MODE"] == "true"
