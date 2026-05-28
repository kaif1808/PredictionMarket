from __future__ import annotations

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


def _participant_index(participant_id: str) -> int:
    digits = "".join(ch for ch in participant_id if ch.isdigit())
    if digits:
        return max(int(digits), 1)
    return (sum(ord(ch) for ch in participant_id) % 16) + 1


def _rotated_position(rotation_id: int, participant_id: str, subject_count: int = 9) -> int:
    idx = _participant_index(participant_id) - 1
    return (idx + max(rotation_id - 1, 0)) % max(subject_count, 1)


def _informed_count_for_subjects(subject_count: int) -> int:
    # Default design is 3 informed slots in treated markets with 9 subjects.
    # For other subject counts, keep at least 6 uninformed slots when possible.
    return max(0, min(3, subject_count - 6))


def get_assignment(session_rotation_id: int, participant_id: str, market_number: int, subject_count: int = 9) -> MarketAssignment:
    pos = _rotated_position(session_rotation_id, participant_id, subject_count)
    informed_count = min(_informed_count_for_subjects(subject_count), subject_count)
    whale_slots = min(2, subject_count)

    if market_number == 1:
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 2:
        if pos < informed_count:
            return MarketAssignment(role_tier="informed", endowment_tokens=100.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 3:
        if pos < whale_slots:
            return MarketAssignment(role_tier="uninformed", endowment_tokens=400.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 4:
        informed_whale_count = min(whale_slots, informed_count)
        informed_normal_count = max(0, informed_count - informed_whale_count)
        if pos < informed_whale_count:
            return MarketAssignment(role_tier="informed", endowment_tokens=400.0)
        if pos < informed_whale_count + informed_normal_count:
            return MarketAssignment(role_tier="informed", endowment_tokens=100.0)
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
    expected_informed = _informed_count_for_subjects(n)
    if informed_2 != expected_informed:
        errors.append("Market 2 informed count must match the 3-treated default rule.")

    market_3 = rotation.get(3, [])
    whales_3 = sum(1 for a in market_3 if a.endowment_tokens == 400.0)
    expected_whales = min(2, n)
    if whales_3 != expected_whales:
        errors.append("Market 3 whale count must match the 2-whale default rule.")
    if any(a.role_tier != "uninformed" for a in market_3):
        errors.append("Market 3 must keep all participants uninformed.")

    market_4 = rotation.get(4, [])
    informed_whales_4 = sum(1 for a in market_4 if a.role_tier == "informed" and a.endowment_tokens == 400.0)
    if informed_whales_4 != min(expected_whales, expected_informed):
        errors.append("Market 4 informed-whale count must match the treated-whale rule.")
    informed_4 = sum(1 for a in market_4 if a.role_tier == "informed")
    if informed_4 != expected_informed:
        errors.append("Market 4 informed count must match the 3-treated default rule.")

    return errors
