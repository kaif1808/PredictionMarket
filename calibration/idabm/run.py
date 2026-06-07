"""CLI entry point for identification ABM."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration.idabm.data import build_market_deviation, build_trade_panel, load_raw
from calibration.idabm.layer3_levelb import fit_level_b, loso_cv
from calibration.idabm.layer3_levelc import fit_crra_all
from calibration.idabm.validation import run_validation

_DEFAULT_OUTDIR = Path("calibration/idabm/output")


def _run_validate(panel: pd.DataFrame, raw: dict, outdir: Path) -> dict:
    val_df, all_passed = run_validation(panel, raw)
    print("\n=== Validation Gate ===")
    print(val_df.to_string(index=False))
    print(f"\nAll passed: {all_passed}")

    out = val_df.to_dict(orient="records")
    (outdir / "validation_gate.json").write_text(json.dumps(out, indent=2))
    return {"all_passed": all_passed, "rows": out}


def _run_loso(panel: pd.DataFrame, outdir: Path) -> dict:
    print("\n=== Level B LOSO-CV ===")
    cv_result = loso_cv(panel)
    print(f"  Folds: {cv_result['n_folds']}")
    print(f"  Informed AUC (mean): {cv_result['mean_informed_auc']:.3f}")
    print(f"  Uninformed AUC (mean): {cv_result['mean_uninformed_auc']:.3f}")
    (outdir / "loso_cv.json").write_text(json.dumps(cv_result, indent=2, default=str))
    return cv_result


def _run_counterfactual(
    experiment: str,
    iters: int,
    quantity_source: str,
    panel: pd.DataFrame,
    raw: dict,
    outdir: Path,
) -> dict:
    from calibration.idabm.counterfactual import run_counterfactual
    from calibration.idabm.data import build_market_deviation

    print(f"\n=== Counterfactual: {experiment} ({iters} iters, qty={quantity_source}) ===")

    models_b = fit_level_b(panel)
    crra_result = fit_crra_all(panel)
    params_c = crra_result["params"]
    print(f"  Fallback count (CRRA): {crra_result['fallback_count']}")

    market_dev = build_market_deviation(raw)
    empirical_abs_dev = float(market_dev["abs_deviation_benchmark"].mean())

    experiments = ["order", "scenario", "full"] if experiment == "all" else [experiment]
    results = {}
    for exp in experiments:
        r = run_counterfactual(
            experiment=exp,
            iters=iters,
            models_b=models_b,
            params_c=params_c,
            empirical_effect=empirical_abs_dev,
            quantity_source=quantity_source,
        )
        results[exp] = r
        effect = r["treatment_effect"]
        print(f"  [{exp}] coef_has_informed={effect.get('coef_has_informed', 'n/a'):.4f}  "
              f"coef_has_whale={effect.get('coef_has_whale', 'n/a'):.4f}")

    out_path = outdir / f"counterfactual_{experiment}.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"  Written: {out_path}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Identification ABM")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--loso", action="store_true", help="Run Level B LOSO-CV")
    parser.add_argument(
        "--counterfactual",
        choices=["order", "scenario", "full", "all"],
        default=None,
    )
    parser.add_argument("--iters", type=int, default=500)
    parser.add_argument(
        "--quantity-source", choices=["levelb", "levelc"], default="levelb"
    )
    parser.add_argument("--outdir", type=Path, default=_DEFAULT_OUTDIR)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)

    print("Loading experiment_2 data…")
    raw = load_raw()
    panel = build_trade_panel(raw)
    print(f"  Panel: {len(panel)} non-practice trades, {panel['market_id'].nunique()} markets")

    summary: dict = {}

    val_result = _run_validate(panel, raw, args.outdir)
    summary["validation"] = val_result

    if args.validate_only:
        print(json.dumps(summary, indent=2, default=str))
        return

    if args.loso or not args.counterfactual:
        summary["loso_cv"] = _run_loso(panel, args.outdir)

    if args.counterfactual:
        summary["counterfactual"] = _run_counterfactual(
            args.counterfactual,
            args.iters,
            args.quantity_source,
            panel,
            raw,
            args.outdir,
        )

    summary_path = args.outdir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
