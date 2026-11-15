"""INR prices: local cache, then CoinGecko (optional), then the bundled fallback file.

A request never fails because prices are missing. Callers skip PRICE_DEVIATION and log it.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlmodel import Session, select

from app.config import Settings, get_settings
from app.logging import get_logger
from app.models import PriceCache

logger = get_logger("prices")
FALLBACK_PATH = Path(__file__).resolve().parents[2] / "sample-data" / "prices_fallback.json"
_fallback: dict[str, dict[str, str]] | None = None
_memory: dict[tuple[str, str], Decimal] = {}
_circuit_failures = 0
_circuit_open_until = 0.0


def _load_fallback() -> dict[str, dict[str, str]]:
    global _fallback
    if _fallback is None:
        _fallback = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    return _fallback


def fallback_price(asset: str, day: date) -> Decimal | None:
    table = _load_fallback().get(asset.upper())
    if not table:
        return None
    raw = table.get(day.isoformat())
    if raw is None:
        return None
    return Decimal(str(raw))


def usdt_inr(day: date) -> Decimal | None:
    """Synchronous lookup used while parsing. Memory cache, then bundled fallback."""
    key = ("USDT", day.isoformat())
    if key in _memory:
        return _memory[key]
    price = fallback_price("USDT", day)
    if price is not None:
        _memory[key] = price
    return price


def lookup_cached(asset: str, day: date, session: Session | None = None) -> Decimal | None:
    """In-process cache, then the price_cache table. The bundled file is not a cache hit."""
    key = (asset.upper(), day.isoformat())
    if key in _memory:
        return _memory[key]
    if session is not None:
        row = session.exec(
            select(PriceCache).where(
                PriceCache.asset == asset.upper(), PriceCache.day == day.isoformat()
            )
        ).first()
        if row is not None:
            price = Decimal(str(row.price_inr))
            _memory[key] = price
            return price
    return None


def remember(
    asset: str, day: date, price: Decimal, source: str, session: Session | None = None
) -> Decimal:
    _memory[(asset.upper(), day.isoformat())] = price
    if session is not None:
        existing = session.exec(
            select(PriceCache).where(
                PriceCache.asset == asset.upper(), PriceCache.day == day.isoformat()
            )
        ).first()
        if existing is None:
            session.add(
                PriceCache(asset=asset.upper(), day=day.isoformat(), price_inr=price, source=source)
            )
            session.commit()
    return price


async def _coingecko(asset: str, day: date, settings: Settings) -> Decimal | None:
    global _circuit_failures, _circuit_open_until
    now = asyncio.get_event_loop().time()
    if _circuit_failures >= 3 and now < _circuit_open_until:
        logger.info("price_circuit_open", asset=asset, day=day.isoformat())
        return None
    coin = settings.coingecko_ids.get(asset.upper())
    if not coin:
        return None
    url = f"{settings.coingecko_base}/coins/{coin}/history"
    params = {"date": day.strftime("%d-%m-%Y"), "localization": "false"}
    delay = 0.3
    async with httpx.AsyncClient(timeout=6) as client:
        for attempt in range(3):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "retry", request=response.request, response=response
                    )
                response.raise_for_status()
                payload = response.json()
                raw = payload.get("market_data", {}).get("current_price", {}).get("inr")
                if raw is None:
                    return None
                _circuit_failures = 0
                return Decimal(str(raw))
            except (httpx.HTTPError, ValueError) as exc:
                logger.info("price_retry", asset=asset, attempt=attempt, error=str(exc))
                if attempt == 2:
                    _circuit_failures += 1
                    if _circuit_failures >= 3:
                        _circuit_open_until = asyncio.get_event_loop().time() + 60
                    return None
                await asyncio.sleep(delay)
                delay *= 2
    return None


async def get_price_inr(
    asset: str, when: datetime | date, session: Session | None = None
) -> Decimal | None:
    """Local cache, then CoinGecko when enabled, then the bundled file. Never raises."""
    settings = get_settings()
    day = _as_date(when) if isinstance(when, datetime) else when
    cached = lookup_cached(asset, day, session)
    if cached is not None:
        return cached
    if settings.prices_online:
        live = await _coingecko(asset.upper(), day, settings)
        if live is not None:
            return remember(asset, day, live, "coingecko", session)
        logger.info("price_fallback", asset=asset, day=day.isoformat())
    bundled = fallback_price(asset, day)
    if bundled is not None:
        return remember(asset, day, bundled, "fallback", session)
    logger.info("price_missing", asset=asset, day=day.isoformat())
    return None


def get_price_inr_sync(
    asset: str, when: datetime | date, session: Session | None = None
) -> Decimal | None:
    day = _as_date(when) if isinstance(when, datetime) else when
    cached = lookup_cached(asset, day, session)
    if cached is not None:
        return cached
    settings = get_settings()
    if settings.prices_online:
        try:
            live = asyncio.run(_coingecko(asset.upper(), day, settings))
        except RuntimeError:
            live = None
            logger.info("price_skip_running_loop", asset=asset)
        if live is not None:
            return remember(asset, day, live, "coingecko", session)
        logger.info("price_fallback", asset=asset, day=day.isoformat())
    bundled = fallback_price(asset, day)
    if bundled is not None:
        return remember(asset, day, bundled, "fallback", session)
    logger.info("price_missing", asset=asset, day=day.isoformat())
    return None


def _as_date(when: datetime | date) -> date:
    if isinstance(when, datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return when.astimezone(UTC).date()
    return when
