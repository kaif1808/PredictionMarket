from __future__ import annotations

import pandas as pd
import pytest

from analysis.load import SessionFrames
from analysis.outcomes import (
    convergence_speed,
    informed_returns,
    information_revelation_correlation,
    price_accuracy,
    price_impact,
    return_inequality,
    trading_volume,
)


def _frames() -> SessionFrames:
    return SessionFrames(
        sessions=pd.DataFrame([{"id": 1}]),
        markets=pd.DataFrame(
            [
                {"id": 11, "market_number": 1, "true_probability": 0.5},
            ]
        ),
        rounds=pd.DataFrame(
            [
                {"id": 101, "market_id": 11, "round_number": 1, "closing_price": 0.55, "bayesian_benchmark": 0.52},
                {"id": 102, "market_id": 11, "round_number": 2, "closing_price": 0.58, "bayesian_benchmark": 0.57},
            ]
        ),
        trades=pd.DataFrame(
            [
                {
                    "id": 1,
                    "market_id": 11,
                    "round_id": 101,
                    "direction": "yes",
                    "quantity": 2,
                    "price_before": 0.5,
                    "price_after": 0.53,
                },
                {
                    "id": 2,
                    "market_id": 11,
                    "round_id": 102,
                    "direction": "no",
                    "quantity": 1,
                    "price_before": 0.58,
                    "price_after": 0.56,
                },
            ]
        ),
        signals=pd.DataFrame(
            [
                {"round_id": 101, "delivered": True, "posterior": 0.7},
                {"round_id": 102, "delivered": True, "posterior": 0.8},
            ]
        ),
        market_roles=pd.DataFrame(
            [
                {
                    "market_id": 11,
                    "participant_id": "P01",
                    "role_tier": "informed",
                    "endowment_tokens": 100.0,
                    "final_balance": 120.0,
                },
                {
                    "market_id": 11,
                    "participant_id": "P02",
                    "role_tier": "uninformed",
                    "endowment_tokens": 100.0,
                    "final_balance": 90.0,
                },
            ]
        ),
        tournament=pd.DataFrame([]),
    )


def test_outcome_shapes_and_core_values() -> None:
    frames = _frames()

    acc = price_accuracy(frames)
    assert len(acc) == 2
    assert float(acc.iloc[0]["price_error"]) == pytest.approx(0.05)

    conv = convergence_speed(frames, threshold=0.02)
    assert int(conv.iloc[0]["convergence_round"]) == 2

    vols = trading_volume(frames)
    assert int(vols["volume_contracts"].sum()) == 3

    impacts = price_impact(frames)
    assert len(impacts) == 2
    assert all(col in impacts.columns for col in ["price_impact", "abs_price_impact"])

    returns = informed_returns(frames)
    p01 = returns[returns["participant_id"] == "P01"].iloc[0]
    assert float(p01["return_tokens"]) == 20.0

    ineq = return_inequality(frames)
    assert len(ineq) == 1
    assert float(ineq.iloc[0]["gini_final_balance"]) >= 0.0

    corr = information_revelation_correlation(frames)
    assert len(corr) == 1
