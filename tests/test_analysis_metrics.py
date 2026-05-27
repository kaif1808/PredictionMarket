from __future__ import annotations

import pandas as pd

from analysis.load import SessionFrames
from analysis.metrics import price_path_deviation, round_volume, treatment_panel


def _frames() -> SessionFrames:
    sessions = pd.DataFrame([{"id": 1}])
    markets = pd.DataFrame(
        [
            {"id": 11, "market_number": 1, "stage": 1, "scenario_id": "C"},
        ]
    )
    rounds = pd.DataFrame(
        [
            {"id": 101, "market_id": 11, "round_number": 1, "closing_price": 0.6, "bayesian_benchmark": 0.55},
        ]
    )
    trades = pd.DataFrame(
        [
            {"round_id": 101, "quantity": 3, "cost": 1.5},
            {"round_id": 101, "quantity": 2, "cost": 1.1},
        ]
    )
    signals = pd.DataFrame([])
    market_roles = pd.DataFrame([])
    tournament = pd.DataFrame([])
    return SessionFrames(
        sessions=sessions,
        markets=markets,
        rounds=rounds,
        trades=trades,
        signals=signals,
        market_roles=market_roles,
        tournament=tournament,
    )


def test_price_path_deviation() -> None:
    out = price_path_deviation(_frames())
    assert len(out) == 1
    assert round(float(out.iloc[0]["abs_deviation"]), 4) == 0.05


def test_round_volume() -> None:
    out = round_volume(_frames())
    assert len(out) == 1
    assert int(out.iloc[0]["volume_contracts"]) == 5


def test_treatment_panel() -> None:
    out = treatment_panel(_frames())
    assert len(out) == 1
    assert int(out.iloc[0]["stage"]) == 1
    assert float(out.iloc[0]["turnover"]) == 2.6
