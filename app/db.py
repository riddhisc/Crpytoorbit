"""Database engine, sessions, and Alembic bootstrap."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.config import get_settings

_engine: Engine | None = None


def _prepare_url(url: str) -> str:
    if url.startswith("sqlite:///./"):
        Path("data").mkdir(parents=True, exist_ok=True)
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = _prepare_url(get_settings().database_url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def session_scope() -> Session:
    return Session(get_engine())


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    if get_settings().database_url.startswith("sqlite:///./"):
        Path("data").mkdir(parents=True, exist_ok=True)
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    command.upgrade(cfg, "head")
