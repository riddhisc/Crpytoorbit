"""Pick a connector from the header signature, or report that mapping is required."""

import json

from app.connectors.base import Connector
from app.connectors.binance import BinanceConnector
from app.connectors.csvutil import read_csv_rows
from app.connectors.generic_mapped import GenericMappedConnector
from app.connectors.wallet_json import WalletJsonConnector
from app.connectors.wazirx import WazirxConnector
from app.models import ConnectorProfile


def header_signature(headers: list[str]) -> str:
    return "|".join(sorted(header.strip().lower() for header in headers if header.strip()))


def extract_headers(filename: str, text: str) -> list[str]:
    stripped = text.lstrip("\ufeff").lstrip()
    if stripped.startswith("{") or filename.lower().endswith(".json"):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict) and "transfers" in payload:
            return ["address", "transfers"]
        return list(payload.keys()) if isinstance(payload, dict) else []
    rows = read_csv_rows(text)
    for row in rows:
        labels = [cell.strip() for cell in row if cell.strip()]
        if len(labels) >= 3:
            return [cell.strip() for cell in row]
    return []


def builtin_connectors() -> list[Connector]:
    return [WazirxConnector(), BinanceConnector(), WalletJsonConnector()]


def detect_connector(
    filename: str,
    text: str,
    profiles: list[ConnectorProfile] | None = None,
) -> Connector | None:
    headers = extract_headers(filename, text)
    for connector in builtin_connectors():
        if connector.detect(filename, text, headers):
            return connector
    signature = header_signature(headers)
    for profile in profiles or []:
        if profile.header_signature == signature:
            mapping = profile.mapping if isinstance(profile.mapping, dict) else {}
            return GenericMappedConnector(mapping, source_name=profile.name)
    return None
