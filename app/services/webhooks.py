"""Outbound signed webhooks and SSRF checks."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import socket
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlmodel import Session, select

from app.errors import AppError
from app.logging import get_logger
from app.models import ExceptionRecord, WebhookConfig, WebhookDelivery, utcnow

logger = get_logger("webhooks")


def assert_public_webhook(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AppError(400, "WEBHOOK_BLOCKED", "Webhook URL must be an absolute http(s) URL.")
    host = parsed.hostname
    try:
        literal = ipaddress.ip_address(host)
        addresses = [literal]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or 80)
        except socket.gaierror as exc:
            raise AppError(400, "WEBHOOK_BLOCKED", "Webhook host could not be resolved.") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    for ip in addresses:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise AppError(400, "WEBHOOK_BLOCKED", "Webhook URL resolves to a non-public address.")


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, header: str) -> bool:
    expected = sign_body(secret, body)
    return hmac.compare_digest(expected, header or "")


def dispatch_new_high(session: Session, exceptions: list[ExceptionRecord]) -> None:
    config = session.get(WebhookConfig, _config_id(session))
    if config is None or not config.enabled or not config.url:
        return
    for exc in exceptions:
        if exc.severity != "high":
            continue
        payload = {
            "event": "exception.created",
            "exception": {
                "id": exc.id,
                "type": exc.type,
                "severity": exc.severity,
                "asset": exc.asset,
                "explanation": exc.explanation,
            },
        }
        deliver_sync(session, config, payload, exc.id)


def deliver_sync(
    session: Session, config: WebhookConfig, payload: dict[str, Any], exception_id: str | None
) -> WebhookDelivery:
    import json

    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = sign_body(config.secret or "orbit-demo", body)
    delivery = WebhookDelivery(
        exception_id=exception_id,
        url=config.url,
        payload=payload,
        signature=signature,
        status="pending",
    )
    session.add(delivery)
    session.commit()
    delay = 0.2
    last_error = ""
    try:
        assert_public_webhook(config.url)
    except AppError as exc:
        delivery.status = "failed"
        delivery.last_error = exc.message
        delivery.attempts = 1
        session.add(delivery)
        session.commit()
        return delivery
    with httpx.Client(timeout=5) as client:
        for attempt in range(1, 4):
            delivery.attempts = attempt
            try:
                response = client.post(
                    config.url,
                    content=body,
                    headers={"Content-Type": "application/json", "X-Orbit-Signature": signature},
                )
                if response.status_code >= 500 or response.status_code == 429:
                    last_error = f"HTTP {response.status_code}"
                else:
                    response.raise_for_status()
                    delivery.status = "delivered"
                    delivery.last_error = None
                    session.add(delivery)
                    session.commit()
                    return delivery
            except httpx.HTTPError as exc:
                last_error = str(exc)
            logger.info("webhook_retry", attempt=attempt, error=last_error)
            time.sleep(delay)
            delay *= 2
    delivery.status = "failed"
    delivery.last_error = last_error
    delivery.created_at = utcnow()
    session.add(delivery)
    session.commit()
    return delivery


async def deliver_async(
    session: Session, config: WebhookConfig, payload: dict[str, Any]
) -> WebhookDelivery:
    import asyncio
    import json

    body = json.dumps(payload, separators=(",", ":")).encode()
    signature = sign_body(config.secret or "orbit-demo", body)
    assert_public_webhook(config.url)
    delivery = WebhookDelivery(
        url=config.url, payload=payload, signature=signature, status="pending"
    )
    session.add(delivery)
    session.commit()
    delay = 0.2
    last_error = ""
    async with httpx.AsyncClient(timeout=5) as client:
        for attempt in range(1, 4):
            delivery.attempts = attempt
            try:
                response = await client.post(
                    config.url,
                    content=body,
                    headers={"Content-Type": "application/json", "X-Orbit-Signature": signature},
                )
                if response.status_code >= 500 or response.status_code == 429:
                    last_error = f"HTTP {response.status_code}"
                else:
                    response.raise_for_status()
                    delivery.status = "delivered"
                    session.add(delivery)
                    session.commit()
                    return delivery
            except httpx.HTTPError as exc:
                last_error = str(exc)
            await asyncio.sleep(delay)
            delay *= 2
    delivery.status = "failed"
    delivery.last_error = last_error
    session.add(delivery)
    session.commit()
    return delivery


def get_or_create_config(session: Session) -> WebhookConfig:
    from app.config import get_settings

    row = session.exec(select(WebhookConfig)).first()
    if row is None:
        settings = get_settings()
        row = WebhookConfig(
            url=settings.webhook_url,
            secret=settings.webhook_secret or "orbit-demo",
            enabled=bool(settings.webhook_url),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _config_id(session: Session) -> str:
    return get_or_create_config(session).id
