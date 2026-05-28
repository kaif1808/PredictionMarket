from __future__ import annotations

import pandas as pd

from analysis.benchmark_recompute import recompute_round_benchmark, recompute_session_benchmarks
from analysis.load import SessionFrames


def test_recompute_round_benchmark_matches_appendix_example() -> None:
    # With informed-only draws at theta=0.85, repeated H signals push benchmark higher.
    signals = pd.DataFrame(
        [
            {"signal_value": "H", "theta": 0.85},
            {"signal_value": "L", "theta": 0.85},
            {"signal_value": "H", "theta": 0.85},
            {"signal_value": "H", "theta": 0.85},
            {"signal_value": "L", "theta": 0.85},
            {"signal_value": "H", "theta": 0.85},
        ]
    )
    out = recompute_round_benchmark(signals, prior=0.5)
    assert 0.96 < out < 0.98


def test_recompute_session_benchmark_table() -> None:
    frames = SessionFrames(
        sessions=pd.DataFrame([{"id": 1}]),
        markets=pd.DataFrame([{"id": 11}]),
        rounds=pd.DataFrame([{"id": 101, "market_id": 11, "round_number": 1, "bayesian_benchmark": 0.6}]),
        trades=pd.DataFrame([]),
        signals=pd.DataFrame(
            [
                {"round_id": 101, "signal_value": "H", "theta": 0.85},
            ]
        ),
        market_roles=pd.DataFrame([]),
        tournament=pd.DataFrame([]),
    )
    out = recompute_session_benchmarks(frames)
    assert len(out) == 1
    assert set(out.columns) == {
        "round_id",
        "market_id",
        "round_number",
        "server_benchmark",
        "recomputed_benchmark",
        "abs_diff",
    }
    assert out.iloc[0]["abs_diff"] is not None
