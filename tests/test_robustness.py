from __future__ import annotations

import pandas as pd

from analysis.load import SessionFrames
from analysis.robustness import add_cumulative_interim_balance_position, tournament_effect_robustness


def _frames() -> SessionFrames:
    sessions = pd.DataFrame([{"id": 1}])
    markets = pd.DataFrame(
        [
            {"id": 11, "market_number": 1, "stage": 1, "scenario_id": "C"},
            {"id": 12, "market_number": 2, "stage": 2, "scenario_id": "A"},
        ]
    )
    rounds = pd.DataFrame(
        [
            {"id": 101, "market_id": 11, "round_number": 1, "closing_price": 0.60, "bayesian_benchmark": 0.55},
            {"id": 102, "market_id": 11, "round_number": 2, "closing_price": 0.62, "bayesian_benchmark": 0.56},
            {"id": 201, "market_id": 12, "round_number": 1, "closing_price": 0.40, "bayesian_benchmark": 0.45},
            {"id": 202, "market_id": 12, "round_number": 2, "closing_price": 0.42, "bayesian_benchmark": 0.46},
        ]
    )
    trades = pd.DataFrame(
        [
            {"round_id": 101, "market_id": 11, "participant_id": "P01", "direction": "yes", "quantity": 2, "cost": 1.2},
            {"round_id": 102, "market_id": 11, "participant_id": "P02", "direction": "no", "quantity": 1, "cost": 0.6},
            {"round_id": 201, "market_id": 12, "participant_id": "P01", "direction": "no", "quantity": 2, "cost": 0.8},
            {"round_id": 202, "market_id": 12, "participant_id": "P02", "direction": "yes", "quantity": 1, "cost": 0.5},
        ]
    )
    signals = pd.DataFrame([])
    market_roles = pd.DataFrame(
        [
            {"market_id": 11, "participant_id": "P01", "endowment_tokens": 100.0},
            {"market_id": 11, "participant_id": "P02", "endowment_tokens": 100.0},
            {"market_id": 12, "participant_id": "P01", "endowment_tokens": 100.0},
            {"market_id": 12, "participant_id": "P02", "endowment_tokens": 100.0},
        ]
    )
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


def test_add_cumulative_interim_balance_position() -> None:
    panel = add_cumulative_interim_balance_position(_frames())
    assert "cumulative_interim_balance_position" in panel.columns
    assert len(panel) == 4
    assert (panel["cumulative_interim_balance_position"] >= 0).all()


def test_tournament_effect_robustness_runs() -> None:
    out = tournament_effect_robustness(_frames())
    assert not out.panel.empty
    assert "cumulative_interim_balance_position" in out.panel.columns
    assert set(["term", "coef", "std_err_hc3", "p_value"]).issubset(set(out.regression_table.columns))
    assert isinstance(out.model_summary_text, str)
