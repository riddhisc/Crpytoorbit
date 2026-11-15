"""Suggest a column mapping without an API key. An LLM is optional and never trusted raw."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from rapidfuzz import fuzz

from app.config import Settings
from app.parsing import parse_datetime, parse_decimal

SYNONYMS: dict[str, list[str]] = {
    "ts": ["date", "time", "trade time", "timestamp", "date(utc)", "datetime"],
    "asset": ["coin", "asset", "symbol", "currency", "token", "market"],
    "side": ["side", "direction", "type", "buy/sell"],
    "qty": ["volume", "units", "executed", "quantity", "qty", "amount", "size"],
    "price": ["price", "rate", "price (inr)", "trade price"],
    "fee": ["fee", "charge", "commission", "fees"],
    "fee_asset": ["fee currency", "fee coin", "fee asset"],
    "tx_hash": ["txhash", "txid", "hash", "transaction hash"],
    "pair": ["pair", "market", "symbol"],
}


def suggest_mapping(headers: list[str], sample_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    used: set[str] = set()
    for field, synonyms in SYNONYMS.items():
        best_header = ""
        best_score = 0.0
        for header in headers:
            score = max(fuzz.token_set_ratio(header.lower(), synonym) for synonym in synonyms)
            score = max(score, fuzz.ratio(header.lower(), field.replace("_", " ")))
            sniffed = _sniff_boost(field, header, sample_rows)
            score = min(100, score + sniffed)
            if score > best_score:
                best_score = score
                best_header = header
        if best_score >= 55 and best_header not in used:
            used.add(best_header)
            suggestions.append(
                {
                    "field": field,
                    "header": best_header,
                    "confidence": best_score / 100,
                    "source": "fuzzy",
                }
            )
    return suggestions


def _sniff_boost(field: str, header: str, rows: list[dict[str, str]]) -> int:
    values = [row.get(header, "") for row in rows[:5] if row.get(header, "").strip()]
    if not values:
        return 0
    if field == "ts":
        hits = 0
        for value in values:
            try:
                parse_datetime(value)
                hits += 1
            except ValueError:
                pass
        return 25 if hits >= max(1, len(values) // 2) else 0
    if field in {"qty", "price", "fee"}:
        hits = sum(1 for value in values if _is_number(value))
        return 15 if hits >= max(1, len(values) // 2) else 0
    if field == "asset":
        hits = sum(1 for value in values if re.fullmatch(r"[A-Za-z]{2,10}", value.strip()))
        return 20 if hits >= max(1, len(values) // 2) else 0
    return 0


def _is_number(value: str) -> bool:
    try:
        parse_decimal(value)
    except ValueError:
        return False
    return True


async def suggest_with_llm(
    headers: list[str],
    sample_rows: list[dict[str, str]],
    settings: Settings,
) -> list[dict[str, Any]] | None:
    """Send only the header and up to five sample rows. Returns None when no key is set."""
    if not settings.anthropic_api_key:
        return None
    trimmed = sample_rows[:5]
    prompt = {
        "headers": headers,
        "sample_rows": trimmed,
        "fields": list(SYNONYMS),
    }
    delay = 0.3
    async with httpx.AsyncClient(timeout=12) as client:
        for attempt in range(3):
            try:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-latest",
                        "max_tokens": 600,
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "Map CSV headers to canonical fields. Reply with JSON only: "
                                    '{"suggestions":[{"field","header","confidence"}]}. '
                                    "Use only the provided headers.\n" + json.dumps(prompt)
                                ),
                            }
                        ],
                    },
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "retry", request=response.request, response=response
                    )
                response.raise_for_status()
                text = "".join(
                    block.get("text", "")
                    for block in response.json().get("content", [])
                    if isinstance(block, dict)
                )
                parsed = json.loads(text[text.find("{") : text.rfind("}") + 1])
                cleaned = []
                allowed = set(headers)
                for item in parsed.get("suggestions", []):
                    if item.get("header") in allowed and item.get("field") in SYNONYMS:
                        cleaned.append(
                            {
                                "field": item["field"],
                                "header": item["header"],
                                "confidence": float(item.get("confidence") or 0.5),
                                "source": "llm",
                            }
                        )
                return cleaned
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                if attempt == 2:
                    return None
                import asyncio

                await asyncio.sleep(delay)
                delay *= 2
    return None
