from __future__ import annotations

import os
from contextlib import contextmanager
from statistics import mean
from typing import Any

from analysis.load import load_session
from analysis.metrics import price_path_deviation
from analysis.outcomes import convergence_speed, informed_returns, information_revelation_correlation, price_accuracy, trading_volume


@contextmanager
def _database_url(database_url: str):
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev


def _session_metrics(session_id: int, database_url: str) -> dict[str, Any]:
    with _database_url(database_url):
        frames = load_session(session_id)

    accuracy_df = price_accuracy(frames)
    deviation_df = price_path_deviation(frames)
    converge_df = convergence_speed(frames)
    volume_df = trading_volume(frames)
    returns_df = informed_returns(frames)
    info_df = information_revelation_correlation(frames)

    informed_mean = float("nan")
    uninformed_mean = float("nan")
    treatment_effect = float("nan")
    if not returns_df.empty:
        by_role = returns_df.groupby("role_tier")["return_ratio"].mean()
        informed_mean = float(by_role.get("informed", float("nan")))
        uninformed_mean = float(by_role.get("uninformed", float("nan")))
        if by_role.get("informed") is not None and by_role.get("uninformed") is not None:
            treatment_effect = informed_mean - uninformed_mean

    return {
        "session_id": session_id,
        "price_mse_vs_truth": float((accuracy_df["price_error"] ** 2).mean()) if not accuracy_df.empty else float("nan"),
        "price_mse_vs_benchmark": float((deviation_df["abs_deviation"] ** 2).mean()) if not deviation_df.empty else float("nan"),
        "convergence_lag_mean": float(converge_df["convergence_round"].dropna().mean()) if not converge_df.empty else float("nan"),
        "price_path_variance": float(frames.rounds["closing_price"].astype(float).var()) if not frames.rounds.empty else float("nan"),
        "trading_volume_total": float(volume_df["volume_contracts"].sum()) if not volume_df.empty else 0.0,
        "informed_return_ratio_mean": informed_mean,
        "uninformed_return_ratio_mean": uninformed_mean,
        "treatment_effect_return_ratio": treatment_effect,
        "info_revelation_corr_mean": float(info_df["corr_avg_posterior_vs_price"].dropna().mean()) if not info_df.empty else float("nan"),
    }


def simulation_report(*, session_ids: list[int], database_url: str) -> dict[str, Any]:
    per_session = [_session_metrics(session_id=sid, database_url=database_url) for sid in session_ids]
    scalar_keys = [
        "price_mse_vs_truth",
        "price_mse_vs_benchmark",
        "convergence_lag_mean",
        "price_path_variance",
        "trading_volume_total",
        "informed_return_ratio_mean",
        "uninformed_return_ratio_mean",
        "treatment_effect_return_ratio",
        "info_revelation_corr_mean",
    ]
    aggregate: dict[str, float] = {}
    for key in scalar_keys:
        vals = [row[key] for row in per_session if row[key] == row[key]]
        aggregate[key] = float(mean(vals)) if vals else float("nan")
    return {"session_ids": session_ids, "per_session": per_session, "aggregate": aggregate}
