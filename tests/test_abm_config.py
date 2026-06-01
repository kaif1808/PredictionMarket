from __future__ import annotations

import pytest

from calibration.abm.config import SimConfig


def test_simconfig_state_hybrid_defaults_are_valid() -> None:
    cfg = SimConfig().validated()
    assert cfg.intensity_mode == "state_hybrid"


def test_simconfig_rejects_invalid_state_intensity_bounds() -> None:
    with pytest.raises(ValueError, match="lambda_min"):
        SimConfig(lambda_min=1.0, lambda_max=1.0).validated()


def test_simconfig_accepts_legacy_homogeneous_mode() -> None:
    cfg = SimConfig(intensity_mode="legacy_homogeneous", event_intensity=0.5).validated()
    assert cfg.intensity_mode == "legacy_homogeneous"
