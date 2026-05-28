from __future__ import annotations

import random

from server import bayesian
from server.roles import MarketAssignment


def test_draw_signal_frequency() -> None:
    rng = random.Random(123)
    draws = [bayesian.draw_signal(true_outcome=1, theta=0.85, rng=rng) for _ in range(20_000)]
    frac_h = draws.count("H") / len(draws)
    assert 0.83 < frac_h < 0.87


def test_posterior_monotonicity() -> None:
    p = 0.5
    p = bayesian.update_posterior(p, "H", 0.65)
    p2 = bayesian.update_posterior(p, "H", 0.65)
    assert p2 > p

    q = 0.5
    q = bayesian.update_posterior(q, "L", 0.65)
    q2 = bayesian.update_posterior(q, "L", 0.65)
    assert q2 < q


def test_posterior_converges_toward_truth() -> None:
    p = 0.5
    for _ in range(20):
        p = bayesian.update_posterior(p, "H", 0.85)
    assert p > 0.99


def test_benchmark_hand_check() -> None:
    benchmark = bayesian.benchmark_price(0.5, [("H", 0.85), ("L", 0.85), ("H", 0.85)])
    assert 0.5 < benchmark < 0.95


def test_draw_for_round_deterministic_seed() -> None:
    roles = [
        ("P01", MarketAssignment(role_tier="informed", endowment_tokens=100.0)),
        ("P02", MarketAssignment(role_tier="informed", endowment_tokens=100.0)),
    ]
    d1 = bayesian.draw_for_round(
        session_id=1, market_id=2, round_id=3, market_roles=roles, true_outcome=1, stage=2
    )
    d2 = bayesian.draw_for_round(
        session_id=1, market_id=2, round_id=3, market_roles=roles, true_outcome=1, stage=2
    )
    assert d1 == d2


def test_stage_1_drawn_but_not_delivered() -> None:
    roles = [("P01", MarketAssignment(role_tier="uninformed", endowment_tokens=100.0))]
    draws = bayesian.draw_for_round(
        session_id=1, market_id=1, round_id=1, market_roles=roles, true_outcome=1, stage=1
    )
    assert len(draws) == 1
    assert draws[0].delivered is False
