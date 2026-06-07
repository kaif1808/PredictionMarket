"""Tests for calibration.idabm.validation."""
from __future__ import annotations

import pytest

from calibration.idabm.data import build_trade_panel, load_raw
from calibration.idabm.validation import (
    _gate_gini,
    _gate_lmsr_rmse,
    _gate_trades_per_round,
    run_validation,
)


@pytest.fixture(scope="module")
def raw():
    return load_raw()


@pytest.fixture(scope="module")
def panel(raw):
    return build_trade_panel(raw)


def test_run_validation_returns_six_rows(panel, raw):
    df, _ = run_validation(panel, raw)
    assert len(df) == 6


def test_run_validation_has_required_columns(panel, raw):
    df, _ = run_validation(panel, raw)
    for col in ["row", "name", "passed", "metric", "threshold"]:
        assert col in df.columns


def test_row1_lmsr_rmse_passes(panel):
    """LMSR RMSE gate passes on real data (mechanical)."""
    name, passed, metric, _ = _gate_lmsr_rmse(panel)
    assert name == "lmsr_rmse"
    assert passed, f"LMSR RMSE gate failed: rmse={metric}"


def test_row5_trades_per_round_passes(panel):
    name, passed, metric, _ = _gate_trades_per_round(panel)
    assert name == "trades_per_round"
    assert passed


def test_row6_gini_gate_exists(panel):
    name, passed, metric, _ = _gate_gini(panel)
    assert name == "gini"
    # metric should be a float
    assert isinstance(metric, float)


def test_validation_all_passed_is_bool(panel, raw):
    _, all_passed = run_validation(panel, raw)
    assert isinstance(all_passed, bool)
