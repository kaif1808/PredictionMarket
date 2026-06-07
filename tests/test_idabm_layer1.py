"""Tests for calibration.idabm.layer1_lmsr."""
from __future__ import annotations

import pytest

from calibration.idabm.data import build_trade_panel, load_raw
from calibration.idabm.layer1_lmsr import replay_all_markets, replay_market


@pytest.fixture(scope="module")
def panel():
    return build_trade_panel(load_raw())


def test_replay_rmse_aggregate(panel):
    result = replay_all_markets(panel)
    assert result["aggregate_rmse"] < 1e-6, (
        f"Aggregate LMSR replay RMSE too large: {result['aggregate_rmse']}"
    )


def test_replay_all_markets_pass(panel):
    result = replay_all_markets(panel)
    for market_id, r in result["per_market"].items():
        assert r["passed"], (
            f"Market {market_id} replay failed: RMSE={r['rmse']}"
        )


def test_replay_holdings_match(panel):
    """Recomputed q_yes/q_no match stored q_yes_after/q_no_after within 1e-4."""
    for market_id, grp in panel.groupby("market_id"):
        result = replay_market(grp, b=36.0)
        assert result["max_holdings_err"] < 1e-4, (
            f"Market {market_id} holdings drift: {result['max_holdings_err']}"
        )


def test_replay_single_market_structure():
    """Replay returns expected keys."""
    raw = load_raw()
    panel = build_trade_panel(raw)
    first_mid = panel["market_id"].iloc[0]
    grp = panel[panel["market_id"] == first_mid]
    result = replay_market(grp)
    assert "rmse" in result
    assert "passed" in result
    assert "n_trades" in result
    assert result["n_trades"] > 0
