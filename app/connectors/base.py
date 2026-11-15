"""Connector contract: detect a file and parse it into canonical rows plus issues."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class ImportIssueDraft:
    source: str
    row_number: int
    severity: str
    reason: str
    raw_text: str


@dataclass
class CanonicalTxDraft:
    source: str
    source_row: int
    ts_utc: datetime
    kind: str
    asset: str
    side: str | None
    qty: Decimal
    price_inr: Decimal | None
    fee_qty: Decimal = Decimal("0")
    fee_asset: str | None = None
    tx_hash: str | None = None
    counterparty: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    fee_missing: bool = False


class Connector(ABC):
    name: str
    confidence: str = "high"

    @abstractmethod
    def detect(self, filename: str, text: str, headers: list[str]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(
        self, filename: str, text: str
    ) -> tuple[list[CanonicalTxDraft], list[ImportIssueDraft]]:
        raise NotImplementedError
