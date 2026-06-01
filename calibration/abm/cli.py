from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration.abm.config import SimConfig, apply_overrides, config_from_mapping, load_config_file, preset_config
from calibration.abm.export import export_all_sessions
from calibration.abm.runner import run_abm
from calibration.abm.sim_metrics import simulation_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ABM sessions through the real Valdoria orchestrator.")
    parser.add_argument("--config", type=str, default="validation", help="Preset name (validation|production) or path to .json/.yaml")
    parser.add_argument("--rotation-id", type=int, default=None)
    parser.add_argument("--subject-count", type=int, default=None)
    parser.add_argument("--treated-count", type=int, default=None)
    parser.add_argument("--b", type=float, default=None)
    parser.add_argument("--risk-aversion", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--profile-mix", type=str, default=None)
    parser.add_argument("--num-sessions", type=int, default=None)
    parser.add_argument("--no-practice", action="store_true")
    parser.add_argument("--outdir", type=Path, default=None)
    parser.add_argument("--db-path", type=str, default=None)

    parser.add_argument("--round-duration-s", type=float, default=None)
    parser.add_argument("--intensity-mode", type=str, default=None)
    parser.add_argument("--event-intensity", type=float, default=None)
    parser.add_argument("--lambda-base", type=float, default=None)
    parser.add_argument("--edge-gain", type=float, default=None)
    parser.add_argument("--edge-exp", type=float, default=None)
    parser.add_argument("--vol-gain", type=float, default=None)
    parser.add_argument("--vol-exp", type=float, default=None)
    parser.add_argument("--vol-ema-alpha", type=float, default=None)
    parser.add_argument("--vol-ref", type=float, default=None)
    parser.add_argument("--lambda-min", type=float, default=None)
    parser.add_argument("--lambda-max", type=float, default=None)
    parser.add_argument("--order-size-dist", type=str, default=None)
    parser.add_argument("--sell-propensity", type=float, default=None)
    parser.add_argument("--edge-threshold", type=float, default=None)
    parser.add_argument("--ra-mean", type=float, default=None)
    parser.add_argument("--ra-sd", type=float, default=None)
    parser.add_argument("--ra-lo", type=float, default=None)
    parser.add_argument("--ra-hi", type=float, default=None)

    parser.add_argument("--emit-metrics", action="store_true")
    return parser.parse_args()


def _resolve_base_config(config_arg: str | None) -> SimConfig:
    if config_arg is None:
        return preset_config("validation")
    try:
        return preset_config(config_arg)
    except ValueError:
        pass

    path = Path(config_arg)
    if not path.exists():
        raise FileNotFoundError(f"config path not found: {config_arg}")
    return config_from_mapping(load_config_file(path))


def _build_config(args: argparse.Namespace) -> SimConfig:
    cfg = _resolve_base_config(args.config)

    overrides: dict[str, Any] = {
        "rotation_id": args.rotation_id,
        "subject_count": args.subject_count,
        "treated_count": args.treated_count,
        "b": args.b,
        "risk_aversion": args.risk_aversion,
        "seed": args.seed,
        "profile_mix": args.profile_mix,
        "num_sessions": args.num_sessions,
        "outdir": args.outdir,
        "db_path": args.db_path,
        "round_duration_s": args.round_duration_s,
        "intensity_mode": args.intensity_mode,
        "event_intensity": args.event_intensity,
        "lambda_base": args.lambda_base,
        "edge_gain": args.edge_gain,
        "edge_exp": args.edge_exp,
        "vol_gain": args.vol_gain,
        "vol_exp": args.vol_exp,
        "vol_ema_alpha": args.vol_ema_alpha,
        "vol_ref": args.vol_ref,
        "lambda_min": args.lambda_min,
        "lambda_max": args.lambda_max,
        "order_size_dist": args.order_size_dist,
        "sell_propensity": args.sell_propensity,
        "edge_threshold": args.edge_threshold,
        "ra_mean": args.ra_mean,
        "ra_sd": args.ra_sd,
        "ra_lo": args.ra_lo,
        "ra_hi": args.ra_hi,
    }
    if args.no_practice:
        overrides["include_practice"] = False
    return apply_overrides(cfg, overrides)


def main() -> None:
    args = _parse_args()
    config = _build_config(args)
    run_result = run_abm(config)
    written = export_all_sessions(
        session_ids=run_result.session_ids,
        outdir=config.outdir,
        database_url=run_result.database_url,
    )
    payload: dict[str, Any] = {
        "config": {
            "subject_count": config.subject_count,
            "treated_count": config.treated_count,
            "b": config.b,
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
            "order_size_dist": config.order_size_dist,
            "sell_propensity": config.sell_propensity,
            "edge_threshold": config.edge_threshold,
            "ra_mean": config.ra_mean,
            "ra_sd": config.ra_sd,
            "ra_lo": config.ra_lo,
            "ra_hi": config.ra_hi,
        },
        "session_ids": run_result.session_ids,
        "database_url": run_result.database_url,
        "db_path": run_result.db_path,
        "outdir": str(config.outdir.resolve()),
        "files_written": len(written),
    }
    if args.emit_metrics:
        payload["simulation_metrics"] = simulation_report(
            session_ids=run_result.session_ids,
            database_url=run_result.database_url,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
