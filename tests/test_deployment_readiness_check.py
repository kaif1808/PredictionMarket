from __future__ import annotations

from scripts.deployment_readiness_check import run_checks


def test_deployment_readiness_local_mode_warns_but_passes(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TOURNAMENT_TIE_BREAK_MODE", raising=False)

    report = run_checks(strict_env=False)
    assert report.ok is True
    assert any("COOKIE_SECURE" in w for w in report.warnings)


def test_deployment_readiness_strict_mode_valid_env_passes(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://db.example/valdoria")
    monkeypatch.setenv("SESSION_SECRET", "this-is-not-default")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("TOURNAMENT_TIE_BREAK_MODE", "shared_prize")

    report = run_checks(strict_env=True)
    assert report.ok is True
    assert report.errors == []


def test_deployment_readiness_strict_mode_missing_env_fails(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASS", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.setenv("TOURNAMENT_TIE_BREAK_MODE", "random")

    report = run_checks(strict_env=True)
    assert report.ok is False
    assert any("Missing required environment variable" in e for e in report.errors)
    assert any("COOKIE_SECURE must be true" in e for e in report.errors)
