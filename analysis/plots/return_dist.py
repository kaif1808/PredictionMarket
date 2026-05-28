from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot return distributions by role tier.")
    parser.add_argument("--market-roles-csv", type=Path, required=True, help="CSV with market_roles export including role_tier and final_balance/endowment_tokens")
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    args = parser.parse_args()

    df = pd.read_csv(args.market_roles_csv)
    if "return_ratio" not in df.columns:
        df["return_ratio"] = (df["final_balance"] - df["endowment_tokens"]) / df["endowment_tokens"]

    args.outdir.mkdir(parents=True, exist_ok=True)
    order = ["uninformed", "informed"]
    data = [df.loc[df["role_tier"] == role, "return_ratio"].dropna().values for role in order]

    plt.figure(figsize=(7, 4))
    plt.boxplot(data, labels=order, showfliers=True)
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)
    plt.title("Return Ratio Distribution by Role Tier")
    plt.ylabel("(final_balance - endowment_tokens) / endowment_tokens")
    plt.tight_layout()
    plt.savefig(args.outdir / "return_ratio_by_role_tier.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    main()
