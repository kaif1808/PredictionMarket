from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.load import load_session
from analysis.benchmark_recompute import recompute_session_benchmarks
from analysis.metrics import price_path_deviation, round_volume, treatment_panel
from analysis.outcomes import (
    convergence_speed,
    information_revelation_correlation,
    insider_returns,
    price_accuracy,
    price_impact,
    return_inequality,
    trading_volume,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export analysis metrics for one session.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    frames = load_session(args.session_id)

    price_path_deviation(frames).to_csv(args.outdir / f"session_{args.session_id}_price_deviation.csv", index=False)
    round_volume(frames).to_csv(args.outdir / f"session_{args.session_id}_round_volume.csv", index=False)
    treatment_panel(frames).to_csv(args.outdir / f"session_{args.session_id}_treatment_panel.csv", index=False)
    recompute_session_benchmarks(frames).to_csv(
        args.outdir / f"session_{args.session_id}_benchmark_recompute.csv",
        index=False,
    )
    price_accuracy(frames).to_csv(args.outdir / f"session_{args.session_id}_price_accuracy.csv", index=False)
    convergence_speed(frames).to_csv(args.outdir / f"session_{args.session_id}_convergence_speed.csv", index=False)
    insider_returns(frames).to_csv(args.outdir / f"session_{args.session_id}_insider_returns.csv", index=False)
    return_inequality(frames).to_csv(args.outdir / f"session_{args.session_id}_return_inequality.csv", index=False)
    trading_volume(frames).to_csv(args.outdir / f"session_{args.session_id}_trading_volume.csv", index=False)
    price_impact(frames).to_csv(args.outdir / f"session_{args.session_id}_price_impact.csv", index=False)
    information_revelation_correlation(frames).to_csv(
        args.outdir / f"session_{args.session_id}_info_revelation_corr.csv",
        index=False,
    )
    print(f"Wrote analysis outputs to {args.outdir.resolve()}")


if __name__ == "__main__":
    main()
