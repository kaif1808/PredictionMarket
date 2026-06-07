"""Layer 3B — direction classifier + quantity regressor, leave-one-session-out CV."""
from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import statsmodels.api as sm

_DIRECTION_FEATURES = [
    "perceived_edge",
    "balance_at_trade",
    "is_informed",
    "is_whale",
    "switch_point",
    "round_number",
]
_QUANTITY_FEATURES = _DIRECTION_FEATURES


def _auc_roc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Mann-Whitney AUC (no sklearn dependency)."""
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    count = sum(
        (float(p) > float(n)) + 0.5 * (float(p) == float(n))
        for p in pos
        for n in neg
    )
    return count / (len(pos) * len(neg))


def _prep_features(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy().astype(float)
    X = sm.add_constant(X, has_constant="add")
    return X


@dataclass
class LevelBModels:
    direction_model: Any = None
    quantity_model: Any = None
    direction_coef: np.ndarray = field(default_factory=lambda: np.array([]))
    quantity_coef: np.ndarray = field(default_factory=lambda: np.array([]))
    direction_features: list[str] = field(default_factory=lambda: list(_DIRECTION_FEATURES))
    quantity_features: list[str] = field(default_factory=lambda: list(_QUANTITY_FEATURES))


def _drop_na_rows(df: pd.DataFrame, cols: list[str], target: str) -> pd.DataFrame:
    needed = cols + [target]
    return df[needed].dropna().copy()


def fit_direction_model(panel: pd.DataFrame) -> Any:
    """Fit statsmodels Logit for yes_exposure_up target."""
    df = _drop_na_rows(panel, _DIRECTION_FEATURES, "yes_exposure_up")
    X = _prep_features(df, _DIRECTION_FEATURES)
    y = df["yes_exposure_up"].astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.Logit(y, X).fit(disp=False, maxiter=200)
    return model


def fit_quantity_model(panel: pd.DataFrame) -> Any:
    """Fit OLS on log(quantity) for quantity magnitude."""
    df = _drop_na_rows(panel, _QUANTITY_FEATURES, "quantity")
    df = df[df["quantity"] > 0].copy()
    df["log_quantity"] = np.log(df["quantity"].astype(float))
    X = _prep_features(df, _QUANTITY_FEATURES)
    y = df["log_quantity"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.OLS(y, X).fit()
    return model


def fit_level_b(panel: pd.DataFrame) -> LevelBModels:
    """Fit both models on full panel."""
    dir_model = fit_direction_model(panel)
    qty_model = fit_quantity_model(panel)
    return LevelBModels(
        direction_model=dir_model,
        quantity_model=qty_model,
        direction_coef=np.array(dir_model.params),
        quantity_coef=np.array(qty_model.params),
    )


def predict_direction_prob(model: Any, df: pd.DataFrame) -> np.ndarray:
    """Return probability of yes_exposure_up=1 for each row."""
    X = _prep_features(df, _DIRECTION_FEATURES)
    return np.array(model.predict(X))


def predict_quantity(model: Any, df: pd.DataFrame) -> np.ndarray:
    """Return predicted quantity magnitude (exponentiated from log-OLS)."""
    X = _prep_features(df, _QUANTITY_FEATURES)
    log_qty = np.array(model.predict(X))
    return np.exp(log_qty)


def loso_cv(panel: pd.DataFrame) -> dict[str, Any]:
    """
    Leave-one-session-out cross-validation.
    Returns per-fold AUC split by is_informed and aggregate.
    """
    sessions = sorted(panel["session_id"].unique().tolist())
    folds: list[dict[str, Any]] = []

    for held_out in sessions:
        train = panel[panel["session_id"] != held_out].copy()
        test = panel[panel["session_id"] == held_out].copy()

        if train.empty or test.empty:
            continue

        try:
            dir_model = fit_direction_model(train)
        except Exception:
            continue

        test_clean = _drop_na_rows(test, _DIRECTION_FEATURES, "yes_exposure_up")
        if test_clean.empty:
            continue

        probs = predict_direction_prob(dir_model, test_clean)
        y_true = test_clean["yes_exposure_up"].astype(int).values

        fold_result: dict[str, Any] = {"held_out_session": held_out}

        for role_label, is_inf_val in [("informed", 1), ("uninformed", 0)]:
            mask = test_clean["is_informed"].astype(int).values == is_inf_val
            if mask.sum() == 0:
                fold_result[f"{role_label}_auc"] = float("nan")
                continue
            auc = _auc_roc(y_true[mask], probs[mask])
            fold_result[f"{role_label}_auc"] = auc

        fold_result["overall_auc"] = _auc_roc(y_true, probs)
        folds.append(fold_result)

    def _nanmean(vals: list) -> float:
        clean = [v for v in vals if not (isinstance(v, float) and v != v)]
        return float(np.mean(clean)) if clean else float("nan")

    return {
        "folds": folds,
        "n_folds": len(folds),
        "mean_informed_auc": _nanmean([f.get("informed_auc", float("nan")) for f in folds]),
        "mean_uninformed_auc": _nanmean([f.get("uninformed_auc", float("nan")) for f in folds]),
        "mean_overall_auc": _nanmean([f.get("overall_auc", float("nan")) for f in folds]),
    }
