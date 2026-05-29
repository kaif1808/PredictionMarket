from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Literal


RoleTier = Literal["uninformed", "informed"]


@dataclass(frozen=True)
class MarketAssignment:
    role_tier: RoleTier
    endowment_tokens: float


@dataclass(frozen=True)
class MarketConfig:
    scenario_id: str
    stage: int
    true_probability: float
    b_parameter: float


def _canonical_participants(subject_count: int) -> list[str]:
    return [f"P{i:02d}" for i in range(1, subject_count + 1)]


def _seeded_market_ranking(
    *,
    session_id: int,
    market_number: int,
    rotation_id: int,
    subject_count: int,
    treated_count: int,
) -> list[str]:
    participants = _canonical_participants(subject_count)
    seed_material = f"{session_id}:{market_number}:{rotation_id}:{subject_count}:{treated_count}"
    seed_int = int(hashlib.sha256(seed_material.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed_int)
    rng.shuffle(participants)
    return participants


def get_assignment(
    session_id: int,
    session_rotation_id: int,
    participant_id: str,
    market_number: int,
    subject_count: int = 9,
    treated_count: int = 3,
) -> MarketAssignment:
    if treated_count < 2:
        raise ValueError("treated_count must be >= 2")
    if treated_count > subject_count:
        raise ValueError("treated_count must be <= subject_count")
    treated_slots = min(treated_count, subject_count)

    if market_number == 1:
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    ranking = _seeded_market_ranking(
        session_id=session_id,
        market_number=market_number,
        rotation_id=session_rotation_id,
        subject_count=subject_count,
        treated_count=treated_slots,
    )
    treated_participants = set(ranking[:treated_slots])

    if market_number == 2:
        if participant_id in treated_participants:
            return MarketAssignment(role_tier="informed", endowment_tokens=100.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 3:
        if participant_id in treated_participants:
            return MarketAssignment(role_tier="uninformed", endowment_tokens=400.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 4:
        if participant_id in treated_participants:
            return MarketAssignment(role_tier="informed", endowment_tokens=400.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    raise ValueError("market_number must be in [1, 4]")


def get_scenario_for_market(session_rotation_id: int, market_number: int) -> str:
    if market_number == 1:
        return "C"
    if market_number == 2:
        return "A" if session_rotation_id % 2 == 1 else "B"
    if market_number == 3:
        return "B" if session_rotation_id % 2 == 1 else "A"
    if market_number == 4:
        return "D"
    raise ValueError("market_number must be in [1, 4]")


def get_market_config(session_rotation_id: int, market_number: int, lmsr_b_parameter: float = 18.0) -> MarketConfig:
    stage = market_number
    scenario = get_scenario_for_market(session_rotation_id, market_number)
    true_prob = {"A": 0.75, "B": 0.25, "C": 0.50, "D": 0.65}[scenario]
    if lmsr_b_parameter <= 0:
        raise ValueError("lmsr_b_parameter must be > 0")
    b_param = float(lmsr_b_parameter)
    return MarketConfig(scenario_id=scenario, stage=stage, true_probability=true_prob, b_parameter=b_param)


def validate_rotation_matrix(rotation: dict[int, list[MarketAssignment]]) -> list[str]:
    errors: list[str] = []
    market_1 = rotation.get(1, [])
    if any(a.role_tier != "uninformed" or a.endowment_tokens != 100.0 for a in market_1):
        errors.append("Market 1 must assign uninformed + 100 tokens to all participants.")

    market_2 = rotation.get(2, [])
    n = max(len(rotation.get(1, [])), 0)
    informed_2 = sum(1 for a in market_2 if a.role_tier == "informed")
    expected_informed = min(3, n)
    if informed_2 != expected_informed:
        errors.append("Market 2 informed count must match the treated-count rule.")

    market_3 = rotation.get(3, [])
    whales_3 = sum(1 for a in market_3 if a.endowment_tokens == 400.0)
    expected_whales = min(3, n)
    if whales_3 != expected_whales:
        errors.append("Market 3 whale count must match the treated-count rule.")
    if any(a.role_tier != "uninformed" for a in market_3):
        errors.append("Market 3 must keep all participants uninformed.")

    market_4 = rotation.get(4, [])
    informed_whales_4 = sum(1 for a in market_4 if a.role_tier == "informed" and a.endowment_tokens == 400.0)
    if informed_whales_4 != min(expected_whales, expected_informed):
        errors.append("Market 4 informed-whale count must match the treated-whale rule.")
    informed_4 = sum(1 for a in market_4 if a.role_tier == "informed")
    if informed_4 != expected_informed:
        errors.append("Market 4 informed count must match the treated-count rule.")

    return errors
