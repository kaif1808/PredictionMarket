from __future__ import annotations

import pandas as pd

from calibration.abm.config import apply_overrides, preset_config
from calibration.abm.replicate import run_replications


def test_run_replications_writes_raw_and_quantiles(tmp_path) -> None:
    base = apply_overrides(
        preset_config("production"),
        {
            "round_duration_s": 1.0,
        },
    )
    chosen = {
        "intensity_mode": "state_hybrid",
        "lambda_base": 1.0,
        "edge_gain": 1.25,
        "edge_exp": 1.0,
        "vol_gain": 1.0,
        "vol_exp": 1.0,
        "vol_ema_alpha": 0.2,
        "vol_ref": 0.05,
        "lambda_min": 0.05,
        "lambda_max": 4.0,
        "order_size_dist": "geometric:p=0.68,tail=0.35",
        "sell_propensity": 0.7799,
        "edge_threshold": 0.0139,
        "ra_mean": 0.431,
        "ra_sd": 0.0569,
        "ra_lo": 0.05,
        "ra_hi": 0.95,
    }
    result = run_replications(
        base_config=base,
        chosen_params=chosen,
        runs=2,
        base_seed=900,
        output=tmp_path / "runs24",
        emit_full_raw=True,
    )

    raw = pd.read_csv(result["raw_path"])
    quantiles = pd.read_csv(result["quantiles_path"])

    assert len(raw) == 2
    assert {"run_index", "seed", "session_id"}.issubset(set(raw.columns))
    assert {"metric", "p10", "p25", "p50", "p75", "p90", "mean"}.issubset(set(quantiles.columns))
    assert (tmp_path / "runs24" / "full_raw" / "run_1" / "session_1_raw_trades.csv").exists()
    assert (tmp_path / "runs24" / "full_raw" / "run_2" / "session_1_raw_rounds.csv").exists()
