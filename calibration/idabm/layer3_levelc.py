"""Layer 3C — per-participant CRRA MLE via scipy."""
from __future__ import annotations

import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.lmsr import cost as lmsr_cost, price as lmsr_price

_MIN_TRADES = 8
_RHO_BOUNDS = (0.05, 5.0)
_DEFAULT_RHO = 1.0
_DEFAULT_SIGMA = 5.0


def crra_u(w: float, rho: float) -> float:
    """CRRA utility. Returns -1e10 for non-positive wealth."""
    if w <= 1e-6:
        return -1e10
    if abs(rho - 1.0) < 1e-8:
        return math.log(w)
    return (w ** (1.0 - rho)) / (1.0 - rho)


def optimal_q_crra(
    p: float,
    W: float,
    q_yes: float,
    q_no: float,
    yes_up: int,
    b: float,
    rho: float,
    max_q: float = 500.0,
) -> float:
    """
    Find q* maximising EU = p·u(W-C+q) + (1-p)·u(W-C) for YES-up direction,
    or p·u(W-C) + (1-p)·u(W-C+q) for YES-down direction.
    Falls back to closed-form if scipy fails.
    """
    p = float(np.clip(p, 1e-6, 1.0 - 1e-6))
    W = max(float(W), 1e-6)
    effective_max = min(max_q, W * 0.99)
    if effective_max < 0.01:
        return 0.01

    def neg_eu(q: float) -> float:
        q = max(q, 1e-4)
        try:
            if yes_up == 1:
                c = lmsr_cost(q_yes, q_no, q, 0.0, b)
                w_win = W - c + q
                w_lose = W - c
            else:
                c = lmsr_cost(q_yes, q_no, 0.0, q, b)
                w_win = W - c
                w_lose = W - c + q
        except Exception:
            return 1e10
        if w_win <= 1e-6 or w_lose <= 1e-6:
            return 1e10
        return -(p * crra_u(w_win, rho) + (1.0 - p) * crra_u(w_lose, rho))

    try:
        from scipy.optimize import minimize_scalar
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = minimize_scalar(neg_eu, bounds=(1e-4, effective_max), method="bounded")
        if res.success:
            return max(1e-4, float(res.x))
    except Exception:
        pass

    # Closed-form approximation
    cur_price = lmsr_price(q_yes, q_no, b)
    if yes_up == 1:
        edge = p - cur_price
    else:
        edge = (1.0 - p) - (1.0 - cur_price)
    denom = max(rho, 0.05) * cur_price * (1.0 - cur_price)
    q_approx = edge * W / denom if denom > 1e-8 else 0.0
    return max(1e-4, min(q_approx, effective_max))


def _nll(params: np.ndarray, trade_rows: list[tuple]) -> float:
    rho = float(np.clip(params[0], *_RHO_BOUNDS))
    log_sigma = float(params[1])
    sigma = math.exp(log_sigma)

    nll = 0.0
    for p, W, q_yes, q_no, yes_up, q_obs, b in trade_rows:
        if W <= 0 or q_obs <= 0:
            continue
        q_star = optimal_q_crra(p, W, q_yes, q_no, yes_up, b, rho)
        resid = q_obs - q_star
        nll += 0.5 * math.log(2 * math.pi * sigma ** 2) + resid ** 2 / (2.0 * sigma ** 2)
    return nll


@dataclass
class CRRAParams:
    participant_id: str
    rho: float
    sigma: float
    n_trades: int
    converged: bool
    fallback: bool
    fallback_reason: str = ""


def fit_crra_participant(
    pid: str,
    trades: pd.DataFrame,
    b: float = 36.0,
) -> Optional[CRRAParams]:
    """MLE CRRA fit for one participant. Returns None if < _MIN_TRADES usable trades."""
    needed = ["perceived_posterior", "balance_at_trade", "q_yes_before", "q_no_before", "yes_exposure_up", "quantity"]
    df = trades[needed].dropna().copy()
    df = df[(df["balance_at_trade"] > 0) & (df["quantity"] > 0)].copy()
    df = df[df["perceived_posterior"].between(1e-6, 1 - 1e-6)].copy()

    if len(df) < _MIN_TRADES:
        return CRRAParams(
            participant_id=pid,
            rho=float("nan"),
            sigma=float("nan"),
            n_trades=len(df),
            converged=False,
            fallback=True,
            fallback_reason="too_few_trades",
        )

    trade_rows = [
        (
            float(row["perceived_posterior"]),
            float(row["balance_at_trade"]),
            float(row["q_yes_before"]),
            float(row["q_no_before"]),
            int(row["yes_exposure_up"]),
            float(row["quantity"]),
            b,
        )
        for _, row in df.iterrows()
    ]

    x0 = np.array([_DEFAULT_RHO, math.log(_DEFAULT_SIGMA)])
    bounds = [list(_RHO_BOUNDS), [-5.0, 5.0]]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = minimize(
                _nll,
                x0=x0,
                args=(trade_rows,),
                bounds=bounds,
                method="L-BFGS-B",
                options={"maxiter": 300, "ftol": 1e-8},
            )
        converged = result.success and result.fun < 1e10
        rho = float(np.clip(result.x[0], *_RHO_BOUNDS)) if converged else float("nan")
        sigma = math.exp(float(result.x[1])) if converged else float("nan")
    except Exception:
        converged = False
        rho, sigma = float("nan"), float("nan")

    return CRRAParams(
        participant_id=pid,
        rho=rho,
        sigma=sigma,
        n_trades=len(df),
        converged=converged,
        fallback=not converged,
        fallback_reason="" if converged else "non_convergence",
    )


def fit_crra_all(panel: pd.DataFrame, b: float = 36.0) -> dict[str, Any]:
    """
    Fit CRRA for all participants. Apply session-mean → global-mean fallback.
    Returns params dict and fallback_count.
    """
    all_params: dict[str, CRRAParams] = {}

    for pid, grp in panel.groupby("participant_id"):
        p = fit_crra_participant(str(pid), grp, b=b)
        if p is not None:
            all_params[str(pid)] = p

    # Session-mean fallback
    session_rhos: dict[int, list[float]] = {}
    for pid, p in all_params.items():
        if p.converged and not math.isnan(p.rho):
            sids = panel.loc[panel["participant_id"] == pid, "session_id"].unique().tolist()
            for sid in sids:
                session_rhos.setdefault(int(sid), []).append(p.rho)

    session_mean_rho = {sid: float(np.mean(rhos)) for sid, rhos in session_rhos.items()}
    global_rhos = [r for rhos in session_rhos.values() for r in rhos]
    global_mean_rho = float(np.mean(global_rhos)) if global_rhos else _DEFAULT_RHO

    fallback_count = 0
    for pid, p in all_params.items():
        if p.fallback or math.isnan(p.rho):
            fallback_count += 1
            sids = panel.loc[panel["participant_id"] == pid, "session_id"].unique().tolist()
            sid = int(sids[0]) if sids else -1
            fallback_rho = session_mean_rho.get(sid, global_mean_rho)
            p.rho = fallback_rho
            p.sigma = _DEFAULT_SIGMA
            p.fallback = True

    return {
        "params": all_params,
        "fallback_count": fallback_count,
        "global_mean_rho": global_mean_rho,
        "session_mean_rho": session_mean_rho,
    }
