from __future__ import annotations

import json

from calibration.abm.calibrate import extract_reference_targets, run_calibration, score_candidate
from calibration.abm.config import apply_overrides, preset_config


def test_extract_reference_targets_matches_known_counts() -> None:
    targets = extract_reference_targets()
    assert targets.non_practice_trade_count == 3352
    assert targets.export_alignment_rows == 3352
    assert targets.non_empty_markets_per_session_min == 4
    assert targets.median_order_size == 1.0
    assert 0.2 <= targets.negative_cost_share <= 0.4


def test_score_candidate_gate_fails_for_off_target_config(tmp_path) -> None:
    targets = extract_reference_targets()
    base = preset_config("validation")
    off_target = apply_overrides(
        base,
        {
            "lambda_base": 0.05,
            "edge_gain": 0.0,
            "vol_gain": 0.0,
            "lambda_min": 0.01,
            "lambda_max": 0.06,
            "sell_propensity": 0.0,
            "edge_threshold": 0.08,
            "db_path": str(tmp_path / "off_target.db"),
            "outdir": tmp_path / "off_target_out",
            "seed": 103,
        },
    )
    result = score_candidate(config=off_target, reference=targets)
    assert result.gate_pass is False
    assert any(not passed for passed in result.primary_gate.values())


def test_run_calibration_writes_outputs(tmp_path) -> None:
    cfg = apply_overrides(
        preset_config("validation"),
        {
            "db_path": str(tmp_path / "calibrate.db"),
            "outdir": tmp_path / "abm_out",
            "seed": 77,
        },
    )
    run = run_calibration(config=cfg, outdir=tmp_path / "calibration", sweep=1, seed=77)
    assert run["candidates"] == 1

    comparison_path = tmp_path / "calibration" / "abm_vs_reference.json"
    chosen_path = tmp_path / "calibration" / "chosen_params.json"
    leaderboard_path = tmp_path / "calibration" / "leaderboard.csv"
    assert comparison_path.exists()
    assert chosen_path.exists()
    assert leaderboard_path.exists()

    comparison = json.loads(comparison_path.read_text())
    assert "reference" in comparison
    assert "modeled" in comparison
    assert "ratios" in comparison
    assert "primary_gate" in comparison
