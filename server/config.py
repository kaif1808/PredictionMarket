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
    allowed_origins: list[str]
    cookie_secure: bool
    tournament_tie_break_mode: str
    lmsr_b_parameter: float
    enable_abm: bool


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_allowed_origins(value: str | None) -> list[str]:
    if value is None or not value.strip():
        return ["http://127.0.0.1:5173", "http://localhost:5173"]
    origins: list[str] = []
    for part in value.split(","):
        entry = part.strip()
        if not entry:
            continue
        if entry == "*":
            origins.append("*")
            continue
        if "://" not in entry:
            origins.extend([f"https://{entry}", f"http://{entry}"])
            continue
        origins.append(entry)
        if entry.startswith("https://"):
            origins.append(f"http://{entry[len('https://'):]}")
        elif entry.startswith("http://"):
            origins.append(f"https://{entry[len('http://'):]}")
    deduped = list(dict.fromkeys(origins))
    return deduped or ["http://127.0.0.1:5173", "http://localhost:5173"]


def _parse_tie_break_mode(value: str | None) -> str:
    if value is None:
        return "shared_prize"
    mode = value.strip().lower()
    if mode in {"shared_prize", "random"}:
        return mode
    return "shared_prize"


def _parse_positive_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value.strip())
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


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
        allowed_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS")),
        cookie_secure=_parse_bool(os.getenv("COOKIE_SECURE"), default=False),
        tournament_tie_break_mode=_parse_tie_break_mode(os.getenv("TOURNAMENT_TIE_BREAK_MODE")),
        lmsr_b_parameter=_parse_positive_float(os.getenv("LMSR_B_PARAMETER"), default=18.0),
        enable_abm=_parse_bool(os.getenv("ENABLE_ABM"), default=False),
    )
