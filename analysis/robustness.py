from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.formula.api as smf

from analysis.load import SessionFrames
from analysis.metrics import treatment_panel


def _balance_position_index(interim_balances: list[float]) -> float:
    """Leader-board concentration proxy in [0, 0.25].

    0 implies perfectly equal balances. Larger values imply concentrated
    interim balance positions (stronger tournament pressure).
    """
    if not interim_balances:
        return 0.0
    n = len(interim_balances)
    ranks = pd.Series(interim_balances).rank(method="average", ascending=False)
    percentiles = (ranks - 1) / max(n - 1, 1)
    return float(((percentiles - 0.5) ** 2).mean())


def add_cumulative_interim_balance_position(frames: SessionFrames) -> pd.DataFrame:
    panel = treatment_panel(frames).copy()
    if panel.empty:
        panel["cumulative_interim_balance_position"] = []
        return panel

    trades = frames.trades.copy()
    market_roles = frames.market_roles.copy()
    if trades.empty:
        panel["cumulative_interim_balance_position"] = 0.0
        return panel

    round_lookup = panel.set_index("round_id")[["market_id", "round_number", "abs_deviation", "turnover", "stage", "scenario_id"]]
    close_price_lookup = frames.rounds.set_index("id")["closing_price"].to_dict()

    position_by_round: dict[int, float] = {}
    for round_id, row in round_lookup.iterrows():
        market_id = int(row["market_id"])
        round_number = int(row["round_number"])
        close_price = float(close_price_lookup.get(round_id, 0.5) or 0.5)

        participants = market_roles[market_roles["market_id"] == market_id][["participant_id", "endowment_tokens"]]
        interim_balances: list[float] = []
        for _, p in participants.iterrows():
            pid = p["participant_id"]
            endowment = float(p["endowment_tokens"])
            ptrades = trades[
                (trades["market_id"] == market_id)
                & (trades["participant_id"] == pid)
                & (trades["round_id"].map(lambda rid: int(round_lookup.loc[rid, "round_number"]) <= round_number))
            ]
            spent = float(ptrades["cost"].sum()) if len(ptrades) else 0.0
            yes_held = float(ptrades[ptrades["direction"] == "yes"]["quantity"].sum()) if len(ptrades) else 0.0
            no_held = float(ptrades[ptrades["direction"] == "no"]["quantity"].sum()) if len(ptrades) else 0.0
            cash = endowment - spent
            marked = cash + yes_held * close_price + no_held * (1.0 - close_price)
            interim_balances.append(marked)

        position_by_round[int(round_id)] = _balance_position_index(interim_balances)

    panel["cumulative_interim_balance_position"] = panel["round_id"].map(position_by_round).fillna(0.0)
    return panel


@dataclass
class RobustnessResult:
    regression_table: pd.DataFrame
    model_summary_text: str
    panel: pd.DataFrame


def tournament_effect_robustness(frames: SessionFrames) -> RobustnessResult:
    panel = add_cumulative_interim_balance_position(frames)
    if panel.empty:
        return RobustnessResult(
            regression_table=pd.DataFrame(
                columns=[
                    "term",
                    "coef",
                    "std_err_hc3",
                    "p_value",
                ]
            ),
            model_summary_text="No data available.",
            panel=panel,
        )

    # Small pilot samples can produce rank-deficient designs. Use a compact
    # fallback formula if needed to keep the robustness check executable.
    formula = "abs_deviation ~ cumulative_interim_balance_position + C(stage) + C(round_number)"
    try:
        model = smf.ols(formula=formula, data=panel).fit(cov_type="HC3")
    except Exception:
        formula = "abs_deviation ~ cumulative_interim_balance_position"
        model = smf.ols(formula=formula, data=panel).fit(cov_type="HC3")

    table = pd.DataFrame(
        {
            "term": model.params.index,
            "coef": model.params.values,
            "std_err_hc3": model.bse.values,
            "p_value": model.pvalues.values,
        }
    )
    try:
        summary_text = model.summary().as_text()
    except Exception:
        summary_text = (
            f"Model summary unavailable for small-sample design.\n"
            f"Formula used: {formula}\n\n"
            f"{table.to_string(index=False)}"
        )

    return RobustnessResult(
        regression_table=table,
        model_summary_text=summary_text,
        panel=panel,
    )
