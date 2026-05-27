from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import lmsr


@dataclass
class SimResult:
    final_price: float
    q_yes: float
    q_no: float
    trades: int


def run_simulation(num_traders: int, rounds: int, b: float, true_probability: float, seed: int) -> SimResult:
    rng = random.Random(seed)
    q_yes = 0.0
    q_no = 0.0
    trades = 0
    for _ in range(rounds):
        for _ in range(num_traders):
            p = lmsr.price(q_yes, q_no, b)
            target = true_probability + rng.uniform(-0.08, 0.08)
            if target > p:
                qty = rng.randint(1, 3)
                q_yes += qty
            else:
                qty = rng.randint(1, 3)
                q_no += qty
            trades += 1
    return SimResult(final_price=lmsr.price(q_yes, q_no, b), q_yes=q_yes, q_no=q_no, trades=trades)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic market simulation for LMSR calibration.")
    parser.add_argument("--num-traders", type=int, default=16)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--b", type=float, default=20.0)
    parser.add_argument("--true-probability", type=float, default=0.65)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run_simulation(
        num_traders=args.num_traders,
        rounds=args.rounds,
        b=args.b,
        true_probability=args.true_probability,
        seed=args.seed,
    )
    print(
        {
            "final_price": round(result.final_price, 4),
            "q_yes": result.q_yes,
            "q_no": result.q_no,
            "trades": result.trades,
        }
    )


if __name__ == "__main__":
    main()
