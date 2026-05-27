from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.bayesian import draw_signal


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate signal draw frequencies against theta.")
    parser.add_argument("--theta", type=float, default=0.85)
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--true-outcome", type=int, default=1, choices=[0, 1])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    draws = [draw_signal(true_outcome=args.true_outcome, theta=args.theta, rng=rng) for _ in range(args.samples)]
    frac_h = draws.count("H") / args.samples
    expected = args.theta if args.true_outcome == 1 else (1.0 - args.theta)
    print(
        {
            "samples": args.samples,
            "theta": args.theta,
            "true_outcome": args.true_outcome,
            "empirical_h": round(frac_h, 4),
            "expected_h": round(expected, 4),
            "abs_error": round(abs(frac_h - expected), 4),
        }
    )


if __name__ == "__main__":
    main()
