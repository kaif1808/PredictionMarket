#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.config import load_settings
from server.roles import get_market_config

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "SESSION_SECRET",
    "ADMIN_USER",
    "ADMIN_PASS",
    "ALLOWED_ORIGINS",
]


@dataclass
class CheckReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _parse_web_line(procfile_text: str) -> str | None:
    for line in procfile_text.splitlines():
        if line.strip().startswith("web:"):
            return line.strip()
    return None


def _extract_workers(web_line: str) -> int | None:
    m = re.search(r"--workers\s+(\d+)", web_line)
    return int(m.group(1)) if m else None


def _extract_keepalive(web_line: str) -> int | None:
    m = re.search(r"--timeout-keep-alive\s+(\d+)", web_line)
    return int(m.group(1)) if m else None


def run_checks(strict_env: bool) -> CheckReport:
    report = CheckReport()

    try:
        procfile = _read_text(ROOT / "Procfile")
        runtime = _read_text(ROOT / "runtime.txt")
    except FileNotFoundError as exc:
        report.fail(str(exc))
        return report

    if "release: alembic upgrade head" not in procfile:
        report.fail("Procfile must include release phase: 'release: alembic upgrade head'.")

    web_line = _parse_web_line(procfile)
    if web_line is None:
        report.fail("Procfile must include a web process.")
    else:
        workers = _extract_workers(web_line)
        if workers is None:
            report.fail("Procfile web process must specify '--workers'.")
        elif workers != 1:
            report.fail(f"Procfile web process must use '--workers 1' (found {workers}).")

        keepalive = _extract_keepalive(web_line)
        if keepalive is None:
            report.fail("Procfile web process must specify '--timeout-keep-alive'.")
        elif keepalive < 55:
            report.fail(f"Procfile keep-alive must be >= 55s for router safety (found {keepalive}).")

    runtime_value = runtime.strip()
    if not runtime_value.startswith("python-3.11"):
        report.fail(f"runtime.txt must pin Python 3.11.x (found '{runtime_value}').")

    settings = load_settings()
    if settings.tournament_tie_break_mode not in {"shared_prize", "random"}:
        report.fail(
            "TOURNAMENT_TIE_BREAK_MODE must be 'shared_prize' or 'random'."
        )
    if settings.lmsr_b_parameter <= 0:
        report.fail("LMSR_B_PARAMETER must be > 0.")

    b_values = {
        get_market_config(1, market_number, lmsr_b_parameter=settings.lmsr_b_parameter).b_parameter
        for market_number in [1, 2, 3, 4]
    }
    if len(b_values) != 1:
        report.fail("All markets must use a shared LMSR B value (Part 11 decision #8).")

    if settings.database_url.startswith("postgresql://") or settings.database_url.startswith("postgres://"):
        report.fail(
            "DATABASE_URL must be normalized to SQLAlchemy psycopg form "
            "('postgresql+psycopg://...')."
        )

    if strict_env:
        for var in REQUIRED_ENV_VARS:
            if not os.getenv(var):
                report.fail(f"Missing required environment variable in strict mode: {var}")
        if not settings.cookie_secure:
            report.fail("COOKIE_SECURE must be true in strict mode.")
        if "*" in settings.allowed_origins:
            report.fail("ALLOWED_ORIGINS cannot contain '*' in strict mode.")
        if settings.session_secret == "dev-secret-change-me":
            report.fail("SESSION_SECRET must not use the default development secret in strict mode.")
    else:
        if not settings.cookie_secure:
            report.warn("COOKIE_SECURE is false (expected in local dev, not production).")
        if settings.session_secret == "dev-secret-change-me":
            report.warn("SESSION_SECRET is using development default.")
        if "*" in settings.allowed_origins:
            report.warn("ALLOWED_ORIGINS includes wildcard '*'.")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deployment-readiness constraints from the Valdoria bible."
    )
    parser.add_argument(
        "--strict-env",
        action="store_true",
        help="Fail if production env vars/safety flags are missing or insecure.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON report.",
    )
    args = parser.parse_args()

    report = run_checks(strict_env=args.strict_env)
    if args.json:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
    else:
        status = "PASS" if report.ok else "FAIL"
        print(f"[deployment-readiness] {status}")
        for err in report.errors:
            print(f"ERROR: {err}")
        for warn in report.warnings:
            print(f"WARN: {warn}")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
