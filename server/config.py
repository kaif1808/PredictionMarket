from __future__ import annotations

import os
from dataclasses import dataclass


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_secret: str
    admin_user: str
    admin_pass: str
    log_level: str


def load_settings() -> Settings:
    database_url = _normalize_database_url(
        os.getenv("DATABASE_URL", "sqlite:///./prediction_market.db")
    )
    return Settings(
        database_url=database_url,
        session_secret=os.getenv("SESSION_SECRET", "dev-secret-change-me"),
        admin_user=os.getenv("ADMIN_USER", "admin"),
        admin_pass=os.getenv("ADMIN_PASS", "admin"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

