from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from calibration.abm.calibrate import _session_primary_metrics
from calibration.abm.config import SimConfig, apply_overrides, config_from_mapping, load_config_file, preset_config
from calibration.abm.export import export_session_outputs
from calibration.abm.runner import run_abm
from calibration.abm.sim_metrics import simulation_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated 24-agent production ABM replications and summarize quantiles.")
    parser.add_argument("--config", type=str, default="production", help="Preset name (validation|production) or path to .json/.yaml")
    parser.add_argument("--chosen", type=Path, required=True, help="Path to chosen_params.json from calibration")
    parser.add_argument("--runs", type=int, default=10, help="Number of replications to run")
    parser.add_argument("--base-seed", type=int, default=4200, help="First seed in deterministic sequence")
    parser.add_argument("--output", type=Path, default=Path("calibration/abm/output/production_runs_24"))
    parser.add_argument(
        "--emit-full-raw",
        action="store_true",
        help="Also export full per-run raw session outputs into output/full_raw/",
    )
    return parser.parse_args()


def _resolve_base_config(config_arg: str) -> SimConfig:
    try:
        return preset_config(config_arg)
    except ValueError:
        path = Path(config_arg)
        if not path.exists():
            raise FileNotFoundError(f"config path not found: {config_arg}") from None
        return config_from_mapping(load_config_file(path))


def _normalize_numeric(value: Any) -> float:
    return float(value) if value is not None else float("nan")


def _run_once(*, config: SimConfig, full_raw_outdir: Path | None = None) -> dict[str, float]:
    run_result = run_abm(config)
    session_id = run_result.session_ids[0]
    if full_raw_outdir is not None:
        export_session_outputs(
            session_id=session_id,
            outdir=full_raw_outdir,
            database_url=run_result.database_url,
        )
    primary = _session_primary_metrics(session_id, run_result.database_url)
    report = simulation_report(session_ids=run_result.session_ids, database_url=run_result.database_url)
    aggregate = report["aggregate"]
    row: dict[str, float] = {"session_id": float(session_id)}
    for key, value in primary.items():
        row[key] = _normalize_numeric(value)
    for key, value in aggregate.items():
        row[key] = _normalize_numeric(value)
    return row


def _quantile_summary(raw: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for metric in metric_cols:
        series = raw[metric].astype(float)
        rows.append(
            {
                "metric": metric,
                "p10": float(series.quantile(0.10)),
                "p25": float(series.quantile(0.25)),
                "p50": float(series.quantile(0.50)),
                "p75": float(series.quantile(0.75)),
                "p90": float(series.quantile(0.90)),
                "mean": float(series.mean()),
            }
        )
    return pd.DataFrame(rows)


def run_replications(
    *,
    base_config: SimConfig,
    chosen_params: dict[str, Any],
    runs: int,
    base_seed: int,
    output: Path,
    emit_full_raw: bool = False,
) -> dict[str, Any]:
    if runs < 1:
        raise ValueError("runs must be >= 1")
    output.mkdir(parents=True, exist_ok=True)

    production_overrides: dict[str, Any] = {
        **chosen_params,
        "subject_count": 24,
        "treated_count": 8,
        "b": 36.0,
        "num_sessions": 1,
        "include_practice": True,
        "outdir": output,
    }
    cfg = apply_overrides(base_config, production_overrides)
    full_raw_root = output / "full_raw"
    if emit_full_raw:
        full_raw_root.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict[str, float]] = []
    for run_index in range(runs):
        seed = base_seed + run_index
        run_cfg = apply_overrides(
            cfg,
            {
                "seed": seed,
                "db_path": str((output / f"run_{run_index + 1}.db").resolve()),
            },
        )
        full_raw_outdir = (full_raw_root / f"run_{run_index + 1}") if emit_full_raw else None
        row = _run_once(config=run_cfg, full_raw_outdir=full_raw_outdir)
        row = {"run_index": float(run_index + 1), "seed": float(seed), **row}
        raw_rows.append(row)

    raw = pd.DataFrame(raw_rows)
    metric_cols = [col for col in raw.columns if col not in {"run_index", "seed"}]
    summary = _quantile_summary(raw, metric_cols)

    raw_path = output / "runs_24_raw.csv"
    summary_path = output / "runs_24_summary_quantiles.csv"
    config_path = output / "runs_24_config.json"

    raw.to_csv(raw_path, index=False)
    summary.to_csv(summary_path, index=False)

    cfg_payload = asdict(cfg)
    cfg_payload["outdir"] = str(cfg.outdir)
    config_path.write_text(
        json.dumps(
            {
                "runs": runs,
                "base_seed": base_seed,
                "chosen_params": chosen_params,
                "applied_config": cfg_payload,
                "artifacts": {
                    "raw": str(raw_path),
                    "quantiles": str(summary_path),
                    "full_raw_root": str(full_raw_root) if emit_full_raw else None,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    return {
        "runs": runs,
        "raw_path": str(raw_path),
        "quantiles_path": str(summary_path),
        "config_path": str(config_path),
        "metrics": metric_cols,
    }


def main() -> None:
    args = _parse_args()
    chosen_params = json.loads(args.chosen.read_text())
    if not isinstance(chosen_params, dict):
        raise ValueError("chosen params file must contain a JSON object")
    base = _resolve_base_config(args.config)
    result = run_replications(
        base_config=base,
        chosen_params=chosen_params,
        runs=args.runs,
        base_seed=args.base_seed,
        output=args.output,
        emit_full_raw=args.emit_full_raw,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
