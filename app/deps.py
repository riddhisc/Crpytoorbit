"""FastAPI dependencies: database session, settings, and writer auth."""

import hashlib
import hmac
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.errors import AppError


def settings_dep() -> Settings:
    return get_settings()


def db_session() -> Iterator[Session]:
    yield from get_session()


def _digest_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256(left.encode()).digest(),
        hashlib.sha256(right.encode()).digest(),
    )


def require_writer(
    request: Request,
    settings: Annotated[Settings, Depends(settings_dep)],
) -> str:
    if settings.demo_mode:
        return "demo-user"
    supplied = request.headers.get("X-API-Key", "")
    if not settings.api_key or not _digest_equal(supplied, settings.api_key):
        raise AppError(401, "UNAUTHORIZED", "Write endpoints require a valid X-API-Key header.")
    return "api-key"


DbSession = Annotated[Session, Depends(db_session)]
AppSettings = Annotated[Settings, Depends(settings_dep)]
Actor = Annotated[str, Depends(require_writer)]
