"""Application settings loaded from .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str = "sqlite:///./data/listings.db"

    # HTTP / scraper
    request_timeout: float = 20.0
    request_min_delay: float = 1.5
    request_max_delay: float = 4.0
    request_max_retries: int = 3
    http_proxy: str | None = None
    stale_days: int = 3
    max_list_pages: int = 20
    detail_workers: int = 4
    source_workers: int = 3

    # Filters
    price_min_eur: int = 150_000
    price_cap_apartment_eur: int = 350_000
    price_cap_house_eur: int = 550_000
    fuzzy_threshold: int = 80

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # Scheduler
    tz: str = "Europe/Sofia"
    daily_hour: int = 7
    daily_minute: int = 0
    weekly_day: str = "mon"
    weekly_hour: int = 8
    weekly_minute: int = 0

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/bgscraper.log"

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def log_file_path(self) -> Path:
        p = Path(self.log_file)
        return p if p.is_absolute() else PROJECT_ROOT / p

    def email_recipients(self) -> list[str]:
        return [addr.strip() for addr in self.email_to.split(",") if addr.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
