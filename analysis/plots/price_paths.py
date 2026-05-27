from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot closing prices vs Bayesian benchmark by market.")
    parser.add_argument("--rounds-csv", type=Path, required=True, help="CSV with rounds export including closing_price and bayesian_benchmark")
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    args = parser.parse_args()

    df = pd.read_csv(args.rounds_csv)
    args.outdir.mkdir(parents=True, exist_ok=True)
    for market_id, grp in df.groupby("market_id"):
        g = grp.sort_values("round_number")
        plt.figure(figsize=(6, 4))
        plt.plot(g["round_number"], g["closing_price"], marker="o", label="Closing price")
        plt.plot(g["round_number"], g["bayesian_benchmark"], marker="x", label="Benchmark")
        plt.title(f"Market {market_id}: Price vs Benchmark")
        plt.xlabel("Round")
        plt.ylabel("Probability")
        plt.ylim(0, 1)
        plt.grid(alpha=0.2)
        plt.legend()
        plt.tight_layout()
        plt.savefig(args.outdir / f"market_{market_id}_price_vs_benchmark.png", dpi=150)
        plt.close()


if __name__ == "__main__":
    main()
