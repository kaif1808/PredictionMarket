"""Tests that calibrate.py fixes are in place."""
from __future__ import annotations

from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_load_reference_frames_no_file_not_found():
    """_load_reference_frames() reads experiment_2, not experiment_1."""
    from calibration.abm.calibrate import _load_reference_frames
    # Must not raise FileNotFoundError
    non_practice, rounds, markets, sessions = _load_reference_frames()
    assert len(non_practice) > 0


def test_load_reference_frames_is_non_practice():
    from calibration.abm.calibrate import _load_reference_frames
    non_practice, _, markets, _ = _load_reference_frames()
    # All rows should be from non-practice markets
    import pandas as pd
    m2 = pd.read_csv(ROOT / "experiment_2" / "markets.csv")
    practice_ids = set(m2.loc[m2["is_practice"].astype(bool), "id"].tolist())
    assert set(non_practice["market_id"].tolist()).isdisjoint(practice_ids)


def test_crosscheck_includes_three_files():
    """_crosscheck_export_alignment checks market_1, market_2, AND market_3."""
    import inspect
    from calibration.abm import calibrate
    src = inspect.getsource(calibrate._crosscheck_export_alignment)
    assert "market_3_trades.csv" in src, "market_3_trades.csv not in crosscheck"


def test_crosscheck_warns_not_raises():
    """_crosscheck_export_alignment warns on mismatch instead of raising."""
    from calibration.abm.calibrate import _crosscheck_export_alignment, _load_reference_frames
    # Should complete without exception regardless of count mismatch
    non_practice, _, _, _ = _load_reference_frames()
    try:
        rows = _crosscheck_export_alignment(non_practice)
        assert isinstance(rows, int)
    except RuntimeError as exc:
        pytest.fail(f"Should warn not raise: {exc}")
