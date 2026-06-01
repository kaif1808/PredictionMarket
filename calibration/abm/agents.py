from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from server import bayesian, lmsr
from server.events import TradeRequest

from calibration.abm.profiles import BehavioralProfile


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _seed(
    *,
    session_id: int,
    market_id: int,
    round_id: int,
    participant_id: str,
    profile_name: str,
    step: str,
) -> str:
    material = f"{session_id}:{market_id}:{round_id}:{participant_id}:{profile_name}:{step}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass
class Agent:
    participant_id: str
    profile: BehavioralProfile
    belief: float = 0.5

    def init_market(self) -> None:
        self.belief = _clamp(0.5 + self.profile.bias, 0.01, 0.99)

    def update_belief(
        self,
        *,
        session_id: int,
        market_id: int,
        round_id: int,
        current_price: float,
        signal_value: str | None,
        signal_theta: float | None,
        signal_delivered: bool,
    ) -> float:
        rng = random.Random(
            _seed(
                session_id=session_id,
                market_id=market_id,
                round_id=round_id,
                participant_id=self.participant_id,
                profile_name=self.profile.name,
                step="belief",
            )
        )

        post = self.belief
        if signal_delivered and signal_value is not None and signal_theta is not None:
            theta_eff = _clamp(0.5 + (signal_theta - 0.5) * self.profile.expertise, 0.51, 0.99)
            realized_signal = signal_value
            if rng.random() > self.profile.expertise:
                realized_signal = "L" if signal_value == "H" else "H"
            raw_post = bayesian.update_posterior(prior=self.belief, signal=realized_signal, theta=theta_eff)
            post = self.belief + (1.0 - self.profile.stubbornness) * (raw_post - self.belief)

        self.belief = _clamp(post + self.profile.market_imitation * (current_price - post), 0.01, 0.99)
        return self.belief

    def decide(
        self,
        *,
        session_id: int,
        market_id: int,
        round_id: int,
        q_yes: float,
        q_no: float,
        b: float,
        balance: float,
    ) -> list[TradeRequest]:
        p = lmsr.price(q_yes, q_no, b)
        direction = "yes" if self.belief > p else "no"
        edge = abs(self.belief - p)
        if edge < 0.02:
            return []

        affordable = lmsr.max_purchasable(q_yes, q_no, balance, direction, b)
        if affordable <= 0:
            return []

        rng = random.Random(
            _seed(
                session_id=session_id,
                market_id=market_id,
                round_id=round_id,
                participant_id=self.participant_id,
                profile_name=self.profile.name,
                step="decide",
            )
        )
        size_frac = (1.0 - self.profile.risk_aversion) * min(1.0, edge / 0.5)
        jitter = 1.0 + self.profile.budget_variance * (rng.random() * 2.0 - 1.0)
        target_qty = int(math.floor(affordable * size_frac * jitter))
        target_qty = max(0, min(target_qty, affordable))
        if target_qty == 0:
            return []

        chunks: list[TradeRequest] = []
        remaining = target_qty
        while remaining > 0:
            qty = min(20, remaining)
            chunks.append(TradeRequest(direction=direction, quantity=qty))
            remaining -= qty
        return chunks
