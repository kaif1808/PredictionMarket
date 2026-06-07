from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.load import load_session
from calibration.abm.config import SimConfig, apply_overrides, preset_config
from calibration.abm.export import _database_url, export_all_sessions
from calibration.abm.runner import run_abm
from calibration.abm.sim_metrics import simulation_report

PRIMARY_KEYS = [
    "trades_per_agent_round",
    "quantity_per_agent_round",
    "median_order_size",
    "sell_share",
    "negative_cost_share",
]


@dataclass(frozen=True)
class ReferenceTargets:
    trades_per_agent_round: float
    quantity_per_agent_round: float
    median_order_size: float
    q25_order_size: float
    q75_order_size: float
    sell_share: float
    negative_cost_share: float
    non_empty_markets_per_session_min: int
    non_practice_trade_count: int
    export_alignment_rows: int


@dataclass(frozen=True)
class CandidateResult:
    params: dict[str, Any]
    metrics: dict[str, float]
    ratios: dict[str, float]
    primary_gate: dict[str, bool]
    score: float
    gate_pass: bool
    sim_report: dict[str, Any]


def _load_reference_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(ROOT / "experiment_2" / "trades.csv")
    rounds = pd.read_csv(ROOT / "experiment_2" / "rounds.csv")
    markets = pd.read_csv(ROOT / "experiment_2" / "markets.csv")
    sessions = pd.read_csv(ROOT / "experiment_2" / "sessions.csv")

    merged = trades.merge(rounds[["id", "market_id", "round_number"]], left_on="round_id", right_on="id", suffixes=("", "_r"))
    merged = merged.drop(columns=["id_r"])
    merged = merged.merge(markets[["id", "session_id", "market_number", "is_practice"]], left_on="market_id", right_on="id", suffixes=("", "_m"))
    merged = merged.drop(columns=["id_m"])
    non_practice = merged[~merged["is_practice"].astype(bool)].copy()
    return non_practice, rounds, markets, sessions


def _agent_round_panel(
    *,
    trades: pd.DataFrame,
    rounds: pd.DataFrame,
    markets: pd.DataFrame,
    participants: list[str],
) -> pd.DataFrame:
    m_np = markets[~markets["is_practice"].astype(bool)][["id", "session_id"]].rename(columns={"id": "market_id"})
    r_np = rounds.merge(m_np, on="market_id", how="inner")[["id", "market_id", "session_id", "round_number"]].rename(columns={"id": "round_id"})

    base_rows: list[dict[str, Any]] = []
    for row in r_np.itertuples(index=False):
        for pid in participants:
            base_rows.append(
                {
                    "session_id": int(row.session_id),
                    "market_id": int(row.market_id),
                    "round_number": int(row.round_number),
                    "participant_id": pid,
                }
            )
    base = pd.DataFrame(base_rows)

    grouped = (
        trades.groupby(["session_id", "market_id", "round_number", "participant_id"], as_index=False)
        .agg(trade_count=("id", "size"), quantity_total=("quantity", "sum"))
    )
    panel = base.merge(grouped, on=["session_id", "market_id", "round_number", "participant_id"], how="left")
    panel["trade_count"] = panel["trade_count"].fillna(0)
    panel["quantity_total"] = panel["quantity_total"].fillna(0)
    return panel


def _crosscheck_export_alignment(non_practice: pd.DataFrame) -> int:
    exp_trade_ids = set(int(x) for x in non_practice["id"].tolist())
    export_trade_ids: set[int] = set()
    total_rows = 0
    for name in ["market_1_trades.csv", "market_2_trades.csv", "market_3_trades.csv"]:
        df = pd.read_csv(ROOT / "export_1" / name)
        total_rows += len(df)
        export_trade_ids.update(int(x) for x in df["trade_id"].tolist())
    # Guard: warn rather than raise — export_1 provenance may differ from experiment_2
    if len(exp_trade_ids) != total_rows:
        print(
            f"[WARN] reference/export row count mismatch: "
            f"experiment_2={len(exp_trade_ids)} export_1={total_rows}"
        )
    elif exp_trade_ids != export_trade_ids:
        diff_a = len(exp_trade_ids - export_trade_ids)
        diff_b = len(export_trade_ids - exp_trade_ids)
        print(
            f"[WARN] reference/export trade-id mismatch: "
            f"missing_in_export={diff_a} extra_in_export={diff_b}"
        )
    return total_rows


def extract_reference_targets() -> ReferenceTargets:
    non_practice, rounds, markets, _sessions = _load_reference_frames()
    alignment_rows = _crosscheck_export_alignment(non_practice)

    participants = sorted(non_practice["participant_id"].dropna().astype(str).unique().tolist())
    panel = _agent_round_panel(trades=non_practice, rounds=rounds, markets=markets, participants=participants)

    sell_share = float((non_practice["direction"] == "sell").mean()) if "sell" in set(non_practice["direction"]) else float((non_practice["cost"] < 0).mean())
    active_markets = (
        non_practice.groupby(["session_id", "market_number"], as_index=False)
        .size()
        .rename(columns={"size": "trade_count"})
    )
    markets_per_session = active_markets[active_markets["trade_count"] > 0].groupby("session_id")["market_number"].nunique()

    return ReferenceTargets(
        trades_per_agent_round=float(panel["trade_count"].mean()),
        quantity_per_agent_round=float(panel["quantity_total"].mean()),
        median_order_size=float(non_practice["quantity"].median()),
        q25_order_size=float(non_practice["quantity"].quantile(0.25)),
        q75_order_size=float(non_practice["quantity"].quantile(0.75)),
        sell_share=float(sell_share),
        negative_cost_share=float((non_practice["cost"] < 0).mean()),
        non_empty_markets_per_session_min=int(markets_per_session.min()),
        non_practice_trade_count=int(len(non_practice)),
        export_alignment_rows=int(alignment_rows),
    )


def _session_primary_metrics(session_id: int, database_url: str) -> dict[str, float]:
    with _database_url(database_url):
        frames = load_session(session_id)

    markets = frames.markets.copy()
    rounds = frames.rounds.copy()
    trades = frames.trades.copy()

    non_practice_market_ids = set(markets.loc[~markets["is_practice"].astype(bool), "id"].astype(int).tolist())
    rounds_np = rounds[rounds["market_id"].isin(non_practice_market_ids)].copy()
    trades_np = trades[trades["market_id"].isin(non_practice_market_ids)].copy()
    roles_np = frames.market_roles[frames.market_roles["market_id"].isin(non_practice_market_ids)].copy()

    participants = sorted(roles_np["participant_id"].astype(str).unique().tolist())
    if trades_np.empty:
        sell_share = 0.0
        neg_share = 0.0
        med_order = 0.0
        q25_order = 0.0
        q75_order = 0.0
    else:
        sell_share = float((trades_np["cost"].astype(float) < 0).mean())
        neg_share = float((trades_np["cost"].astype(float) < 0).mean())
        med_order = float(trades_np["quantity"].astype(float).median())
        q25_order = float(trades_np["quantity"].astype(float).quantile(0.25))
        q75_order = float(trades_np["quantity"].astype(float).quantile(0.75))

    rounds_ref = rounds_np[["id", "market_id", "round_number"]].rename(columns={"id": "round_id"})
    markets_ref = markets[["id", "session_id", "is_practice"]].rename(columns={"id": "market_id"})
    trades_ref = trades_np.merge(rounds_ref, on=["round_id", "market_id"], how="left")
    trades_ref = trades_ref.merge(markets_ref[["market_id", "session_id"]], on="market_id", how="left")
    trades_ref = trades_ref.rename(columns={"id": "id"})

    panel = _agent_round_panel(trades=trades_ref, rounds=rounds_np, markets=markets, participants=participants)

    active_markets = (
        trades_ref.groupby(["session_id", "market_id"], as_index=False)
        .size()
        .rename(columns={"size": "trade_count"})
    )
    markets_per_session = active_markets[active_markets["trade_count"] > 0].groupby("session_id")["market_id"].nunique()
    non_empty_min = int(markets_per_session.min()) if not markets_per_session.empty else 0

    return {
        "trades_per_agent_round": float(panel["trade_count"].mean()) if not panel.empty else 0.0,
        "quantity_per_agent_round": float(panel["quantity_total"].mean()) if not panel.empty else 0.0,
        "median_order_size": med_order,
        "q25_order_size": q25_order,
        "q75_order_size": q75_order,
        "sell_share": sell_share,
        "negative_cost_share": neg_share,
        "non_empty_markets_per_session_min": float(non_empty_min),
        "non_practice_trade_count": float(len(trades_np)),
    }


def _ratio(modeled: float, reference: float) -> float:
    if reference == 0:
        return float("inf") if modeled > 0 else 1.0
    return modeled / reference


def score_candidate(*, config: SimConfig, reference: ReferenceTargets) -> CandidateResult:
    run_result = run_abm(config)
    export_all_sessions(
        session_ids=run_result.session_ids,
        outdir=config.outdir,
        database_url=run_result.database_url,
    )

    per_session_metrics = [_session_primary_metrics(sid, run_result.database_url) for sid in run_result.session_ids]
    modeled: dict[str, float] = {}
    for key in [
        "trades_per_agent_round",
        "quantity_per_agent_round",
        "median_order_size",
        "q25_order_size",
        "q75_order_size",
        "sell_share",
        "negative_cost_share",
        "non_empty_markets_per_session_min",
        "non_practice_trade_count",
    ]:
        vals = [row[key] for row in per_session_metrics]
        modeled[key] = float(sum(vals) / len(vals)) if vals else 0.0

    ratios = {key: _ratio(modeled[key], float(getattr(reference, key))) for key in PRIMARY_KEYS}
    gate = {key: (0.5 <= ratios[key] <= 1.5) for key in PRIMARY_KEYS}
    gate["all_four_markets_active"] = modeled["non_empty_markets_per_session_min"] >= 4.0

    score = float(sum(abs(math.log(max(1e-9, ratios[key]))) for key in PRIMARY_KEYS))
    sim_report = simulation_report(session_ids=run_result.session_ids, database_url=run_result.database_url)

    params = {
        "intensity_mode": config.intensity_mode,
        "event_intensity": config.event_intensity,
        "lambda_base": config.lambda_base,
        "edge_gain": config.edge_gain,
        "edge_exp": config.edge_exp,
        "vol_gain": config.vol_gain,
        "vol_exp": config.vol_exp,
        "vol_ema_alpha": config.vol_ema_alpha,
        "vol_ref": config.vol_ref,
        "lambda_min": config.lambda_min,
        "lambda_max": config.lambda_max,
        "sell_propensity": config.sell_propensity,
        "order_size_dist": config.order_size_dist,
        "edge_threshold": config.edge_threshold,
        "ra_mean": config.ra_mean,
        "ra_sd": config.ra_sd,
        "ra_lo": config.ra_lo,
        "ra_hi": config.ra_hi,
        "seed": config.seed,
        "subject_count": config.subject_count,
        "treated_count": config.treated_count,
        "b": config.b,
    }

    return CandidateResult(
        params=params,
        metrics=modeled,
        ratios=ratios,
        primary_gate=gate,
        score=score,
        gate_pass=all(gate.values()),
        sim_report=sim_report,
    )


def _candidate_space(rng: random.Random, base: SimConfig, n: int) -> list[SimConfig]:
    order_specs = [
        "geometric:p=0.62,tail=0.25",
        "geometric:p=0.68,tail=0.35",
        "geometric:p=0.74,tail=0.45",
        "powerlaw:alpha=1.5",
    ]
    out: list[SimConfig] = [base]
    for idx in range(max(0, n - 1)):
        out.append(
            apply_overrides(
                base,
                {
                    "intensity_mode": "state_hybrid",
                    "lambda_base": round(rng.uniform(0.45, 1.8), 4),
                    "edge_gain": round(rng.uniform(0.25, 2.5), 4),
                    "edge_exp": round(rng.uniform(0.65, 2.2), 4),
                    "vol_gain": round(rng.uniform(0.2, 2.2), 4),
                    "vol_exp": round(rng.uniform(0.65, 2.2), 4),
                    "vol_ema_alpha": round(rng.uniform(0.05, 0.55), 4),
                    "vol_ref": round(rng.uniform(0.01, 0.12), 4),
                    "lambda_min": round(rng.uniform(0.01, 0.35), 4),
                    "lambda_max": round(rng.uniform(1.2, 6.5), 4),
                    "sell_propensity": round(rng.uniform(0.20, 0.85), 4),
                    "edge_threshold": round(rng.uniform(0.01, 0.055), 4),
                    "ra_mean": round(rng.uniform(0.22, 0.72), 4),
                    "ra_sd": round(rng.uniform(0.05, 0.28), 4),
                    "order_size_dist": order_specs[idx % len(order_specs)],
                    "seed": base.seed + idx + 1,
                },
            )
        )
    return out


def _build_leaderboard(results: list[CandidateResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for res in results:
        rows.append(
            {
                **res.params,
                "score": res.score,
                "gate_pass": res.gate_pass,
                **{f"ratio_{k}": v for k, v in res.ratios.items()},
                **{f"gate_{k}": v for k, v in res.primary_gate.items()},
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["gate_pass", "score"], ascending=[False, True]).reset_index(drop=True)


def run_calibration(*, config: SimConfig, outdir: Path, sweep: int, seed: int) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    reference = extract_reference_targets()
    candidates = _candidate_space(random.Random(seed), config, max(1, sweep))

    results: list[CandidateResult] = []
    for candidate in candidates:
        result = score_candidate(config=candidate, reference=reference)
        results.append(result)

    leaderboard = _build_leaderboard(results)
    leaderboard_path = outdir / "leaderboard.csv"
    leaderboard.to_csv(leaderboard_path, index=False)

    best = results[0]
    for result in results[1:]:
        if (result.gate_pass and not best.gate_pass) or (
            result.gate_pass == best.gate_pass and result.score < best.score
        ):
            best = result

    chosen_path = outdir / "chosen_params.json"
    chosen_path.write_text(json.dumps(best.params, indent=2, sort_keys=True) + "\n")

    comparison = {
        "reference": asdict(reference),
        "modeled": best.metrics,
        "ratios": best.ratios,
        "primary_gate": best.primary_gate,
        "gate_pass": best.gate_pass,
        "score": best.score,
        "simulation_report": best.sim_report,
    }
    compare_path = outdir / "abm_vs_reference.json"
    compare_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")

    return {
        "leaderboard_path": str(leaderboard_path),
        "chosen_params_path": str(chosen_path),
        "comparison_path": str(compare_path),
        "candidates": len(results),
        "best_gate_pass": best.gate_pass,
        "best_score": best.score,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate ABM continuous-time settings against experiment_1/export_1.")
    parser.add_argument("--extract-only", action="store_true", help="Only extract and print reference targets")
    parser.add_argument("--config", type=str, default="validation", help="Preset config name (validation|production)")
    parser.add_argument("--sweep", type=int, default=24, help="Number of candidate configs to evaluate")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", type=Path, default=Path("calibration/abm/output/calibration"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    targets = extract_reference_targets()
    if args.extract_only:
        print(json.dumps(asdict(targets), indent=2, sort_keys=True))
        return

    config = preset_config(args.config)
    result = run_calibration(config=config, outdir=args.outdir, sweep=args.sweep, seed=args.seed)
    payload = {
        "config": args.config,
        "reference": asdict(targets),
        "result": result,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
