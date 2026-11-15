"""Shared parsing helpers for every connector. Bad values raise ValueError; callers record ImportIssue."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.config import get_settings

IST = timezone(timedelta(hours=5, minutes=30))

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d",
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %I:%M %p",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
)

_CURRENCY_CHARS = str.maketrans("", "", "₹$€£ ")


def parse_decimal(raw: Any) -> Decimal:
    if raw is None:
        raise ValueError("empty number")
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return Decimal(raw)
    if isinstance(raw, float):
        return Decimal(str(raw))
    text = str(raw).translate(_CURRENCY_CHARS).strip()
    if text == "" or text.lower() in {"null", "none", "nan"}:
        raise ValueError("empty number")
    if re.fullmatch(r"-?[\d,]+", text) and "," in text:
        parts = text.split(",")
        if len(parts[-1]) in (1, 2) and all(part.replace("-", "", 1).isdigit() for part in parts):
            sign = "-" if text.startswith("-") else ""
            digits = [part[1:] if part.startswith("-") else part for part in parts]
            text = sign + "".join(digits[:-1]) + "." + digits[-1]
        else:
            text = text.replace(",", "")
    elif "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"non-numeric quantity: {raw}") from exc


def parse_datetime(raw: Any, assume_tz: timezone = UTC) -> datetime:
    if raw is None:
        raise ValueError("unparseable date")
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=assume_tz).astimezone(UTC)
        return raw.astimezone(UTC)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return datetime.fromtimestamp(int(raw), tz=UTC)
    text = str(raw).strip()
    if text == "":
        raise ValueError("unparseable date")
    if re.fullmatch(r"\d{9,13}", text):
        seconds = int(text)
        if len(text) >= 13:
            seconds = seconds // 1000
        return datetime.fromtimestamp(seconds, tz=UTC)
    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=assume_tz)
        return parsed.astimezone(UTC)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=assume_tz)
        return parsed.astimezone(UTC)
    raise ValueError("unparseable date")


def canonical_asset(raw: str) -> str:
    token = raw.strip().upper()
    if token == "":
        raise ValueError("unknown ticker")
    aliases = get_settings().ticker_aliases
    token = aliases.get(token, token)
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", token):
        raise ValueError("unknown ticker")
    return token


def split_pair(pair: str) -> tuple[str, str]:
    text = pair.strip().upper().replace("-", "").replace("_", "")
    if "/" in pair:
        base, quote = pair.upper().split("/", 1)
        return canonical_asset(base), quote.strip().upper()
    quotes = sorted(get_settings().known_quotes, key=len, reverse=True)
    for quote in quotes:
        if text.endswith(quote) and len(text) > len(quote):
            return canonical_asset(text[: -len(quote)]), quote
    raise ValueError(f"unknown pair: {pair}")


def strip_unit(raw: str) -> tuple[Decimal, str | None]:
    text = str(raw).strip()
    if text == "":
        raise ValueError("non-numeric quantity")
    match = re.fullmatch(r"([+-]?[0-9][0-9.,]*)\s*([A-Za-z]+)?", text)
    if not match:
        raise ValueError("non-numeric quantity")
    qty = parse_decimal(match.group(1))
    unit = match.group(2).upper() if match.group(2) else None
    return qty, unit


def dec_str(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def stable_key(
    source: str,
    source_row: int,
    ts_utc: datetime,
    kind: str,
    asset: str,
    side: str | None,
    qty: Decimal,
    price_inr: Decimal | None,
    tx_hash: str | None,
) -> str:
    parts = [
        source,
        str(source_row),
        as_utc(ts_utc).isoformat(),
        kind,
        asset,
        side or "",
        dec_str(qty),
        dec_str(price_inr),
        (tx_hash or "").lower(),
    ]
    return "|".join(parts)
