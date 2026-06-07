"""Layer 2 — posterior recompute gate and empirical signal×outcome map."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.bayesian import SIGNAL_SCORE, update_posterior


def recompute_signal_posteriors(
    signals: pd.DataFrame,
    rounds: Optional[pd.DataFrame] = None,
    prior: float = 0.5,
) -> dict[str, Any]:
    """
    Check that stored posteriors are reproducible by update_posterior.

    Two modes co-exist in the data:
      - Fresh-0.5 (sessions 1 & 2): each round draws from prior=0.5 independently.
      - Accumulated (session 35): each round's prior = stored posterior from prior round.

    For each signal, we test both modes and take min error. If either mode reproduces
    the stored posterior exactly, the gate passes.
    Gate: max(min_error) < 1e-6.
    """
    delivered = signals[signals["delivered"].astype(bool)].copy()
    if delivered.empty:
        return {"max_abs_err": 0.0, "passed": True, "n_signals": 0}

    if rounds is not None:
        delivered = delivered.merge(
            rounds[["id", "market_id", "round_number"]].rename(columns={"id": "round_id"}),
            on="round_id",
            how="left",
        )
    else:
        delivered["market_id"] = 0
        delivered["round_number"] = 0

    errors: list[float] = []
    group_keys = ["market_id", "participant_id"]

    for _, grp in delivered.groupby(group_keys):
        grp = grp.sort_values("round_number")
        accumulated_prior = prior  # tracks running prior = stored posterior of prev round

        for _, row in grp.iterrows():
            sv = str(row["signal_value"])
            theta = float(row["theta"])
            stored = float(row["posterior"])
            try:
                # Fresh: each round independently draws from prior=0.5
                fresh_err = abs(update_posterior(prior=prior, signal=sv, theta=theta) - stored)
                # Accumulated: prior = stored posterior of previous round
                accum_err = abs(update_posterior(prior=accumulated_prior, signal=sv, theta=theta) - stored)
                errors.append(min(fresh_err, accum_err))
            except Exception:
                errors.append(float("inf"))
            # Always advance accumulated_prior using stored (ground truth)
            accumulated_prior = stored

    max_err = max(errors) if errors else 0.0
    return {
        "max_abs_err": max_err,
        "passed": max_err < 1e-6,
        "n_signals": len(errors),
    }


def empirical_signal_outcome_map(
    signals: pd.DataFrame,
    rounds: pd.DataFrame,
    markets: pd.DataFrame,
    market_resolutions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join signals → rounds → markets → resolutions.
    Group by (signal_value, outcome) → mean posterior.
    Returns DataFrame indexed by signal_value with one column per outcome value.
    """
    sig = signals[signals["delivered"].astype(bool)].copy()
    if sig.empty:
        return pd.DataFrame()

    # rounds: round_id → market_id
    sig = sig.merge(
        rounds[["id", "market_id"]].rename(columns={"id": "round_id"}),
        on="round_id",
        how="left",
    )
    # markets: market_id → session_id (for join with resolutions)
    sig = sig.merge(
        markets[["id"]].rename(columns={"id": "market_id"}),
        on="market_id",
        how="left",
    )
    # market_resolutions: market_id → outcome
    sig = sig.merge(
        market_resolutions[["market_id", "outcome"]],
        on="market_id",
        how="left",
    )

    sig["posterior"] = sig["posterior"].astype(float)
    sig["signal_score"] = sig["signal_value"].map(SIGNAL_SCORE)

    result = (
        sig.dropna(subset=["outcome", "signal_value"])
        .groupby(["signal_value", "outcome"])["posterior"]
        .mean()
        .reset_index()
        .rename(columns={"posterior": "mean_posterior"})
    )
    result["signal_score"] = result["signal_value"].map(SIGNAL_SCORE)
    return result.sort_values(["outcome", "signal_score"])


def is_monotone_in_score(signal_map: pd.DataFrame, outcome: int = 1) -> bool:
    """
    Check that mean_posterior increases monotonically with signal_score for a given outcome.
    S- (-2) → M- (-1) → N (0) → M+ (1) → S+ (2) should give increasing posterior.
    """
    sub = signal_map[signal_map["outcome"] == outcome].sort_values("signal_score")
    if len(sub) < 2:
        return True
    posteriors = sub["mean_posterior"].tolist()
    return all(posteriors[i] <= posteriors[i + 1] for i in range(len(posteriors) - 1))
