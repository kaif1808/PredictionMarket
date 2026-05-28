from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from random import Random
from typing import Literal

from server.roles import MarketAssignment

SignalValue = Literal["H", "L"]


@dataclass(frozen=True)
class SignalDraw:
    participant_id: str
    value: SignalValue
    theta: float
    posterior: float
    delivered: bool
    seed: str


def draw_signal(true_outcome: int, theta: float, rng: Random) -> SignalValue:
    if theta <= 0.5 or theta >= 1.0:
        raise ValueError("theta must be in (0.5, 1.0)")
    p_h = theta if true_outcome == 1 else 1.0 - theta
    return "H" if rng.random() < p_h else "L"


def update_posterior(prior: float, signal: SignalValue, theta: float) -> float:
    if not 0.0 < prior < 1.0:
        raise ValueError("prior must be in (0,1)")
    if theta <= 0.5 or theta >= 1.0:
        raise ValueError("theta must be in (0.5,1.0)")

    if signal == "H":
        num = prior * theta
        den = num + (1.0 - prior) * (1.0 - theta)
    else:
        num = prior * (1.0 - theta)
        den = num + (1.0 - prior) * theta
    return num / den


def benchmark_price(prior: float, all_signals: list[tuple[str, float]]) -> float:
    if not 0.0 < prior < 1.0:
        raise ValueError("prior must be in (0,1)")
    log_odds = math.log(prior / (1.0 - prior))
    for signal_value, theta in all_signals:
        if signal_value == "H":
            log_odds += math.log(theta / (1.0 - theta))
        elif signal_value == "L":
            log_odds += math.log((1.0 - theta) / theta)
        else:
            raise ValueError(f"unknown signal value {signal_value}")
    if log_odds >= 0:
        z = math.exp(-log_odds)
        return 1.0 / (1.0 + z)
    z = math.exp(log_odds)
    return z / (1.0 + z)


def _seed_for(session_id: int, market_id: int, round_id: int, participant_id: str) -> str:
    raw = f"{session_id}:{market_id}:{round_id}:{participant_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _assignment_from_any(market_role: object) -> tuple[str, MarketAssignment]:
    if isinstance(market_role, tuple) and len(market_role) == 2:
        pid = str(market_role[0])
        assignment = market_role[1]
        if isinstance(assignment, MarketAssignment):
            return pid, assignment
    if isinstance(market_role, dict):
        pid = str(market_role["participant_id"])
        role_tier = str(market_role["role_tier"])
        endowment = float(market_role.get("endowment_tokens", 100.0))
        return pid, MarketAssignment(role_tier=role_tier, endowment_tokens=endowment)
    raise TypeError("market_roles must contain (participant_id, MarketAssignment) or dict objects")


def draw_for_round(
    session_id: int,
    market_id: int,
    round_id: int,
    market_roles: list[object],
    true_outcome: int,
    stage: int,
    prior_by_participant: dict[str, float] | None = None,
) -> list[SignalDraw]:
    draws: list[SignalDraw] = []
    priors = prior_by_participant or {}

    for role_item in market_roles:
        participant_id, assignment = _assignment_from_any(role_item)
        role = assignment.role_tier
        if stage == 1:
            theta = 0.65
            delivered = False
        elif role == "informed":
            theta = 0.85
            delivered = True
        else:
            continue

        seed = _seed_for(session_id, market_id, round_id, participant_id)
        rng = random.Random(seed)
        value = draw_signal(true_outcome=true_outcome, theta=theta, rng=rng)
        prior = priors.get(participant_id, 0.5)
        posterior = update_posterior(prior=prior, signal=value, theta=theta)
        priors[participant_id] = posterior

        draws.append(
            SignalDraw(
                participant_id=participant_id,
                value=value,
                theta=theta,
                posterior=posterior,
                delivered=delivered,
                seed=seed,
            )
        )
    return draws
