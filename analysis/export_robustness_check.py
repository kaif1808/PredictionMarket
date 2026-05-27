from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.load import load_session
from analysis.robustness import tournament_effect_robustness


def main() -> None:
    parser = argparse.ArgumentParser(description="Run tournament-effect robustness check for one session.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    frames = load_session(args.session_id)
    res = tournament_effect_robustness(frames)

    res.panel.to_csv(args.outdir / f"session_{args.session_id}_robustness_panel.csv", index=False)
    res.regression_table.to_csv(
        args.outdir / f"session_{args.session_id}_robustness_regression.csv",
        index=False,
    )
    (args.outdir / f"session_{args.session_id}_robustness_summary.txt").write_text(
        res.model_summary_text,
        encoding="utf-8",
    )
    print(f"Wrote robustness outputs to {args.outdir.resolve()}")


if __name__ == "__main__":
    main()
