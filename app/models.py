"""SQLModel tables. Money and quantities are NUMERIC, never float."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON, Column, Index, Numeric
from sqlmodel import Field, SQLModel

MONEY = Numeric(38, 18)


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class ImportBatch(SQLModel, table=True):
    __tablename__ = "import_batch"
    id: str = Field(default_factory=new_id, primary_key=True)
    job_id: str = Field(index=True)
    filename: str
    content_sha256: str = Field(index=True)
    connector: str | None = None
    confidence: str | None = None
    status: str = "queued"
    rows_imported: int = 0
    rows_skipped: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class CanonicalTx(SQLModel, table=True):
    __tablename__ = "canonical_tx"
    __table_args__ = (
        Index("ix_canonical_tx_asset_ts", "asset", "ts_utc"),
        Index("ix_canonical_tx_hash", "tx_hash"),
    )
    id: str = Field(default_factory=new_id, primary_key=True)
    source: str = Field(index=True)
    source_row: int
    import_id: str = Field(foreign_key="import_batch.id", index=True)
    ts_utc: datetime
    kind: str
    asset: str
    side: str | None = None
    qty: Decimal = Field(sa_column=Column(MONEY, nullable=False))
    price_inr: Decimal | None = Field(default=None, sa_column=Column(MONEY, nullable=True))
    fee_qty: Decimal = Field(default=Decimal("0"), sa_column=Column(MONEY, nullable=False))
    fee_asset: str | None = None
    tx_hash: str | None = None
    counterparty: str | None = None
    raw: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    excluded: bool = False
    stable_key: str = Field(index=True)


class ImportIssue(SQLModel, table=True):
    __tablename__ = "import_issue"
    id: str = Field(default_factory=new_id, primary_key=True)
    import_id: str = Field(foreign_key="import_batch.id", index=True)
    source: str
    row_number: int
    severity: str
    reason: str
    raw_text: str


class ExceptionRecord(SQLModel, table=True):
    __tablename__ = "exception_record"
    __table_args__ = (Index("ix_exception_fingerprint", "fingerprint", unique=True),)
    id: str = Field(default_factory=new_id, primary_key=True)
    type: str = Field(index=True)
    severity: str = Field(index=True)
    asset: str | None = None
    source: str | None = None
    ts_utc: datetime | None = None
    estimated_value_inr: Decimal | None = Field(
        default=None, sa_column=Column(MONEY, nullable=True)
    )
    explanation: str
    suggested_fix: str
    status: str = Field(default="open", index=True)
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    fingerprint: str
    details: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ExceptionRelatedTx(SQLModel, table=True):
    __tablename__ = "exception_related_tx"
    id: str = Field(default_factory=new_id, primary_key=True)
    exception_id: str = Field(foreign_key="exception_record.id", index=True)
    tx_id: str = Field(foreign_key="canonical_tx.id", index=True)


class MatchedTransfer(SQLModel, table=True):
    __tablename__ = "matched_transfer"
    id: str = Field(default_factory=new_id, primary_key=True)
    out_tx_id: str = Field(foreign_key="canonical_tx.id", index=True)
    in_tx_id: str = Field(foreign_key="canonical_tx.id", index=True)
    asset: str
    sent_qty: Decimal = Field(sa_column=Column(MONEY, nullable=False))
    received_qty: Decimal = Field(sa_column=Column(MONEY, nullable=False))
    fee_qty: Decimal = Field(sa_column=Column(MONEY, nullable=False))
    match_kind: str


class PriceCache(SQLModel, table=True):
    __tablename__ = "price_cache"
    id: str = Field(default_factory=new_id, primary_key=True)
    asset: str = Field(index=True)
    day: str = Field(index=True)
    price_inr: Decimal = Field(sa_column=Column(MONEY, nullable=False))
    source: str


class ResolutionEvent(SQLModel, table=True):
    __tablename__ = "resolution_event"
    id: str = Field(default_factory=new_id, primary_key=True)
    exception_id: str = Field(foreign_key="exception_record.id", index=True)
    from_status: str | None = None
    to_status: str
    note: str | None = None
    actor: str = "demo-user"
    created_at: datetime = Field(default_factory=utcnow)


class ConnectorProfile(SQLModel, table=True):
    __tablename__ = "connector_profile"
    id: str = Field(default_factory=new_id, primary_key=True)
    name: str
    header_signature: str = Field(index=True, unique=True)
    mapping: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow)


class WebhookConfig(SQLModel, table=True):
    __tablename__ = "webhook_config"
    id: str = Field(default_factory=new_id, primary_key=True)
    url: str = ""
    secret: str = ""
    enabled: bool = False
    updated_at: datetime = Field(default_factory=utcnow)


class WebhookDelivery(SQLModel, table=True):
    __tablename__ = "webhook_delivery"
    id: str = Field(default_factory=new_id, primary_key=True)
    exception_id: str | None = Field(default=None, index=True)
    url: str
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    signature: str = ""
    status: str = "pending"
    attempts: int = 0
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Job(SQLModel, table=True):
    __tablename__ = "job"
    id: str = Field(default_factory=new_id, primary_key=True)
    kind: str
    status: str = "queued"
    progress: int = 0
    message: str = ""
    result: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error: str | None = None
    idempotency_key: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class IdempotencyKey(SQLModel, table=True):
    __tablename__ = "idempotency_key"
    key: str = Field(primary_key=True)
    request_hash: str
    job_id: str
    created_at: datetime = Field(default_factory=utcnow)
