from __future__ import annotations

import argparse
import os
from pathlib import Path

# Keep plotting cache/config in writable temp dirs for sandboxed environments.
cache_root = Path("/private/tmp")
os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib-config"))
os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))
(cache_root / "matplotlib-config").mkdir(parents=True, exist_ok=True)
(cache_root / "fontconfig").mkdir(parents=True, exist_ok=True)

import matplotlib
import pandas as pd

# Force a non-GUI backend so scripts work in headless/sandboxed environments.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _exclude_practice_rounds(rounds_df: pd.DataFrame, rounds_csv: Path, include_practice: bool) -> pd.DataFrame:
    if include_practice:
        return rounds_df

    markets_csv = rounds_csv.parent / "markets.csv"
    if not markets_csv.exists():
        return rounds_df

    markets = pd.read_csv(markets_csv)
    if "id" not in markets.columns or "market_id" not in rounds_df.columns:
        return rounds_df

    if "is_practice" in markets.columns:
        practice_market_ids = set(markets.loc[markets["is_practice"] == True, "id"].astype(int).tolist())  # noqa: E712
    elif "market_number" in markets.columns:
        practice_market_ids = set(markets.loc[markets["market_number"] == 0, "id"].astype(int).tolist())
    else:
        return rounds_df

    return rounds_df[~rounds_df["market_id"].astype(int).isin(practice_market_ids)].copy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot closing prices vs Bayesian benchmark by market.")
    parser.add_argument("--rounds-csv", type=Path, required=True, help="CSV with rounds export including closing_price and bayesian_benchmark")
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    parser.add_argument(
        "--include-practice",
        action="store_true",
        help="Include practice market (market_number=0) if present.",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.rounds_csv)
    required = {"market_id", "round_number", "closing_price", "bayesian_benchmark"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"{args.rounds_csv} is missing required columns: {', '.join(missing)}"
        )

    if df.empty:
        raise ValueError(f"{args.rounds_csv} is empty; no rounds available to plot.")

    df = _exclude_practice_rounds(df, args.rounds_csv, include_practice=args.include_practice)
    if df.empty:
        raise ValueError("No non-practice rounds remain after filtering.")

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
