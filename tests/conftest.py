# ruff: noqa: E402
"""Test environment. Set before the app is imported."""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="orbit-test-"))
_DB = _ROOT / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ["PRICES_ONLINE"] = "false"
os.environ["API_KEY"] = "test-key"
os.environ["ETHERSCAN_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest
from app.config import get_settings
from app.db import reset_engine
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _fresh_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    os.environ["DEMO_MODE"] = "true"
    os.environ["PRICES_ONLINE"] = "false"
    os.environ["API_KEY"] = "test-key"
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    reset_engine()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
