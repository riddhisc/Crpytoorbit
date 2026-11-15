"""Thresholds, tax rates, and runtime settings.

Tax rates: Verify against current Income Tax rules / consult a CA.
"""

from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Crypto Orbit Reconciliation Desk"
    demo_mode: bool = True
    api_key: str = ""
    database_url: str = "sqlite:///./data/orbit.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    prices_online: bool = False
    etherscan_api_key: str = ""
    anthropic_api_key: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""

    # Reconciliation thresholds
    transfer_window_hours: int = 6
    transfer_tolerance_pct: Decimal = Decimal("0.5")
    price_deviation_pct: Decimal = Decimal("8")
    large_transfer_inr: Decimal = Decimal("1000000")  # ₹10 lakh

    # Verify against current Income Tax rules / consult a CA.
    tax_rate_pct: Decimal = Decimal("30")
    tds_rate_pct: Decimal = Decimal("1")
    fees_as_cost: bool = False

    max_upload_bytes: int = 5_000_000
    max_rows: int = 50_000
    coingecko_base: str = "https://api.coingecko.com/api/v3"
    etherscan_base: str = "https://api.etherscan.io/api"

    ticker_aliases: dict[str, str] = Field(default_factory=lambda: {"XBT": "BTC", "BTCB": "BTC"})
    known_quotes: tuple[str, ...] = ("USDT", "BUSD", "USDC", "INR")
    coingecko_ids: dict[str, str] = Field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "USDT": "tether",
        }
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
