from __future__ import annotations

import math
import pandas as pd

from analysis.benchmark_recompute import recompute_session_benchmarks
from analysis.load import load_session
from analysis.outcomes import (
    convergence_speed,
    informed_returns,
    information_revelation_correlation,
    price_accuracy,
    price_impact,
    return_inequality,
    trading_volume,
)
from calibration.abm.config import SimConfig, preset_config
from calibration.abm.export import _database_url, export_all_sessions
from calibration.abm.runner import run_abm
from calibration.abm.sim_metrics import simulation_report


def test_abm_export_pipeline_and_analysis_parity(tmp_path) -> None:
    base = preset_config("validation")
    config = SimConfig(
        **{
            **base.__dict__,
            "seed": 42,
            "num_sessions": 1,
            "include_practice": True,
            "db_path": str(tmp_path / "abm_export.db"),
            "outdir": tmp_path / "out",
        }
    )
    run_result = run_abm(config)
    written = export_all_sessions(
        session_ids=run_result.session_ids,
        outdir=config.outdir,
        database_url=run_result.database_url,
    )
    assert written
    sid = run_result.session_ids[0]
    expected_metric = config.outdir / f"session_{sid}_price_accuracy.csv"
    expected_recompute = config.outdir / f"session_{sid}_benchmark_recompute.csv"
    expected_raw = config.outdir / f"session_{sid}_raw_rounds.csv"
    expected_trades = config.outdir / f"session_{sid}_raw_trades.csv"
    assert expected_metric.exists()
    assert expected_recompute.exists()
    assert expected_raw.exists()
    assert expected_trades.exists()

    with _database_url(run_result.database_url):
        frames = load_session(sid)
    assert not price_accuracy(frames).empty
    assert not convergence_speed(frames).empty
    assert not informed_returns(frames).empty
    assert not return_inequality(frames).empty
    assert not trading_volume(frames).empty
    assert not price_impact(frames).empty
    _ = information_revelation_correlation(frames)

    recomputed = recompute_session_benchmarks(frames)
    assert not recomputed.empty
    assert float(recomputed["abs_diff"].max()) <= 1e-9

    trade_export = pd.read_csv(expected_trades)
    assert (trade_export["cost"].astype(float) < 0).any()

    report = simulation_report(session_ids=run_result.session_ids, database_url=run_result.database_url)
    assert report["session_ids"] == run_result.session_ids
    assert report["per_session"]
    assert not math.isnan(report["aggregate"]["price_mse_vs_truth"])
