"""Pydantic response models. Decimal values are serialized as strings."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

Money = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
]
T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorBody(APIModel):
    code: str = Field(examples=["UNSUPPORTED_FILE"])
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(APIModel):
    error: ErrorBody


class JobCreated(APIModel):
    job_id: str


class ImportFileStatus(APIModel):
    import_id: str | None = None
    filename: str
    connector: str | None = None
    confidence: str | None = None
    rows_imported: int = 0
    rows_skipped: int = 0
    duplicate: bool = False


class JobStatus(APIModel):
    job_id: str
    status: str
    progress: int
    message: str
    files: list[ImportFileStatus] = Field(default_factory=list)
    error: str | None = None


class LedgerRow(APIModel):
    id: str
    source: str
    source_row: int
    ts_utc: datetime
    kind: str
    asset: str
    side: str | None
    qty: Money
    price_inr: Money | None
    fee_qty: Money
    fee_asset: str | None
    tx_hash: str | None
    counterparty: str | None
    excluded: bool
    running_balance: Money | None = None
    matched_tx_id: str | None = None
    match_note: str | None = None
    raw: dict[str, Any]


class ExceptionItem(APIModel):
    id: str
    type: str
    severity: str
    asset: str | None
    source: str | None
    ts_utc: datetime | None
    estimated_value_inr: Money | None
    explanation: str
    suggested_fix: str
    status: str
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    fingerprint: str


class EvidenceRow(APIModel):
    id: str
    source: str
    ts_utc: datetime
    kind: str
    asset: str
    side: str | None
    qty: Money
    price_inr: Money | None
    tx_hash: str | None
    raw: dict[str, Any]
    role: str


class HistoryEvent(APIModel):
    id: str
    from_status: str | None
    to_status: str
    note: str | None
    actor: str
    created_at: datetime


class ExceptionDetail(ExceptionItem):
    evidence: list[EvidenceRow]
    history: list[HistoryEvent]
    details: dict[str, Any]


class StatusUpdate(APIModel):
    status: str = Field(examples=["resolved"])
    resolution_note: str = ""


class BulkUpdate(APIModel):
    ids: list[str]
    status: str
    resolution_note: str = ""


class Holding(APIModel):
    asset: str
    qty: Money
    value_inr: Money
    open_exceptions: int


class Summary(APIModel):
    total_tx: int
    matched_pct: Money
    open_exceptions: int
    value_at_risk_inr: Money
    by_type: dict[str, int]
    by_severity: dict[str, int]
    holdings: list[Holding]
    demo_mode: bool


class LotUseOut(APIModel):
    acquired_ts: str
    qty: Money
    unit_cost: Money
    cost: Money


class SaleOut(APIModel):
    tx_id: str
    ts_utc: str
    qty: Money
    proceeds: Money
    cost: Money
    gain: Money
    lots: list[LotUseOut]


class TaxAsset(APIModel):
    asset: str
    realized_gain_inr: Money
    taxable_gain_inr: Money
    estimated_tax_inr: Money
    tds_inr: Money
    sales: list[SaleOut]


class TaxResponse(APIModel):
    assets: list[TaxAsset]
    totals: TaxAsset
    tax_rate_pct: Money
    tds_rate_pct: Money
    fees_as_cost: bool
    disclaimer: str


class ImportIssueOut(APIModel):
    id: str
    import_id: str
    source: str
    filename: str | None = None
    row_number: int
    severity: str
    reason: str
    raw_text: str


class AuditEvent(APIModel):
    id: str
    exception_id: str
    exception_type: str | None = None
    from_status: str | None
    to_status: str
    note: str | None
    actor: str
    created_at: datetime


class MappingSuggestion(APIModel):
    field: str
    header: str
    confidence: float
    source: str


class MappingSuggestRequest(APIModel):
    headers: list[str]
    sample_rows: list[dict[str, str]]


class MappingSuggestResponse(APIModel):
    suggestions: list[MappingSuggestion]
    llm_used: bool


class MappingPreviewRequest(APIModel):
    headers: list[str]
    rows: list[dict[str, str]]
    mapping: dict[str, str]
    source_name: str = "custom"


class PreviewRow(APIModel):
    source_row: int
    ts_utc: datetime
    kind: str
    asset: str
    side: str | None
    qty: Money
    price_inr: Money | None


class MappingPreviewResponse(APIModel):
    rows: list[PreviewRow]
    issues: list[dict[str, Any]]


class MappingProfileRequest(APIModel):
    name: str
    headers: list[str]
    mapping: dict[str, str]


class MappingProfileOut(APIModel):
    id: str
    name: str
    header_signature: str
    mapping: dict[str, str]


class WebhookSettings(APIModel):
    url: str = ""
    secret: str = ""
    enabled: bool = False


class WebhookTestResult(APIModel):
    status: str
    attempts: int
    last_error: str | None = None


class InboundTransaction(APIModel):
    timestamp: datetime | int | str
    asset: str
    quantity: Decimal
    kind: str
    side: str | None = None
    price_inr: Decimal | None = None
    fee_qty: Decimal = Decimal("0")
    fee_asset: str | None = None
    tx_hash: str | None = None
    counterparty: str | None = None


class InboundPayload(APIModel):
    source: str = "webhook"
    transactions: list[InboundTransaction]


class HealthOut(APIModel):
    status: str


class ReadyOut(APIModel):
    status: str
    revision: str


class DemoResult(APIModel):
    job_id: str
    files: list[ImportFileStatus]
    open_exceptions: int
    matches: int
