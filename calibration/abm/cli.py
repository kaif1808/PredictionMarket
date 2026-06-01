from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration.abm.config import SimConfig, apply_overrides, config_from_mapping, load_config_file
from calibration.abm.export import export_all_sessions
from calibration.abm.runner import run_abm
from calibration.abm.sim_metrics import simulation_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ABM sessions through the real Valdoria orchestrator.")
    parser.add_argument("--config", type=Path, default=None)
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
    parser.add_argument("--emit-metrics", action="store_true")
    return parser.parse_args()


def _build_config(args: argparse.Namespace) -> SimConfig:
    cfg = SimConfig().validated()
    if args.config:
        cfg = config_from_mapping(load_config_file(args.config))

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
