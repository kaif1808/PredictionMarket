"""Tests for calibration.idabm.layer2_info."""
from __future__ import annotations

import pytest

from calibration.idabm.data import load_raw
from calibration.idabm.layer2_info import (
    empirical_signal_outcome_map,
    is_monotone_in_score,
    recompute_signal_posteriors,
)


@pytest.fixture(scope="module")
def raw():
    return load_raw()


def test_posterior_recompute_max_err(raw):
    result = recompute_signal_posteriors(raw["signals"], rounds=raw["rounds"])
    assert result["max_abs_err"] < 1e-6, (
        f"Posterior recompute max abs err too large: {result['max_abs_err']}"
    )


def test_posterior_recompute_n_signals(raw):
    result = recompute_signal_posteriors(raw["signals"], rounds=raw["rounds"])
    # There should be delivered signals
    assert result["n_signals"] > 0


def test_signal_map_returns_dataframe(raw):
    smap = empirical_signal_outcome_map(
        raw["signals"], raw["rounds"], raw["markets"], raw["market_resolutions"]
    )
    assert not smap.empty
    assert "signal_value" in smap.columns
    assert "mean_posterior" in smap.columns


def test_signal_map_monotone_for_yes_outcome(raw):
    smap = empirical_signal_outcome_map(
        raw["signals"], raw["rounds"], raw["markets"], raw["market_resolutions"]
    )
    # Filter to outcome=1 (YES), check that higher signal_score → higher mean posterior
    yes_smap = smap[smap["outcome"] == 1]
    if len(yes_smap) < 2:
        pytest.skip("Not enough signal values with YES outcome to check monotonicity")
    assert is_monotone_in_score(smap, outcome=1), (
        "Posterior not monotonically increasing in SIGNAL_SCORE for YES outcome"
    )
