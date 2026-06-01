from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BehavioralProfile:
    name: str
    risk_aversion: float
    bias: float
    stubbornness: float
    expertise: float
    market_imitation: float
    budget_variance: float


PROFILE_PRESETS: dict[str, BehavioralProfile] = {
    "rational": BehavioralProfile(
        name="rational",
        risk_aversion=0.30,
        bias=0.00,
        stubbornness=0.15,
        expertise=0.95,
        market_imitation=0.15,
        budget_variance=0.05,
    ),
    "noise": BehavioralProfile(
        name="noise",
        risk_aversion=0.65,
        bias=0.00,
        stubbornness=0.20,
        expertise=0.55,
        market_imitation=0.45,
        budget_variance=0.70,
    ),
    "herder": BehavioralProfile(
        name="herder",
        risk_aversion=0.45,
        bias=0.00,
        stubbornness=0.30,
        expertise=0.75,
        market_imitation=0.70,
        budget_variance=0.20,
    ),
    "stubborn": BehavioralProfile(
        name="stubborn",
        risk_aversion=0.35,
        bias=0.08,
        stubbornness=0.90,
        expertise=0.80,
        market_imitation=0.10,
        budget_variance=0.10,
    ),
    "overreact": BehavioralProfile(
        name="overreact",
        risk_aversion=0.25,
        bias=-0.05,
        stubbornness=0.05,
        expertise=0.85,
        market_imitation=0.30,
        budget_variance=0.30,
    ),
}


def parse_mix(mix: str) -> list[BehavioralProfile]:
    specs: list[BehavioralProfile] = []
    if not mix.strip():
        return [PROFILE_PRESETS["rational"]]
    for item in mix.split(","):
        raw = item.strip()
        if not raw:
            continue
        if ":" not in raw:
            raise ValueError(f"invalid profile mix item '{raw}', expected name:count")
        name, count_text = raw.split(":", 1)
        profile = PROFILE_PRESETS.get(name.strip())
        if profile is None:
            raise ValueError(f"unknown profile '{name.strip()}'")
        count = int(count_text.strip())
        if count <= 0:
            raise ValueError("profile mix counts must be positive")
        specs.extend([profile] * count)
    if not specs:
        raise ValueError("profile mix produced no profiles")
    return specs


def assign_profiles(participant_ids: list[str], mix: str) -> dict[str, BehavioralProfile]:
    ordered = parse_mix(mix)
    assigned: dict[str, BehavioralProfile] = {}
    for index, pid in enumerate(sorted(participant_ids)):
        profile = ordered[index] if index < len(ordered) else ordered[index % len(ordered)]
        assigned[pid] = profile
    return assigned
