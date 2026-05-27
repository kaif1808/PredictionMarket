from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.benchmark_recompute import recompute_session_benchmarks
from analysis.load import load_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate server Bayesian benchmarks against independent recomputation.")
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()

    frames = load_session(args.session_id)
    table = recompute_session_benchmarks(frames)
    if table.empty:
        print({"session_id": args.session_id, "rounds_checked": 0, "max_abs_diff": None, "ok": True})
        return

    diffs = table["abs_diff"].dropna()
    max_diff = float(diffs.max()) if len(diffs) else math.nan
    ok = bool(len(diffs) == 0 or max_diff <= args.tolerance)
    print(
        {
            "session_id": args.session_id,
            "rounds_checked": int(len(table)),
            "max_abs_diff": max_diff,
            "tolerance": args.tolerance,
            "ok": ok,
        }
    )
    if not ok:
        worst = table.sort_values("abs_diff", ascending=False).head(5)
        print(worst.to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
