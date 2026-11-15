"""On-chain wallet JSON adapter. Optionally fetches Etherscan when a key is configured."""

import json
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.connectors.base import CanonicalTxDraft, Connector, ImportIssueDraft
from app.parsing import canonical_asset, parse_datetime, parse_decimal


class WalletJsonConnector(Connector):
    name = "wallet"

    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        stripped = text.lstrip("\ufeff").lstrip()
        if not stripped.startswith("{"):
            return False
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and isinstance(payload.get("transfers"), list)

    def parse(
        self, filename: str, text: str
    ) -> tuple[list[CanonicalTxDraft], list[ImportIssueDraft]]:
        try:
            payload = json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError:
            return [], [ImportIssueDraft("wallet", 1, "error", "unparseable date", text[:500])]
        transfers = payload.get("transfers") if isinstance(payload, dict) else None
        if not isinstance(transfers, list):
            return [], [ImportIssueDraft("wallet", 1, "error", "unparseable date", text[:500])]
        address = str(payload.get("address") or "")
        drafts: list[CanonicalTxDraft] = []
        issues: list[ImportIssueDraft] = []
        for index, item in enumerate(transfers, start=1):
            if not isinstance(item, dict):
                issues.append(
                    ImportIssueDraft(
                        "wallet", index, "warning", "unparseable date", str(item)[:500]
                    )
                )
                continue
            try:
                drafts.append(_parse_transfer(index, item, address))
            except ValueError as exc:
                issues.append(
                    ImportIssueDraft(
                        "wallet", index, "warning", _reason(exc), json.dumps(item)[:500]
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


def _parse_transfer(row_number: int, item: dict[str, Any], address: str) -> CanonicalTxDraft:
    try:
        ts = parse_datetime(item.get("timestamp"))
    except ValueError as exc:
        raise ValueError("unparseable date") from exc
    direction = str(item.get("direction") or "").strip().lower()
    if direction == "in":
        kind = "TRANSFER_IN"
        counterparty = str(item.get("from") or "") or None
    elif direction == "out":
        kind = "TRANSFER_OUT"
        counterparty = str(item.get("to") or "") or None
    else:
        raise ValueError("unknown side")
    try:
        asset = canonical_asset(str(item.get("asset") or ""))
    except ValueError as exc:
        raise ValueError("unknown ticker") from exc
    try:
        qty = parse_decimal(item.get("value"))
    except ValueError as exc:
        raise ValueError("non-numeric quantity") from exc
    if qty < 0:
        raise ValueError("negative quantity")
    if qty == 0:
        raise ValueError("non-numeric quantity")
    tx_hash = str(item.get("hash") or "").strip() or None
    return CanonicalTxDraft(
        source="wallet",
        source_row=row_number,
        ts_utc=ts,
        kind=kind,
        asset=asset,
        side=None,
        qty=qty,
        price_inr=None,
        fee_qty=Decimal("0"),
        tx_hash=tx_hash,
        counterparty=counterparty,
        raw={"address": address, **item},
    )


async def fetch_etherscan_wallet(
    address: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Live fetch is optional. Demo never needs a key."""
    cfg = settings or get_settings()
    if not cfg.etherscan_api_key:
        return None
    params = {
        "module": "account",
        "action": "tokentx",
        "address": address,
        "sort": "asc",
        "apikey": cfg.etherscan_api_key,
    }
    delay = 0.4
    async with httpx.AsyncClient(timeout=8) as client:
        for attempt in range(3):
            response = await client.get(cfg.etherscan_base, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    return None
                import asyncio

                await asyncio.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            body = response.json()
            transfers = []
            for row in body.get("result") or []:
                if not isinstance(row, dict):
                    continue
                direction = "in" if str(row.get("to", "")).lower() == address.lower() else "out"
                decimals = int(row.get("tokenDecimal") or 18)
                value = Decimal(row.get("value") or "0") / (Decimal(10) ** decimals)
                transfers.append(
                    {
                        "hash": row.get("hash"),
                        "timestamp": int(row.get("timeStamp") or 0),
                        "asset": row.get("tokenSymbol"),
                        "value": format(value, "f"),
                        "direction": direction,
                        "from": row.get("from"),
                        "to": row.get("to"),
                    }
                )
            return {"address": address, "transfers": transfers}
    return None
