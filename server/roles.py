from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


RoleTier = Literal["uninformed", "semi_informed", "insider"]


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


def _rotated_position(rotation_id: int, participant_id: str, subject_count: int = 16) -> int:
    idx = _participant_index(participant_id) - 1
    return (idx + max(rotation_id - 1, 0)) % max(subject_count, 1)


def _semi_count_for_subjects(subject_count: int) -> int:
    # Ensure full participant coverage across markets 2 and 4:
    # each participant must receive at least one informed role tier.
    informed_slots = math.ceil(subject_count / 2)
    semi = max(informed_slots - 2, 2)
    return semi


def get_assignment(session_rotation_id: int, participant_id: str, market_number: int, subject_count: int = 16) -> MarketAssignment:
    pos = _rotated_position(session_rotation_id, participant_id, subject_count)
    semi_count = _semi_count_for_subjects(subject_count)
    info_slots = 2 + semi_count

    if market_number == 1:
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 2:
        if pos < 2:
            return MarketAssignment(role_tier="insider", endowment_tokens=100.0)
        if pos < info_slots:
            return MarketAssignment(role_tier="semi_informed", endowment_tokens=100.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 3:
        if pos < 2:
            return MarketAssignment(role_tier="uninformed", endowment_tokens=400.0)
        return MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)

    if market_number == 4:
        start = max(subject_count - info_slots, 0)
        local_pos = pos - start
        if local_pos >= 0 and local_pos < 2:
            return MarketAssignment(role_tier="insider", endowment_tokens=400.0)
        if local_pos >= 0 and local_pos < info_slots:
            return MarketAssignment(role_tier="semi_informed", endowment_tokens=100.0)
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
    insiders_2 = sum(1 for a in market_2 if a.role_tier == "insider")
    semi_2 = sum(1 for a in market_2 if a.role_tier == "semi_informed")
    if insiders_2 != 2:
        errors.append("Market 2 must contain exactly 2 insiders.")
    expected_info_slots = math.ceil(n / 2) if n > 0 else 0
    if semi_2 != max(expected_info_slots - 2, 2):
        errors.append("Market 2 semi_informed count must match subject-count coverage rule.")

    market_3 = rotation.get(3, [])
    whales_3 = sum(1 for a in market_3 if a.endowment_tokens == 400.0)
    if whales_3 != 2:
        errors.append("Market 3 must contain exactly 2 whales with 400-token endowment.")
    if any(a.role_tier != "uninformed" for a in market_3):
        errors.append("Market 3 must keep all participants uninformed.")

    market_4 = rotation.get(4, [])
    insider_whales = sum(1 for a in market_4 if a.role_tier == "insider" and a.endowment_tokens == 400.0)
    if insider_whales != 2:
        errors.append("Market 4 must contain exactly 2 insider-whales.")
    semi_4 = sum(1 for a in market_4 if a.role_tier == "semi_informed")
    if semi_4 != max(expected_info_slots - 2, 2):
        errors.append("Market 4 semi_informed count must match subject-count coverage rule.")

    return errors
