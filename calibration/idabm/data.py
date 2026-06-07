"""Load experiment_2 CSVs and build per-trade feature panel."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "experiment_2"

_CSV_NAMES = [
    "trades", "rounds", "markets", "sessions",
    "market_roles", "signals", "risk_elicitations", "market_resolutions",
]


def load_raw(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(data_dir / f"{name}.csv") for name in _CSV_NAMES}


def build_trade_panel(raw: Optional[dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
    """One row per non-practice trade with all derived features."""
    if raw is None:
        raw = load_raw()

    trades = raw["trades"].copy()
    rounds = raw["rounds"].copy()
    markets = raw["markets"].copy()
    market_roles = raw["market_roles"].copy()
    signals = raw["signals"].copy()
    risk_elicitations = raw["risk_elicitations"].copy()

    # Step 1: trades → rounds
    panel = trades.merge(
        rounds[["id", "market_id", "round_number", "bayesian_benchmark", "closing_price"]].rename(
            columns={"id": "round_id"}
        ),
        on="round_id",
        how="inner",
    )

    # Step 2: → markets, filter non-practice
    panel = panel.merge(
        markets[
            ["id", "session_id", "market_number", "stage", "true_probability", "b_parameter", "is_practice"]
        ].rename(columns={"id": "market_id"}),
        on="market_id",
        how="inner",
    )
    panel = panel[~panel["is_practice"].astype(bool)].copy()

    # Step 3: → market_roles
    mr = market_roles.copy()
    mr["is_informed"] = (mr["role_tier"] == "informed").astype(int)
    mr["is_whale"] = (mr["endowment_tokens"] >= 400).astype(int)
    panel = panel.merge(
        mr[["market_id", "participant_id", "is_informed", "is_whale", "starting_balance"]],
        on=["market_id", "participant_id"],
        how="left",
    )

    # Step 4: → signals (left join — not all trades have a signal for the round)
    sig = signals[["round_id", "participant_id", "posterior", "signal_value", "theta", "delivered"]].copy()
    panel = panel.merge(sig, on=["round_id", "participant_id"], how="left")
    panel["delivered"] = panel["delivered"].fillna(False).astype(bool)
    panel["has_posterior"] = panel["delivered"].astype(int)
    panel["perceived_posterior"] = np.where(
        panel["delivered"] & panel["posterior"].notna(),
        panel["posterior"].astype(float),
        0.5,
    )

    # Step 5: → risk_elicitations (holt_laury_10 only)
    re = risk_elicitations[risk_elicitations["instrument"] == "holt_laury_10"].copy()
    re = re[["session_id", "participant_id", "switch_point"]].copy()

    session_medians = re.groupby("session_id")["switch_point"].median()
    global_median = float(re["switch_point"].median()) if re["switch_point"].notna().any() else 5.0

    def _impute(row: pd.Series):
        if pd.notna(row["switch_point"]):
            return row["switch_point"], False
        med = session_medians.get(row["session_id"], global_median)
        if pd.isna(med):
            med = global_median
        return med, True

    imputed = re.apply(_impute, axis=1).tolist()
    re["switch_point_filled"] = [x[0] for x in imputed]
    re["switch_point_imputed"] = [x[1] for x in imputed]

    panel = panel.merge(
        re[["session_id", "participant_id", "switch_point_filled", "switch_point_imputed"]].rename(
            columns={"switch_point_filled": "switch_point"}
        ),
        on=["session_id", "participant_id"],
        how="left",
    )
    panel["switch_point_imputed"] = panel["switch_point_imputed"].fillna(True)
    panel["switch_point"] = panel["switch_point"].fillna(global_median)

    # Derived columns
    panel["perceived_edge"] = panel["perceived_posterior"] - panel["price_before"].astype(float)
    # cost=0 treated as buy (near-zero-price; sell at 0 is not economically meaningful)
    _cost_buy = panel["cost"].astype(float) >= 0
    panel["signed_quantity"] = panel["quantity"].astype(float) * np.where(_cost_buy, 1.0, -1.0)
    panel["yes_exposure_up"] = (
        ((panel["direction"] == "yes") & _cost_buy)
        | ((panel["direction"] == "no") & ~_cost_buy)
    ).astype(int)

    # q_before: market-level state before each trade (shared across all participants)
    panel = panel.sort_values(["market_id", "executed_at"]).copy()
    panel["q_yes_before"] = (
        panel.groupby("market_id")["q_yes_after"].transform(lambda x: x.shift(1).fillna(0.0))
    )
    panel["q_no_before"] = (
        panel.groupby("market_id")["q_no_after"].transform(lambda x: x.shift(1).fillna(0.0))
    )

    # balance_at_trade: per (market, participant), balance before this trade
    panel = panel.sort_values(["market_id", "participant_id", "executed_at"]).copy()
    panel["_prior_cost"] = panel.groupby(["market_id", "participant_id"])["cost"].transform(
        lambda x: x.astype(float).shift(1).fillna(0.0).cumsum()
    )
    panel["balance_at_trade"] = panel["starting_balance"].astype(float) - panel["_prior_cost"]
    panel = panel.drop(columns=["_prior_cost"])

    return panel.reset_index(drop=True)


def build_market_deviation(raw: Optional[dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
    """Per non-practice market: abs_deviation_benchmark = |last-round closing_price − bayesian_benchmark|."""
    if raw is None:
        raw = load_raw()

    rounds = raw["rounds"].copy()
    markets = raw["markets"].copy()

    non_practice_ids = set(markets.loc[~markets["is_practice"].astype(bool), "id"].tolist())
    rounds_np = rounds[rounds["market_id"].isin(non_practice_ids)].copy()

    last_rounds = (
        rounds_np.sort_values("round_number")
        .groupby("market_id")
        .last()
        .reset_index()[["market_id", "closing_price", "bayesian_benchmark"]]
    )
    last_rounds["abs_deviation_benchmark"] = (
        last_rounds["closing_price"].astype(float) - last_rounds["bayesian_benchmark"].astype(float)
    ).abs()

    result = last_rounds.merge(
        markets[["id", "session_id", "market_number", "stage", "true_probability"]].rename(
            columns={"id": "market_id"}
        ),
        on="market_id",
        how="left",
    )
    return result[["market_id", "session_id", "market_number", "stage", "true_probability", "abs_deviation_benchmark"]]
