from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration.simulate_market import run_simulation


def evaluate_b(b: float, runs: int, true_probability: float) -> float:
    errors = []
    for seed in range(runs):
        result = run_simulation(
            num_traders=16,
            rounds=5,
            b=b,
            true_probability=true_probability,
            seed=seed,
        )
        errors.append(abs(result.final_price - true_probability))
    return mean(errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep LMSR B values and report fit quality.")
    parser.add_argument("--b-values", default="10,15,18,20,25,30,40,50,60,70,80,90,100", help="Comma-separated B values to evaluate.")
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--true-probability", type=float, default=0.65)
    args = parser.parse_args()

    values = [float(v.strip()) for v in args.b_values.split(",") if v.strip()]
    scored = []
    for b in values:
        mae = evaluate_b(b=b, runs=args.runs, true_probability=args.true_probability)
        scored.append((b, mae))
        print(f"B={b:.2f} -> mean abs error={mae:.4f}")
    best = min(scored, key=lambda x: x[1])
    print(f"Recommended B={best[0]:.2f} (lowest mean abs error {best[1]:.4f})")


if __name__ == "__main__":
    main()
