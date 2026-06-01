from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from analysis.benchmark_recompute import recompute_session_benchmarks
from analysis.load import load_session
from analysis.metrics import price_path_deviation, round_volume, treatment_panel
from analysis.outcomes import (
    convergence_speed,
    informed_returns,
    information_revelation_correlation,
    price_accuracy,
    price_impact,
    return_inequality,
    trading_volume,
)


@contextmanager
def _database_url(database_url: str):
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev


def export_session_outputs(*, session_id: int, outdir: Path, database_url: str) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    with _database_url(database_url):
        frames = load_session(session_id)

    outputs: list[Path] = []

    metric_writes = [
        (price_path_deviation(frames), f"session_{session_id}_price_deviation.csv"),
        (round_volume(frames), f"session_{session_id}_round_volume.csv"),
        (treatment_panel(frames), f"session_{session_id}_treatment_panel.csv"),
        (recompute_session_benchmarks(frames), f"session_{session_id}_benchmark_recompute.csv"),
        (price_accuracy(frames), f"session_{session_id}_price_accuracy.csv"),
        (convergence_speed(frames), f"session_{session_id}_convergence_speed.csv"),
        (informed_returns(frames), f"session_{session_id}_informed_returns.csv"),
        (return_inequality(frames), f"session_{session_id}_return_inequality.csv"),
        (trading_volume(frames), f"session_{session_id}_trading_volume.csv"),
        (price_impact(frames), f"session_{session_id}_price_impact.csv"),
        (information_revelation_correlation(frames), f"session_{session_id}_info_revelation_corr.csv"),
    ]
    for frame, name in metric_writes:
        path = outdir / name
        frame.to_csv(path, index=False)
        outputs.append(path)

    raw_writes = [
        (frames.sessions, "sessions"),
        (frames.markets, "markets"),
        (frames.rounds, "rounds"),
        (frames.trades, "trades"),
        (frames.signals, "signals"),
        (frames.market_roles, "market_roles"),
        (frames.tournament, "tournament"),
    ]
    for frame, label in raw_writes:
        path = outdir / f"session_{session_id}_raw_{label}.csv"
        frame.to_csv(path, index=False)
        outputs.append(path)

    return outputs


def export_all_sessions(*, session_ids: list[int], outdir: Path, database_url: str) -> list[Path]:
    written: list[Path] = []
    for sid in session_ids:
        written.extend(export_session_outputs(session_id=sid, outdir=outdir, database_url=database_url))
    return written
