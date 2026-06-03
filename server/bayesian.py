from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from random import Random
from typing import Literal

from server.roles import MarketAssignment

SignalValue = Literal["S+", "M+", "N", "M-", "S-"]
SIGNAL_SCORE: dict[SignalValue, int] = {
    "S+": 2,
    "M+": 1,
    "N": 0,
    "M-": -1,
    "S-": -2,
}

SIGNAL_ORDER: tuple[SignalValue, ...] = ("S+", "M+", "N", "M-", "S-")


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
    if true_outcome not in (0, 1):
        raise ValueError("true_outcome must be 0 or 1")
    alpha = math.log(theta / (1.0 - theta)) / 4.0
    direction = 1.0 if true_outcome == 1 else -1.0
    weights = [math.exp(direction * alpha * SIGNAL_SCORE[s]) for s in SIGNAL_ORDER]
    total = sum(weights)
    cutoff = rng.random() * total
    cumulative = 0.0
    for signal, weight in zip(SIGNAL_ORDER, weights, strict=True):
        cumulative += weight
        if cutoff <= cumulative:
            return signal
    return SIGNAL_ORDER[-1] if true_outcome == 1 else SIGNAL_ORDER[0]


def update_posterior(prior: float, signal: SignalValue, theta: float) -> float:
    if not 0.0 < prior < 1.0:
        raise ValueError("prior must be in (0,1)")
    if theta <= 0.5 or theta >= 1.0:
        raise ValueError("theta must be in (0.5,1.0)")
    if signal not in SIGNAL_SCORE:
        raise ValueError(f"unknown signal value {signal}")

    alpha = math.log(theta / (1.0 - theta)) / 4.0
    lr = math.exp(2.0 * alpha * SIGNAL_SCORE[signal])
    num = prior * lr
    den = num + (1.0 - prior)
    return num / den


def informed_signal_theta(true_probability: float) -> float:
    if not 0.0 <= true_probability <= 1.0:
        raise ValueError("true_probability must be in [0,1]")
    if true_probability <= 0.2 or true_probability >= 0.8:
        return 0.65
    if true_probability <= 0.35 or true_probability >= 0.65:
        return 0.72
    return 0.85


def benchmark_price(prior: float, all_signals: list[tuple[str, float]]) -> float:
    if not 0.0 < prior < 1.0:
        raise ValueError("prior must be in (0,1)")
    log_odds = math.log(prior / (1.0 - prior))
    for signal_value, theta in all_signals:
        if theta <= 0.5 or theta >= 1.0:
            raise ValueError(f"invalid theta={theta}")
        if signal_value not in SIGNAL_SCORE:
            raise ValueError(f"unknown signal value {signal_value}")
        alpha = math.log(theta / (1.0 - theta)) / 4.0
        lr = math.exp(2.0 * alpha * SIGNAL_SCORE[signal_value])
        log_odds += math.log(lr)
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
    true_probability: float,
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
            theta = informed_signal_theta(true_probability)
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
