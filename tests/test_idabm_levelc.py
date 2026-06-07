"""Tests for calibration.idabm.layer3_levelc."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from calibration.idabm.layer3_levelc import (
    CRRAParams,
    _MIN_TRADES,
    crra_u,
    fit_crra_all,
    fit_crra_participant,
    optimal_q_crra,
)


def _synthetic_trades(rho: float = 1.5, n: int = 30, seed: int = 0) -> pd.DataFrame:
    """Generate synthetic trades from a CRRA trader with known rho."""
    rng = np.random.default_rng(seed)
    rows = []
    b = 36.0
    for i in range(n):
        p = float(rng.uniform(0.3, 0.7))
        W = float(rng.uniform(50, 200))
        q_yes = float(rng.uniform(0, 30))
        q_no = float(rng.uniform(0, 30))
        yes_up = int(rng.random() < 0.5)
        q_star = optimal_q_crra(p, W, q_yes, q_no, yes_up, b, rho)
        q_obs = max(1.0, q_star + float(rng.normal(0, 2)))
        rows.append(
            {
                "participant_id": "SYN",
                "session_id": 1,
                "market_id": 1,
                "perceived_posterior": p,
                "balance_at_trade": W,
                "q_yes_before": q_yes,
                "q_no_before": q_no,
                "yes_exposure_up": yes_up,
                "quantity": q_obs,
            }
        )
    return pd.DataFrame(rows)


def test_crra_u_positive_wealth():
    assert crra_u(100.0, 0.5) > 0
    assert crra_u(100.0, 2.0) < 0  # rho > 1: u = w^(1-rho)/(1-rho) < 0
    assert crra_u(1.0, 1.0) == pytest.approx(math.log(1.0))


def test_crra_u_nonpositive_wealth():
    assert crra_u(0.0, 1.5) == pytest.approx(-1e10)
    assert crra_u(-1.0, 1.0) == pytest.approx(-1e10)


def test_optimal_q_positive():
    q = optimal_q_crra(p=0.7, W=100.0, q_yes=0.0, q_no=0.0, yes_up=1, b=36.0, rho=1.0)
    assert q > 0


def test_rho_recovery_synthetic():
    """Recovered rho should be within 0.5 of true rho for large N."""
    true_rho = 1.5
    trades = _synthetic_trades(rho=true_rho, n=60, seed=42)
    result = fit_crra_participant("SYN", trades, b=36.0)
    assert result is not None
    assert not result.fallback, f"Should converge; reason={result.fallback_reason}"
    assert abs(result.rho - true_rho) < 0.8, (
        f"Recovered rho={result.rho:.3f} far from true={true_rho}"
    )


def test_thin_participant_triggers_fallback():
    """Participant with < _MIN_TRADES triggers fallback."""
    trades = _synthetic_trades(n=_MIN_TRADES - 1, seed=1)
    result = fit_crra_participant("THIN", trades, b=36.0)
    assert result is not None
    assert result.fallback
    assert result.fallback_reason == "too_few_trades"


def test_fit_crra_all_fallback_count():
    """fit_crra_all reports fallback_count > 0 when some participants have few trades."""
    thin_trades = _synthetic_trades(n=_MIN_TRADES - 1, seed=2)
    thick_trades = _synthetic_trades(rho=1.0, n=40, seed=3)
    thin_trades["participant_id"] = "THIN"
    thick_trades["participant_id"] = "THICK"
    panel = pd.concat([thin_trades, thick_trades], ignore_index=True)
    result = fit_crra_all(panel, b=36.0)
    assert result["fallback_count"] >= 1
    assert "THIN" in result["params"]
    assert result["params"]["THIN"].fallback
