from __future__ import annotations

import pandas as pd

from analysis.load import SessionFrames


def price_path_deviation(frames: SessionFrames) -> pd.DataFrame:
    rounds = frames.rounds.copy()
    if rounds.empty:
        return pd.DataFrame(columns=["market_id", "round_number", "abs_deviation"])
    rounds["abs_deviation"] = (rounds["closing_price"] - rounds["bayesian_benchmark"]).abs()
    return rounds[["market_id", "round_number", "abs_deviation"]]


def round_volume(frames: SessionFrames) -> pd.DataFrame:
    if frames.trades.empty:
        return pd.DataFrame(columns=["round_id", "volume_contracts"])
    agg = frames.trades.groupby("round_id", as_index=False)["quantity"].sum()
    agg = agg.rename(columns={"quantity": "volume_contracts"})
    return agg


def treatment_panel(frames: SessionFrames) -> pd.DataFrame:
    rounds = frames.rounds.merge(
        frames.markets[["id", "market_number", "stage", "scenario_id"]],
        left_on="market_id",
        right_on="id",
        how="left",
    )
    rounds = rounds.drop(columns=["id_y"]).rename(columns={"id_x": "round_id"})
    if frames.trades.empty:
        rounds["turnover"] = 0
    else:
        turnover = frames.trades.groupby("round_id", as_index=False)["cost"].sum()
        rounds = rounds.merge(turnover, on="round_id", how="left")
        rounds = rounds.rename(columns={"cost": "turnover"}).fillna({"turnover": 0})
    rounds["abs_deviation"] = (rounds["closing_price"] - rounds["bayesian_benchmark"]).abs()
    return rounds[
        ["round_id", "market_id", "market_number", "stage", "scenario_id", "round_number", "abs_deviation", "turnover"]
    ]
