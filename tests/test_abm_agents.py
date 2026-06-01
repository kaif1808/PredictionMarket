from __future__ import annotations

import statistics

from server import lmsr

from calibration.abm.agents import Agent
from calibration.abm.profiles import BehavioralProfile


def _profile(name: str = "t", **overrides: float) -> BehavioralProfile:
    base = BehavioralProfile(
        name=name,
        risk_aversion=0.2,
        bias=0.0,
        stubbornness=0.0,
        expertise=1.0,
        market_imitation=0.0,
        budget_variance=0.0,
    )
    return BehavioralProfile(
        name=base.name,
        risk_aversion=overrides.get("risk_aversion", base.risk_aversion),
        bias=overrides.get("bias", base.bias),
        stubbornness=overrides.get("stubbornness", base.stubbornness),
        expertise=overrides.get("expertise", base.expertise),
        market_imitation=overrides.get("market_imitation", base.market_imitation),
        budget_variance=overrides.get("budget_variance", base.budget_variance),
    )


def test_market_init_bias_clamps() -> None:
    hi = Agent("P01", _profile(bias=0.9))
    hi.init_market()
    assert hi.belief == 0.99
    lo = Agent("P02", _profile(bias=-0.9))
    lo.init_market()
    assert lo.belief == 0.01


def test_stubbornness_one_keeps_belief_before_imitation() -> None:
    agent = Agent("P01", _profile(stubbornness=1.0, market_imitation=0.0))
    agent.belief = 0.62
    out = agent.update_belief(
        session_id=1,
        market_id=1,
        round_id=1,
        current_price=0.2,
        signal_value="H",
        signal_theta=0.85,
        signal_delivered=True,
        event_index=7,
    )
    assert out == 0.62


def test_market_imitation_one_equals_price_without_signal() -> None:
    agent = Agent("P01", _profile(market_imitation=1.0))
    agent.belief = 0.8
    out = agent.update_belief(
        session_id=1,
        market_id=1,
        round_id=2,
        current_price=0.37,
        signal_value=None,
        signal_theta=None,
        signal_delivered=False,
        event_index=4,
    )
    assert out == 0.37


def test_expertise_zero_flips_signal_deterministically() -> None:
    agent = Agent("P01", _profile(expertise=0.0))
    agent.belief = 0.5
    out = agent.update_belief(
        session_id=1,
        market_id=1,
        round_id=3,
        current_price=0.5,
        signal_value="H",
        signal_theta=0.85,
        signal_delivered=True,
        event_index=11,
    )
    assert out < 0.5


def test_decide_hold_when_edge_is_below_threshold() -> None:
    agent = Agent("P01", _profile(risk_aversion=0.0, budget_variance=0.0))
    agent.belief = 0.51
    assert (
        agent.decide(
            session_id=1,
            market_id=1,
            round_id=1,
            q_yes=0,
            q_no=0,
            b=36,
            balance=100,
            edge_threshold=0.02,
        )
        == []
    )


def test_decide_sell_path_requires_holdings() -> None:
    agent = Agent("P01", _profile(risk_aversion=0.0, budget_variance=0.0))
    agent.belief = 0.2
    without_holdings = agent.decide(
        session_id=7,
        market_id=3,
        round_id=2,
        q_yes=0,
        q_no=0,
        b=36,
        balance=100,
        yes_held=0,
        no_held=0,
        event_index=5,
        sell_propensity=1.0,
    )
    assert all(t.side == "buy" for t in without_holdings)

    with_holdings = []
    for event_index in range(1, 30):
        with_holdings = agent.decide(
            session_id=7,
            market_id=3,
            round_id=2,
            q_yes=0,
            q_no=0,
            b=36,
            balance=100,
            yes_held=25,
            no_held=0,
            event_index=event_index,
            sell_propensity=1.0,
        )
        if with_holdings:
            break
    assert with_holdings
    assert all(t.side == "sell" and t.direction == "yes" for t in with_holdings)
    assert sum(t.quantity for t in with_holdings) <= 25


def test_decide_never_exceeds_affordable_and_splits_to_20() -> None:
    agent = Agent("P01", _profile(risk_aversion=0.0, budget_variance=0.0))
    agent.belief = 0.99
    trades = agent.decide(
        session_id=9,
        market_id=2,
        round_id=4,
        q_yes=0,
        q_no=0,
        b=36,
        balance=10000,
        event_index=19,
        order_size_dist="powerlaw:alpha=1.01",
    )
    total_qty = sum(t.quantity for t in trades)
    affordable = lmsr.max_purchasable(0, 0, 10000, "yes", 36)
    assert total_qty <= affordable
    assert all(1 <= t.quantity <= 20 for t in trades)


def test_decide_small_order_heavy_distribution() -> None:
    agent = Agent("P01", _profile(risk_aversion=0.0, budget_variance=0.0))
    agent.belief = 0.99
    draws: list[int] = []
    for idx in range(1, 220):
        trades = agent.decide(
            session_id=12,
            market_id=4,
            round_id=3,
            q_yes=0,
            q_no=0,
            b=36,
            balance=500,
            event_index=idx,
            order_size_dist="geometric:p=0.8,tail=0.0",
        )
        if trades:
            draws.append(sum(t.quantity for t in trades))
    assert draws
    assert statistics.median(draws) <= 2


def test_decide_same_seed_and_event_is_identical() -> None:
    agent = Agent("P01", _profile(risk_aversion=0.3, budget_variance=0.5))
    agent.belief = 0.74
    first = agent.decide(
        session_id=2,
        market_id=8,
        round_id=5,
        q_yes=7,
        q_no=4,
        b=36,
        balance=121.5,
        yes_held=4,
        no_held=3,
        event_index=6,
    )
    second = agent.decide(
        session_id=2,
        market_id=8,
        round_id=5,
        q_yes=7,
        q_no=4,
        b=36,
        balance=121.5,
        yes_held=4,
        no_held=3,
        event_index=6,
    )
    assert [t.model_dump() for t in first] == [t.model_dump() for t in second]
