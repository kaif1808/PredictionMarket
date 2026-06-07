"""Counterfactual session generator and treatment-effect estimator."""
from __future__ import annotations

import math
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import statsmodels.api as sm
from server.bayesian import draw_signal, informed_signal_theta, update_posterior
from server.lmsr import cost as lmsr_cost, price as lmsr_price
from calibration.idabm.layer3_levelb import LevelBModels, predict_direction_prob, predict_quantity
from calibration.idabm.layer3_levelc import CRRAParams, optimal_q_crra

_B = 36.0
_N_ROUNDS = 5
_N_PARTICIPANTS = 9
_N_INFORMED = 3
_PARTICIPANTS = [f"P{i:02d}" for i in range(1, _N_PARTICIPANTS + 1)]


@dataclass
class SessionResult:
    abs_deviation_benchmark: float
    gini_cost: float
    has_informed: int
    has_whale: int
    true_probs: list[float]
    n_markets: int


def _crra_u(w: float, rho: float) -> float:
    if w <= 1e-6:
        return -1e10
    if abs(rho - 1.0) < 1e-8:
        return math.log(w)
    return (w ** (1.0 - rho)) / (1.0 - rho)


def _gini(values: list[float]) -> float:
    arr = sorted(max(float(v), 0.0) for v in values)
    n = len(arr)
    if n == 0:
        return 0.0
    total = sum(arr)
    if total == 0:
        return 0.0
    weighted = sum((i + 1) * x for i, x in enumerate(arr))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def _make_participant_row(
    pid: str,
    q_yes: float,
    q_no: float,
    posterior: float,
    balance: float,
    is_informed: int,
    is_whale: int,
    switch_point: float,
    round_number: int,
) -> pd.DataFrame:
    price_now = lmsr_price(q_yes, q_no, _B)
    return pd.DataFrame(
        [
            {
                "perceived_edge": posterior - price_now,
                "balance_at_trade": balance,
                "is_informed": is_informed,
                "is_whale": is_whale,
                "switch_point": switch_point,
                "round_number": round_number,
                "perceived_posterior": posterior,
                "q_yes_before": q_yes,
                "q_no_before": q_no,
                "yes_exposure_up": 0,  # placeholder
            }
        ]
    )


def generate_session(
    true_probs: list[float],
    models_b: LevelBModels,
    params_c: dict[str, CRRAParams],
    rng: np.random.Generator,
    n_informed: int = _N_INFORMED,
    has_whale: bool = True,
    quantity_source: str = "levelb",
) -> SessionResult:
    """
    Simulate one synthetic session with given scenario (true_prob per market).
    quantity_source: "levelb" or "levelc"
    """
    participants = _PARTICIPANTS[:_N_PARTICIPANTS]
    informed_ids = set(participants[:n_informed])
    whale_id = participants[0] if has_whale else None

    endowments = {pid: 400.0 if pid == whale_id else 100.0 for pid in participants}
    switch_points = {pid: float(rng.integers(3, 9)) for pid in participants}

    global_rho = float(np.mean([p.rho for p in params_c.values() if not math.isnan(p.rho)])) if params_c else 1.0

    market_deviations: list[float] = []
    total_costs: dict[str, list[float]] = {pid: [] for pid in participants}

    for market_idx, tp in enumerate(true_probs):
        # Resolve outcome
        true_outcome = int(rng.random() < tp)
        theta = informed_signal_theta(tp)

        # Starting balances for this market (carry over from prior, or start fresh)
        balances = dict(endowments)  # simplified: reset to endowment each market

        q_yes, q_no = 0.0, 0.0
        posteriors = {pid: 0.5 for pid in participants}

        round_closing_prices: list[float] = []
        round_benchmarks: list[float] = []

        for round_num in range(1, _N_ROUNDS + 1):
            # Update informed beliefs with new signal
            for pid in informed_ids:
                if tp > 0:
                    sig_rng = np.random.default_rng(int(rng.integers(0, 2**31)))
                    import random as _random
                    _rng_compat = _random.Random(int(sig_rng.integers(0, 2**31)))
                    sv = draw_signal(true_outcome=true_outcome, theta=theta, rng=_rng_compat)
                    posteriors[pid] = update_posterior(
                        prior=posteriors[pid], signal=sv, theta=theta
                    )

            # Each participant trades once per round (in random order)
            pid_order = list(participants)
            rng.shuffle(pid_order)

            for pid in pid_order:
                posterior = posteriors[pid]
                balance = balances[pid]
                is_inf = 1 if pid in informed_ids else 0
                is_wh = 1 if pid == whale_id else 0
                sp = switch_points[pid]

                if balance <= 1.0:
                    continue

                row_df = _make_participant_row(
                    pid, q_yes, q_no, posterior, balance, is_inf, is_wh, sp, round_num
                )

                # Direction from Level B
                dir_prob = float(predict_direction_prob(models_b.direction_model, row_df)[0])
                yes_up = 1 if rng.random() < dir_prob else 0
                row_df["yes_exposure_up"] = yes_up

                # Quantity
                if quantity_source == "levelc":
                    crra = params_c.get(pid)
                    rho = crra.rho if crra and not math.isnan(crra.rho) else global_rho
                    qty = optimal_q_crra(
                        posterior, balance, q_yes, q_no, yes_up, _B, rho
                    )
                    qty = max(1.0, min(qty, balance * 0.9))
                else:
                    qty = float(predict_quantity(models_b.quantity_model, row_df)[0])
                    qty = max(1.0, min(qty, balance * 0.9))

                qty = round(qty)
                if qty < 1:
                    continue

                # Execute trade
                try:
                    if yes_up == 1:
                        c = lmsr_cost(q_yes, q_no, qty, 0.0, _B)
                        if c > balance:
                            continue
                        q_yes += qty
                        balances[pid] -= c
                        total_costs[pid].append(c)
                    else:
                        c = lmsr_cost(q_yes, q_no, 0.0, qty, _B)
                        if c > balance:
                            continue
                        q_no += qty
                        balances[pid] -= c
                        total_costs[pid].append(c)
                except Exception:
                    continue

            round_closing_prices.append(lmsr_price(q_yes, q_no, _B))

            # Bayesian benchmark (all informed signals aggregated)
            from server.bayesian import benchmark_price
            all_sigs: list[tuple[str, float]] = []
            round_benchmarks.append(float(np.mean(list(posteriors[pid] for pid in informed_ids))) if informed_ids else 0.5)

        # Market deviation: |last closing price - benchmark|
        last_price = round_closing_prices[-1] if round_closing_prices else 0.5
        last_bench = round_benchmarks[-1] if round_benchmarks else tp
        market_deviations.append(abs(last_price - last_bench))

    abs_dev = float(np.mean(market_deviations)) if market_deviations else float("nan")
    all_costs = [c for cs in total_costs.values() for c in cs]
    gini = _gini([abs(c) for c in all_costs])

    return SessionResult(
        abs_deviation_benchmark=abs_dev,
        gini_cost=gini,
        has_informed=int(n_informed > 0),
        has_whale=int(has_whale),
        true_probs=list(true_probs),
        n_markets=len(true_probs),
    )


def estimate_treatment_effect(results: list[SessionResult]) -> dict[str, Any]:
    """OLS: abs_deviation_benchmark ~ has_informed + has_whale."""
    df = pd.DataFrame(
        [
            {
                "abs_deviation_benchmark": r.abs_deviation_benchmark,
                "has_informed": r.has_informed,
                "has_whale": r.has_whale,
            }
            for r in results
            if not math.isnan(r.abs_deviation_benchmark)
        ]
    )
    if df.empty or len(df) < 3:
        return {"error": "insufficient data"}

    X = sm.add_constant(df[["has_informed", "has_whale"]])
    y = df["abs_deviation_benchmark"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ols = sm.OLS(y, X).fit()

    return {
        "coef_has_informed": float(ols.params.get("has_informed", float("nan"))),
        "coef_has_whale": float(ols.params.get("has_whale", float("nan"))),
        "coef_const": float(ols.params.get("const", float("nan"))),
        "pval_has_informed": float(ols.pvalues.get("has_informed", float("nan"))),
        "pval_has_whale": float(ols.pvalues.get("has_whale", float("nan"))),
        "r_squared": float(ols.rsquared),
        "n_obs": len(df),
        "has_informed": float(ols.params.get("has_informed", float("nan"))),
        "has_whale": float(ols.params.get("has_whale", float("nan"))),
    }


_REAL_ORDER = [0.5, 0.75, 0.25, 0.65]  # stages 1-4 for scenario_order="C,A,B,D"


def run_counterfactual(
    experiment: str,
    iters: int,
    models_b: LevelBModels,
    params_c: dict[str, CRRAParams],
    empirical_effect: Optional[float],
    quantity_source: str = "levelb",
    seed: int = 42,
) -> dict[str, Any]:
    """
    Run counterfactual experiment.
    experiment: "order" | "scenario" | "full"
    Returns effect distribution and OLS estimates.
    """
    rng = np.random.default_rng(seed)
    results: list[SessionResult] = []

    for i in range(iters):
        # Vary role assignment across iterations (half with informed, half without)
        n_informed = _N_INFORMED if i % 2 == 0 else 0
        has_whale = bool(rng.random() < 0.5)

        # Scenario (true_probs per market)
        if experiment == "order":
            # Permute the fixed scenario order
            order = list(_REAL_ORDER)
            rng.shuffle(order)
            true_probs = order
        elif experiment == "scenario":
            # Randomize true_probs uniformly
            true_probs = [float(rng.uniform(0.2, 0.8)) for _ in _REAL_ORDER]
        else:  # "full"
            order = list(_REAL_ORDER)
            rng.shuffle(order)
            true_probs = [float(rng.uniform(0.2, 0.8)) for _ in order]

        result = generate_session(
            true_probs=true_probs,
            models_b=models_b,
            params_c=params_c,
            rng=rng,
            n_informed=n_informed,
            has_whale=has_whale,
            quantity_source=quantity_source,
        )
        results.append(result)

    effect = estimate_treatment_effect(results)
    devs = [r.abs_deviation_benchmark for r in results if not math.isnan(r.abs_deviation_benchmark)]

    return {
        "experiment": experiment,
        "iters": iters,
        "treatment_effect": effect,
        "deviation_mean": float(np.mean(devs)) if devs else float("nan"),
        "deviation_std": float(np.std(devs)) if devs else float("nan"),
        "empirical_abs_deviation": empirical_effect,
        "n_valid": len(devs),
    }
