from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SimConfig:
    rotation_id: int = 1
    subject_count: int = 9
    treated_count: int = 3
    b: float = 36.0
    # Deprecated single-value override kept for backward compatibility.
    risk_aversion: float | None = None
    seed: int = 42
    profile_mix: str = "rational:5,herder:2,noise:2"
    num_sessions: int = 1
    include_practice: bool = True
    outdir: Path = Path("calibration/abm/output")
    db_path: str = ":memory:"

    round_duration_s: float = 90.0
    intensity_mode: str = "state_hybrid"
    # Legacy homogeneous Poisson knob, used only when intensity_mode="legacy_homogeneous".
    event_intensity: float = 1.3635
    lambda_base: float = 1.0
    edge_gain: float = 1.25
    edge_exp: float = 1.0
    vol_gain: float = 1.0
    vol_exp: float = 1.0
    vol_ema_alpha: float = 0.2
    vol_ref: float = 0.05
    lambda_min: float = 0.05
    lambda_max: float = 4.0
    order_size_dist: str = "geometric:p=0.68,tail=0.35"
    reaction_delay_s: float = 0.65
    reaction_delay_jitter_s: float = 0.35
    sell_propensity: float = 0.7799
    edge_threshold: float = 0.0139

    ra_mean: float = 0.431
    ra_sd: float = 0.0569
    ra_lo: float = 0.05
    ra_hi: float = 0.95

    def validated(self) -> SimConfig:
        if self.subject_count < 2:
            raise ValueError("subject_count must be >= 2")
        if self.treated_count < 2:
            raise ValueError("treated_count must be >= 2")
        if self.treated_count > self.subject_count:
            raise ValueError("treated_count must be <= subject_count")
        if self.b <= 0:
            raise ValueError("b must be > 0")
        if self.num_sessions < 1:
            raise ValueError("num_sessions must be >= 1")
        if self.risk_aversion is not None and not (0.0 <= self.risk_aversion <= 1.0):
            raise ValueError("risk_aversion override must be in [0,1]")
        if self.round_duration_s <= 0:
            raise ValueError("round_duration_s must be > 0")
        if self.intensity_mode not in {"state_hybrid", "legacy_homogeneous"}:
            raise ValueError("intensity_mode must be one of: state_hybrid, legacy_homogeneous")
        if self.event_intensity <= 0:
            raise ValueError("event_intensity must be > 0")
        if self.lambda_base <= 0:
            raise ValueError("lambda_base must be > 0")
        if not (0.0 <= self.lambda_min < self.lambda_max):
            raise ValueError("require 0 <= lambda_min < lambda_max")
        if self.edge_gain < 0 or self.vol_gain < 0:
            raise ValueError("edge_gain and vol_gain must be >= 0")
        if self.edge_exp <= 0 or self.vol_exp <= 0:
            raise ValueError("edge_exp and vol_exp must be > 0")
        if not (0.0 < self.vol_ema_alpha <= 1.0):
            raise ValueError("vol_ema_alpha must be in (0,1]")
        if self.vol_ref <= 0:
            raise ValueError("vol_ref must be > 0")
        if not (0.0 <= self.sell_propensity <= 1.0):
            raise ValueError("sell_propensity must be in [0,1]")
        if self.edge_threshold < 0:
            raise ValueError("edge_threshold must be >= 0")
        if self.reaction_delay_s < 0:
            raise ValueError("reaction_delay_s must be >= 0")
        if self.reaction_delay_jitter_s < 0:
            raise ValueError("reaction_delay_jitter_s must be >= 0")
        if self.ra_sd < 0:
            raise ValueError("ra_sd must be >= 0")
        if not (0.0 <= self.ra_lo <= 1.0 and 0.0 <= self.ra_hi <= 1.0):
            raise ValueError("ra_lo/ra_hi must be in [0,1]")
        if self.ra_lo >= self.ra_hi:
            raise ValueError("ra_lo must be < ra_hi")
        if not (self.ra_lo <= self.ra_mean <= self.ra_hi):
            raise ValueError("ra_mean must lie within [ra_lo, ra_hi]")
        return self


PRESET_VALIDATION = SimConfig(subject_count=9, treated_count=3, b=36.0)
PRESET_PRODUCTION = SimConfig(subject_count=24, treated_count=8, b=36.0)


def preset_config(name: str) -> SimConfig:
    normalized = name.strip().lower()
    if normalized == "validation":
        return PRESET_VALIDATION.validated()
    if normalized == "production":
        return PRESET_PRODUCTION.validated()
    raise ValueError(f"unknown preset config '{name}'")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("YAML config requires pyyaml. Use JSON config or install pyyaml.") from exc
    payload = yaml.safe_load(path.read_text())  # type: ignore[no-untyped-call]
    return payload if isinstance(payload, dict) else {}


def load_config_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else {}
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    raise ValueError("config file must be .json, .yaml, or .yml")


def config_from_mapping(mapping: dict[str, Any]) -> SimConfig:
    values: dict[str, Any] = dict(mapping)
    if "outdir" in values and values["outdir"] is not None:
        values["outdir"] = Path(values["outdir"])
    return SimConfig(**values).validated()


def apply_overrides(base: SimConfig, overrides: dict[str, Any]) -> SimConfig:
    filtered = {k: v for k, v in overrides.items() if v is not None}
    if "outdir" in filtered:
        filtered["outdir"] = Path(filtered["outdir"])
    return replace(base, **filtered).validated()
