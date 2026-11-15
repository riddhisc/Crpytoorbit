"""Inbound transactions and outbound webhook settings."""

import hashlib
import json
from datetime import UTC
from decimal import Decimal

from fastapi import APIRouter, Header, Request
from sqlmodel import Session

from app.connectors.base import CanonicalTxDraft, ImportIssueDraft
from app.deps import Actor, DbSession
from app.errors import AppError
from app.limiter import limiter
from app.models import ImportBatch, Job
from app.parsing import canonical_asset, parse_datetime
from app.reconcile.service import reconcile
from app.schemas import InboundPayload, JobCreated, WebhookSettings, WebhookTestResult
from app.services.ingest import _persist_rows
from app.services.jobs import start_job
from app.services.webhooks import assert_public_webhook, deliver_async, get_or_create_config

router = APIRouter(prefix="/api/v1", tags=["webhooks"])


@router.post(
    "/webhooks/transactions",
    status_code=202,
    response_model=JobCreated,
    summary="Ingest JSON transactions",
)
@limiter.limit("30/minute")
async def inbound(
    request: Request,
    body: InboundPayload,
    session: DbSession,
    _actor: Actor,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobCreated:
    raw = await request.body()
    digest = hashlib.sha256(raw).hexdigest()
    job, replayed = start_job(session, "webhook-in", [digest], idempotency_key)
    if replayed:
        return JobCreated(job_id=job.id)
    _persist_inbound(session, job, body, digest)
    return JobCreated(job_id=job.id)


def _persist_inbound(session: Session, job: Job, body: InboundPayload, digest: str) -> None:
    drafts: list[CanonicalTxDraft] = []
    issues: list[ImportIssueDraft] = []
    for index, tx in enumerate(body.transactions, start=1):
        raw_text = json.dumps(tx.model_dump(mode="json"))
        try:
            ts = parse_datetime(tx.timestamp, assume_tz=UTC)
            asset = canonical_asset(tx.asset)
            if tx.kind not in {"TRADE", "TRANSFER_IN", "TRANSFER_OUT"}:
                raise ValueError("unknown side")
            if tx.quantity <= 0:
                raise ValueError("negative quantity")
            side = (tx.side or "").upper() or None
            if tx.kind == "TRADE" and side not in {"BUY", "SELL"}:
                raise ValueError("unknown side")
        except ValueError as exc:
            reason = (
                str(exc)
                if str(exc)
                in {
                    "unknown side",
                    "negative quantity",
                    "unknown ticker",
                    "unparseable date",
                    "non-numeric quantity",
                }
                else "unknown side"
            )
            issues.append(ImportIssueDraft(body.source, index, "warning", reason, raw_text))
            continue
        drafts.append(
            CanonicalTxDraft(
                source=(body.source or "webhook")[:40],
                source_row=index,
                ts_utc=ts,
                kind=tx.kind,
                asset=asset,
                side=side if tx.kind == "TRADE" else None,
                qty=Decimal(tx.quantity),
                price_inr=Decimal(tx.price_inr) if tx.price_inr is not None else None,
                fee_qty=Decimal(tx.fee_qty or 0),
                fee_asset=tx.fee_asset,
                tx_hash=tx.tx_hash,
                counterparty=tx.counterparty,
                raw=json.loads(tx.model_dump_json()),
            )
        )
    batch = ImportBatch(
        job_id=job.id,
        filename="webhook.json",
        content_sha256=digest,
        connector="webhook",
        confidence="high",
        status="running",
    )
    session.add(batch)
    session.commit()
    imported, skipped = _persist_rows(session, batch, drafts, issues)
    batch.rows_imported = imported
    batch.rows_skipped = skipped
    batch.status = "done"
    session.add(batch)
    session.commit()
    summary = reconcile(session)
    job.status = "done"
    job.progress = 100
    job.result = {"imported": imported, "reconcile": summary}
    session.add(job)
    session.commit()


@router.get(
    "/settings/webhook", response_model=WebhookSettings, summary="Read the outbound webhook"
)
def get_webhook(session: DbSession) -> WebhookSettings:
    config = get_or_create_config(session)
    return WebhookSettings(url=config.url, secret=config.secret, enabled=config.enabled)


@router.put(
    "/settings/webhook", response_model=WebhookSettings, summary="Update the outbound webhook"
)
def put_webhook(body: WebhookSettings, session: DbSession, _actor: Actor) -> WebhookSettings:
    if body.enabled and body.url:
        assert_public_webhook(body.url)
    config = get_or_create_config(session)
    config.url = body.url
    if body.secret:
        config.secret = body.secret
    config.enabled = body.enabled
    session.add(config)
    session.commit()
    return WebhookSettings(url=config.url, secret=config.secret, enabled=config.enabled)


@router.post(
    "/settings/webhook/test", response_model=WebhookTestResult, summary="Send a signed test event"
)
@limiter.limit("10/minute")
async def test_webhook(request: Request, session: DbSession, _actor: Actor) -> WebhookTestResult:
    config = get_or_create_config(session)
    if not config.url:
        raise AppError(422, "VALIDATION_ERROR", "Set a webhook URL before sending a test.")
    delivery = await deliver_async(
        session,
        config,
        {"event": "webhook.test", "message": "Crypto Orbit test event"},
    )
    return WebhookTestResult(
        status=delivery.status, attempts=delivery.attempts, last_error=delivery.last_error
    )
