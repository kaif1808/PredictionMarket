from __future__ import annotations

import math

import pandas as pd

from analysis.load import SessionFrames


def _validate_prior(prior: float) -> None:
    if not (0.0 < prior < 1.0):
        raise ValueError("prior must be in (0,1)")


def recompute_round_benchmark(signals: pd.DataFrame, prior: float = 0.5) -> float:
    """Independent Bayesian benchmark recomputation from signal rows.

    Uses a log-odds accumulator and does not depend on server.bayesian.
    """
    _validate_prior(prior)
    log_odds = math.log(prior / (1.0 - prior))
    for row in signals.itertuples(index=False):
        theta = float(row.theta)
        if not (0.5 < theta < 1.0):
            raise ValueError(f"invalid theta={theta}")
        if row.signal_value == "H":
            log_odds += math.log(theta / (1.0 - theta))
        elif row.signal_value == "L":
            log_odds += math.log((1.0 - theta) / theta)
        else:
            raise ValueError(f"invalid signal_value={row.signal_value}")
    if log_odds >= 0:
        z = math.exp(-log_odds)
        return 1.0 / (1.0 + z)
    z = math.exp(log_odds)
    return z / (1.0 + z)


def recompute_session_benchmarks(frames: SessionFrames, prior: float = 0.5) -> pd.DataFrame:
    """Recompute all per-round benchmarks and compare to stored server values."""
    _validate_prior(prior)
    rounds = frames.rounds.copy()
    if rounds.empty:
        return pd.DataFrame(
            columns=[
                "round_id",
                "market_id",
                "round_number",
                "server_benchmark",
                "recomputed_benchmark",
                "abs_diff",
            ]
        )

    signals = frames.signals.copy()
    rows: list[dict[str, float | int | None]] = []
    for rr in rounds.itertuples(index=False):
        s = signals[signals["round_id"] == rr.id]
        recomputed = recompute_round_benchmark(s, prior=prior)
        server_val = float(rr.bayesian_benchmark) if rr.bayesian_benchmark is not None else None
        abs_diff = abs(recomputed - server_val) if server_val is not None else None
        rows.append(
            {
                "round_id": int(rr.id),
                "market_id": int(rr.market_id),
                "round_number": int(rr.round_number),
                "server_benchmark": server_val,
                "recomputed_benchmark": recomputed,
                "abs_diff": abs_diff,
            }
        )
    return pd.DataFrame(rows)
