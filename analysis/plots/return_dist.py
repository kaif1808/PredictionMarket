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


def _exclude_practice_rows(df: pd.DataFrame, market_roles_csv: Path, include_practice: bool) -> pd.DataFrame:
    if include_practice or "market_id" not in df.columns:
        return df

    markets_csv = market_roles_csv.parent / "markets.csv"
    if not markets_csv.exists():
        return df

    markets = pd.read_csv(markets_csv)
    if "id" not in markets.columns:
        return df

    if "is_practice" in markets.columns:
        practice_market_ids = set(markets.loc[markets["is_practice"] == True, "id"].astype(int).tolist())  # noqa: E712
    elif "market_number" in markets.columns:
        practice_market_ids = set(markets.loc[markets["market_number"] == 0, "id"].astype(int).tolist())
    else:
        return df

    return df[~df["market_id"].astype(int).isin(practice_market_ids)].copy()


def _normalize_role(raw_role: str) -> str:
    role = str(raw_role).strip().lower()
    if role in {"informed", "insider"}:
        return "insider"
    if role == "uninformed":
        return "uninformed"
    return role


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot return ratio distributions by role/endowment permutations.")
    parser.add_argument("--market-roles-csv", type=Path, required=True, help="CSV with market_roles export including role_tier and final_balance/endowment_tokens")
    parser.add_argument("--outdir", type=Path, default=Path("analysis/output"))
    parser.add_argument(
        "--whale-threshold",
        type=float,
        default=400.0,
        help="Endowment threshold used to classify whale vs nonwhale.",
    )
    parser.add_argument(
        "--include-practice",
        action="store_true",
        help="Include practice market (market_number=0) if present.",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.market_roles_csv)
    required = {"role_tier", "endowment_tokens"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"{args.market_roles_csv} is missing required columns: {', '.join(missing)}"
        )

    if "return_ratio" not in df.columns:
        if "final_balance" not in df.columns:
            raise ValueError(
                f"{args.market_roles_csv} must contain either return_ratio or final_balance."
            )
        final_balance = pd.to_numeric(df["final_balance"], errors="coerce")
        endowment = pd.to_numeric(df["endowment_tokens"], errors="coerce")
        df["return_ratio"] = (final_balance - endowment) / endowment

    df["return_ratio"] = pd.to_numeric(df["return_ratio"], errors="coerce")
    df = _exclude_practice_rows(df, args.market_roles_csv, include_practice=args.include_practice)
    df["role_group"] = df["role_tier"].map(_normalize_role)
    df["endowment_tokens"] = pd.to_numeric(df["endowment_tokens"], errors="coerce")
    df["endowment_group"] = df["endowment_tokens"].map(
        lambda v: "whale" if pd.notna(v) and float(v) >= args.whale_threshold else "nonwhale"
    )
    df["segment"] = df["role_group"] + "_" + df["endowment_group"]
    df = df.dropna(subset=["role_tier", "return_ratio"])
    if df.empty:
        raise ValueError(f"{args.market_roles_csv} produced no valid return_ratio rows to plot.")

    args.outdir.mkdir(parents=True, exist_ok=True)
    order = [
        "insider_nonwhale",
        "insider_whale",
        "uninformed_nonwhale",
        "uninformed_whale",
    ]
    order = [segment for segment in order if (df["segment"] == segment).any()]
    if not order:
        raise ValueError("No valid insider/uninformed x whale/nonwhale groups found to plot.")
    data = [df.loc[df["segment"] == segment, "return_ratio"].dropna().values for segment in order]

    plt.figure(figsize=(9, 4))
    plt.boxplot(data, tick_labels=order, showfliers=True)
    plt.axhline(0, color="gray", linestyle="--", linewidth=1)
    plt.title("Return Ratio Distribution by Insider/Uninformed x Whale/Nonwhale")
    plt.ylabel("(final_balance - endowment_tokens) / endowment_tokens")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(args.outdir / "return_ratio_by_role_endowment_segment.png", dpi=150)
    plt.close()


if __name__ == "__main__":
    main()
