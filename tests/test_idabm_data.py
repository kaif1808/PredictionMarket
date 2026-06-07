"""Tests for calibration.idabm.data."""
from __future__ import annotations

import pandas as pd
import pytest

from calibration.idabm.data import build_market_deviation, build_trade_panel, load_raw


@pytest.fixture(scope="module")
def raw():
    return load_raw()


@pytest.fixture(scope="module")
def panel(raw):
    return build_trade_panel(raw)


def test_markets_count(raw):
    markets = raw["markets"]
    assert len(markets) == 15
    practice = markets[markets["is_practice"].astype(bool)]
    assert len(practice) == 3
    assert set(practice["id"].tolist()) == {1, 2, 34}


def test_panel_non_practice_markets(panel, raw):
    markets = raw["markets"]
    non_practice_ids = set(markets.loc[~markets["is_practice"].astype(bool), "id"].tolist())
    assert panel["market_id"].isin(non_practice_ids).all()
    assert panel["market_id"].nunique() == 12


def test_panel_no_nan_key_features(panel):
    key_cols = [
        "direction", "quantity", "is_informed", "is_whale",
        "perceived_posterior", "yes_exposure_up", "balance_at_trade",
        "round_number",
    ]
    for col in key_cols:
        assert panel[col].isna().sum() == 0, f"NaN found in column {col}"


def test_yes_exposure_up_values(panel):
    assert set(panel["yes_exposure_up"].unique()).issubset({0, 1})


def test_balance_at_trade_reconstruction(panel, raw):
    """For the first trade of any (market, participant), balance_at_trade == starting_balance."""
    panel_sorted = panel.sort_values(["market_id", "participant_id", "executed_at"])
    first_trades = panel_sorted.groupby(["market_id", "participant_id"]).first().reset_index()
    diff = (first_trades["balance_at_trade"] - first_trades["starting_balance"]).abs()
    assert (diff < 1e-6).all(), f"First-trade balance mismatch: max={diff.max()}"


def test_market_deviation_rows(raw):
    dev = build_market_deviation(raw)
    assert len(dev) == 12, f"Expected 12 deviation rows, got {len(dev)}"
    assert "abs_deviation_benchmark" in dev.columns
    assert dev["abs_deviation_benchmark"].isna().sum() == 0


def test_perceived_posterior_bounds(panel):
    assert (panel["perceived_posterior"] >= 0.0).all()
    assert (panel["perceived_posterior"] <= 1.0).all()


def test_perceived_edge_consistency(panel):
    """perceived_edge = perceived_posterior - price_before."""
    expected = panel["perceived_posterior"] - panel["price_before"].astype(float)
    diff = (panel["perceived_edge"] - expected).abs()
    assert (diff < 1e-9).all()
