"""Tests for calibration.idabm.counterfactual."""
from __future__ import annotations

import numpy as np
import pytest

from calibration.idabm.counterfactual import (
    SessionResult,
    estimate_treatment_effect,
    generate_session,
    run_counterfactual,
)
from calibration.idabm.data import build_trade_panel, load_raw
from calibration.idabm.layer3_levelb import fit_level_b
from calibration.idabm.layer3_levelc import fit_crra_all


@pytest.fixture(scope="module")
def panel():
    return build_trade_panel(load_raw())


@pytest.fixture(scope="module")
def models_b(panel):
    return fit_level_b(panel)


@pytest.fixture(scope="module")
def params_c(panel):
    return fit_crra_all(panel)["params"]


def test_generate_session_returns_result(models_b, params_c):
    rng = np.random.default_rng(0)
    result = generate_session(
        true_probs=[0.5, 0.75, 0.25, 0.65],
        models_b=models_b,
        params_c=params_c,
        rng=rng,
    )
    assert isinstance(result, SessionResult)
    assert 0.0 <= result.abs_deviation_benchmark <= 1.0 or result.abs_deviation_benchmark != result.abs_deviation_benchmark  # allow nan
    assert result.n_markets == 4


def test_generate_session_b_is_always_36(models_b, params_c):
    from calibration.idabm import counterfactual as cf
    assert cf._B == 36.0


def test_run_counterfactual_small(models_b, params_c):
    """Smoke test: n=20 iterations completes and returns expected keys."""
    result = run_counterfactual(
        experiment="order",
        iters=20,
        models_b=models_b,
        params_c=params_c,
        empirical_effect=0.1,
        quantity_source="levelb",
        seed=42,
    )
    assert "treatment_effect" in result
    effect = result["treatment_effect"]
    assert "has_informed" in effect or "coef_has_informed" in effect
    assert "has_whale" in effect or "coef_has_whale" in effect


def test_estimate_treatment_effect_structure():
    results = [
        SessionResult(0.1, 0.3, 1, 0, [0.5, 0.75, 0.25, 0.65], 4),
        SessionResult(0.2, 0.4, 0, 1, [0.5, 0.75, 0.25, 0.65], 4),
        SessionResult(0.15, 0.35, 1, 1, [0.5, 0.75, 0.25, 0.65], 4),
        SessionResult(0.25, 0.45, 0, 0, [0.5, 0.75, 0.25, 0.65], 4),
    ]
    effect = estimate_treatment_effect(results)
    assert "coef_has_informed" in effect
    assert "coef_has_whale" in effect
    assert "n_obs" in effect
    assert effect["n_obs"] == 4
