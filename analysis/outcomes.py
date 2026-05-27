from __future__ import annotations

import math

import pandas as pd

from analysis.load import SessionFrames


def _gini(values: list[float]) -> float:
    if not values:
        return 0.0
    arr = sorted(max(float(v), 0.0) for v in values)
    n = len(arr)
    total = sum(arr)
    if total == 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(arr))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def price_accuracy(frames: SessionFrames) -> pd.DataFrame:
    rounds = frames.rounds.merge(frames.markets[["id", "market_number", "true_probability"]], left_on="market_id", right_on="id")
    rounds["price_error"] = (rounds["closing_price"] - rounds["true_probability"]).abs()
    return rounds[["market_id", "market_number", "round_number", "price_error"]]


def convergence_speed(frames: SessionFrames, threshold: float = 0.05) -> pd.DataFrame:
    rounds = frames.rounds.copy()
    if rounds.empty:
        return pd.DataFrame(columns=["market_id", "convergence_round"])
    rounds["abs_dev"] = (rounds["closing_price"] - rounds["bayesian_benchmark"]).abs()
    converged = rounds[rounds["abs_dev"] <= threshold].groupby("market_id", as_index=False)["round_number"].min()
    converged = converged.rename(columns={"round_number": "convergence_round"})
    all_markets = rounds[["market_id"]].drop_duplicates()
    return all_markets.merge(converged, on="market_id", how="left")


def price_path_deviation(frames: SessionFrames) -> pd.DataFrame:
    rounds = frames.rounds.copy()
    rounds["abs_deviation"] = (rounds["closing_price"] - rounds["bayesian_benchmark"]).abs()
    return rounds[["market_id", "round_number", "abs_deviation"]]


def insider_returns(frames: SessionFrames) -> pd.DataFrame:
    roles = frames.market_roles.copy()
    if roles.empty:
        return pd.DataFrame(columns=["market_id", "participant_id", "role_tier", "return_tokens", "return_ratio"])
    roles["return_tokens"] = roles["final_balance"] - roles["endowment_tokens"]
    roles["return_ratio"] = roles["return_tokens"] / roles["endowment_tokens"]
    return roles[["market_id", "participant_id", "role_tier", "return_tokens", "return_ratio"]]


def return_inequality(frames: SessionFrames) -> pd.DataFrame:
    roles = frames.market_roles.copy()
    if roles.empty:
        return pd.DataFrame(columns=["market_id", "gini_final_balance"])
    rows: list[dict[str, float | int]] = []
    for market_id, grp in roles.groupby("market_id"):
        vals = [float(x) for x in grp["final_balance"].dropna().tolist()]
        rows.append({"market_id": int(market_id), "gini_final_balance": _gini(vals)})
    return pd.DataFrame(rows)


def trading_volume(frames: SessionFrames) -> pd.DataFrame:
    if frames.trades.empty:
        return pd.DataFrame(columns=["market_id", "round_id", "volume_contracts"])
    return (
        frames.trades.groupby(["market_id", "round_id"], as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "volume_contracts"})
    )


def price_impact(frames: SessionFrames) -> pd.DataFrame:
    trades = frames.trades.copy()
    if trades.empty:
        return pd.DataFrame(columns=["trade_id", "market_id", "round_id", "price_impact"])
    trades["price_impact"] = trades["price_after"] - trades["price_before"]
    trades["abs_price_impact"] = trades["price_impact"].abs()
    return trades[["id", "market_id", "round_id", "direction", "quantity", "price_impact", "abs_price_impact"]].rename(
        columns={"id": "trade_id"}
    )


def information_revelation_correlation(frames: SessionFrames) -> pd.DataFrame:
    rounds = frames.rounds.copy()
    if rounds.empty:
        return pd.DataFrame(columns=["market_id", "corr_avg_posterior_vs_price"])
    signals = frames.signals[frames.signals["delivered"] == True].copy()  # noqa: E712
    if signals.empty:
        out = rounds[["market_id"]].drop_duplicates()
        out["corr_avg_posterior_vs_price"] = math.nan
        return out
    avg_signal = signals.groupby("round_id", as_index=False)["posterior"].mean().rename(columns={"posterior": "avg_posterior"})
    merged = rounds.merge(avg_signal, left_on="id", right_on="round_id", how="left")
    merged["avg_posterior"] = merged["avg_posterior"].astype(float)
    merged["closing_price"] = merged["closing_price"].astype(float)
    rows: list[dict[str, float | int]] = []
    for market_id, grp in merged.groupby("market_id"):
        sub = grp.dropna(subset=["avg_posterior", "closing_price"])
        corr = sub["avg_posterior"].corr(sub["closing_price"]) if len(sub) >= 2 else math.nan
        rows.append({"market_id": int(market_id), "corr_avg_posterior_vs_price": corr})
    return pd.DataFrame(rows)
