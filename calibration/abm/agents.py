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


def _parse_order_size_dist(spec: str) -> tuple[str, dict[str, float]]:
    head, *tail = [part.strip() for part in spec.split(",") if part.strip()]
    if not head:
        return "geometric", {"p": 0.68, "tail": 0.35}

    if ":" in head:
        name, first = head.split(":", 1)
        params: dict[str, float] = {}
        if "=" in first:
            key, value = first.split("=", 1)
            params[key.strip()] = float(value)
        else:
            params["p"] = float(first)
    else:
        name = head
        params = {}

    for raw in tail:
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        params[key.strip()] = float(value)

    return name.strip().lower(), params


def _sample_order_size(rng: random.Random, spec: str, *, max_qty: int) -> int:
    max_qty = max(1, min(20, int(max_qty)))
    name, params = _parse_order_size_dist(spec)

    if name in {"geometric", "geom"}:
        p = _clamp(params.get("p", 0.68), 1e-6, 0.999999)
        tail = _clamp(params.get("tail", 0.35), 0.0, 1.0)
        if rng.random() < tail:
            low = min(5, max_qty)
            return rng.randint(low, max_qty)
        u = max(1e-12, rng.random())
        draw = int(math.ceil(math.log(1 - u) / math.log(1 - p)))
        return max(1, min(max_qty, draw))

    if name in {"powerlaw", "zipf"}:
        alpha = max(1.01, params.get("alpha", 1.6))
        weights = [1.0 / (k**alpha) for k in range(1, max_qty + 1)]
        total = sum(weights)
        threshold = rng.random() * total
        acc = 0.0
        for idx, weight in enumerate(weights, start=1):
            acc += weight
            if acc >= threshold:
                return idx
        return max_qty

    return max(1, min(max_qty, rng.randint(1, max_qty)))


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
        event_index: int = 0,
    ) -> float:
        rng = random.Random(
            _seed(
                session_id=session_id,
                market_id=market_id,
                round_id=round_id,
                participant_id=self.participant_id,
                profile_name=self.profile.name,
                step=f"belief:{event_index}",
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
        yes_held: float = 0.0,
        no_held: float = 0.0,
        event_index: int = 0,
        edge_threshold: float = 0.02,
        sell_propensity: float = 0.42,
        order_size_dist: str = "geometric:p=0.68,tail=0.35",
    ) -> list[TradeRequest]:
        p = lmsr.price(q_yes, q_no, b)
        edge = self.belief - p
        abs_edge = abs(edge)
        if abs_edge < edge_threshold:
            return []

        buy_direction = "yes" if edge > 0 else "no"
        sell_direction = "no" if edge > 0 else "yes"
        sell_held = no_held if sell_direction == "no" else yes_held
        held_qty = max(0, int(math.floor(sell_held + 1e-9)))

        affordable = lmsr.max_purchasable(q_yes, q_no, balance, buy_direction, b)
        affordable_qty = max(0, int(math.floor(affordable)))

        risk_scale = max(0.0, 1.0 - self.profile.risk_aversion)
        edge_scale = min(1.0, abs_edge / 0.5)
        buy_score = risk_scale * edge_scale if affordable_qty > 0 else 0.0
        sell_score = sell_propensity * risk_scale * edge_scale if held_qty > 0 else 0.0
        if buy_score <= 0 and sell_score <= 0:
            return []

        rng = random.Random(
            _seed(
                session_id=session_id,
                market_id=market_id,
                round_id=round_id,
                participant_id=self.participant_id,
                profile_name=self.profile.name,
                step=f"decide:{event_index}",
            )
        )

        action_side = "buy"
        action_direction = buy_direction
        action_budget = affordable_qty
        if sell_propensity >= 1.0 and sell_score > 0:
            action_side = "sell"
            action_direction = sell_direction
            action_budget = held_qty
        elif buy_score > 0 and sell_score > 0:
            sell_prob = sell_score / (buy_score + sell_score)
            if rng.random() < sell_prob:
                action_side = "sell"
                action_direction = sell_direction
                action_budget = held_qty
        elif sell_score > 0:
            action_side = "sell"
            action_direction = sell_direction
            action_budget = held_qty

        if action_budget <= 0:
            return []

        activation = min(1.0, 0.55 + 0.45 * max(buy_score, sell_score))
        if rng.random() > activation:
            return []

        base_draw = _sample_order_size(rng, order_size_dist, max_qty=min(20, action_budget))
        jitter = 1.0 + self.profile.budget_variance * (rng.random() * 2.0 - 1.0)
        qty = int(round(base_draw * (0.60 + 1.80 * max(buy_score, sell_score)) * jitter))
        qty = max(1, min(action_budget, qty))

        chunks: list[TradeRequest] = []
        remaining = qty
        while remaining > 0:
            chunk = min(20, remaining)
            chunks.append(TradeRequest(side=action_side, direction=action_direction, quantity=chunk))
            remaining -= chunk
        return chunks
