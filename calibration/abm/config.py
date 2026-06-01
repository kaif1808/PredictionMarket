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
    b: float = 18.0
    risk_aversion: float | None = None
    seed: int = 42
    profile_mix: str = "rational:5,herder:2,noise:2"
    num_sessions: int = 1
    include_practice: bool = True
    outdir: Path = Path("calibration/abm/output")
    db_path: str = ":memory:"

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
        return self


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
