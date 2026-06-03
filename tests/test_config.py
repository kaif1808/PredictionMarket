from __future__ import annotations

from server.config import load_settings


def test_load_settings_parses_allowed_origins_and_cookie_secure(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    s = load_settings()
    assert s.allowed_origins == [
        "https://a.example",
        "http://a.example",
        "https://b.example",
        "http://b.example",
    ]
    assert s.cookie_secure is True


def test_load_settings_parses_host_only_allowed_origins(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "predictionmarket-1c97c5cc79dd.herokuapp.com")
    s = load_settings()
    assert s.allowed_origins == [
        "https://predictionmarket-1c97c5cc79dd.herokuapp.com",
        "http://predictionmarket-1c97c5cc79dd.herokuapp.com",
    ]


def test_load_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TOURNAMENT_TIE_BREAK_MODE", raising=False)
    monkeypatch.delenv("LMSR_B_PARAMETER", raising=False)
    monkeypatch.delenv("ENABLE_ABM", raising=False)
    s = load_settings()
    assert "http://127.0.0.1:5173" in s.allowed_origins
    assert s.cookie_secure is False
    assert s.tournament_tie_break_mode == "shared_prize"
    assert s.lmsr_b_parameter == 18.0
    assert s.enable_abm is False


def test_load_settings_tie_break_mode(monkeypatch) -> None:
    monkeypatch.setenv("TOURNAMENT_TIE_BREAK_MODE", "random")
    assert load_settings().tournament_tie_break_mode == "random"
    monkeypatch.setenv("TOURNAMENT_TIE_BREAK_MODE", "invalid-mode")
    assert load_settings().tournament_tie_break_mode == "shared_prize"


def test_load_settings_lmsr_b_parameter(monkeypatch) -> None:
    monkeypatch.setenv("LMSR_B_PARAMETER", "22.5")
    assert load_settings().lmsr_b_parameter == 22.5
    monkeypatch.setenv("LMSR_B_PARAMETER", "-1")
    assert load_settings().lmsr_b_parameter == 18.0


def test_load_settings_enable_abm(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_ABM", "true")
    assert load_settings().enable_abm is True
    monkeypatch.setenv("ENABLE_ABM", "false")
    assert load_settings().enable_abm is False
