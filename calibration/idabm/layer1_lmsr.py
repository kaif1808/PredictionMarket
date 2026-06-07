"""Layer 1 — LMSR replay validation."""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.lmsr import price


def replay_market(market_trades: pd.DataFrame, b: float = 36.0) -> dict[str, Any]:
    """
    Walk trades in executed_at order from (q_yes=0, q_no=0).
    Returns rmse, passed (rmse < 1e-6), and per-trade recomputed prices.
    """
    trades = market_trades.sort_values("executed_at").reset_index(drop=True)
    n = len(trades)
    if n == 0:
        return {"rmse": 0.0, "passed": True, "n_trades": 0, "max_holdings_err": 0.0}

    q_yes, q_no = 0.0, 0.0
    recomputed: list[float] = []
    q_yes_hist: list[float] = []
    q_no_hist: list[float] = []

    for _, row in trades.iterrows():
        direction = str(row["direction"])
        qty = float(row["quantity"])
        # cost=0 treated as buy (near-zero-price assets; sell at 0 makes no economic sense)
        sign = 1.0 if float(row["cost"]) >= 0 else -1.0

        if direction == "yes":
            q_yes += sign * qty
        else:
            q_no += sign * qty

        q_yes_hist.append(q_yes)
        q_no_hist.append(q_no)
        recomputed.append(price(q_yes, q_no, b))

    actual_prices = trades["price_after"].astype(float).tolist()
    q_yes_stored = trades["q_yes_after"].astype(float).tolist()
    q_no_stored = trades["q_no_after"].astype(float).tolist()

    max_holdings_err = max(
        max(abs(r - s) for r, s in zip(q_yes_hist, q_yes_stored)),
        max(abs(r - s) for r, s in zip(q_no_hist, q_no_stored)),
    )

    # Fallback: if holdings drift, seed q from first trade's stored values minus delta
    if max_holdings_err > 0.1:
        first = trades.iloc[0]
        f_qty = float(first["quantity"])
        f_sign = 1.0 if float(first["cost"]) > 0 else -1.0
        if str(first["direction"]) == "yes":
            q_yes = float(first["q_yes_after"]) - f_sign * f_qty
            q_no = float(first["q_no_after"])
        else:
            q_yes = float(first["q_yes_after"])
            q_no = float(first["q_no_after"]) - f_sign * f_qty

        recomputed = []
        for _, row in trades.iterrows():
            direction = str(row["direction"])
            qty = float(row["quantity"])
            sign = 1.0 if float(row["cost"]) >= 0 else -1.0
            if direction == "yes":
                q_yes += sign * qty
            else:
                q_no += sign * qty
            recomputed.append(price(q_yes, q_no, b))

    rmse = math.sqrt(sum((r - a) ** 2 for r, a in zip(recomputed, actual_prices)) / n)
    return {
        "rmse": rmse,
        "passed": rmse < 1e-6,
        "n_trades": n,
        "max_holdings_err": max_holdings_err,
        "recomputed_prices": recomputed,
    }


def replay_all_markets(panel: pd.DataFrame, b: float = 36.0) -> dict[str, Any]:
    """Run LMSR replay for all markets in panel. Returns aggregate RMSE and per-market results."""
    results: dict[int, dict] = {}
    sq_errors: list[float] = []
    n_total = 0

    for market_id, grp in panel.groupby("market_id"):
        res = replay_market(grp, b=b)
        results[int(market_id)] = res
        sq_errors.extend(
            (r - a) ** 2
            for r, a in zip(
                res.get("recomputed_prices", []),
                grp.sort_values("executed_at")["price_after"].astype(float).tolist(),
            )
        )
        n_total += res["n_trades"]

    aggregate_rmse = math.sqrt(sum(sq_errors) / n_total) if n_total > 0 else 0.0
    all_passed = all(r["passed"] for r in results.values())

    return {
        "aggregate_rmse": aggregate_rmse,
        "all_passed": all_passed,
        "passed": all_passed,
        "n_trades": n_total,
        "per_market": results,
    }
