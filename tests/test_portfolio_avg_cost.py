from __future__ import annotations

from dataclasses import dataclass

import pytest

from server.portfolio import compute_market_avg_costs, compute_side_avg_cost


@dataclass(frozen=True)
class StubTrade:
    quantity: int
    cost: float


def test_avg_cost_pure_buys() -> None:
    trades = [
        StubTrade(quantity=2, cost=1.0),
        StubTrade(quantity=3, cost=1.8),
    ]
    out = compute_side_avg_cost(trades)  # type: ignore[arg-type]
    assert out.quantity == 5
    assert out.avg_cost is not None
    assert abs(out.avg_cost - 0.56) < 1e-9


def test_avg_cost_buy_buy_sell_keeps_running_average() -> None:
    trades = [
        StubTrade(quantity=2, cost=1.0),   # 0.50
        StubTrade(quantity=2, cost=1.2),   # 0.60
        StubTrade(quantity=1, cost=-0.7),  # sell 1, remove at running avg
    ]
    out = compute_side_avg_cost(trades)  # type: ignore[arg-type]
    assert out.quantity == 3
    assert out.avg_cost is not None
    assert abs(out.avg_cost - 0.55) < 1e-9


def test_avg_cost_full_liquidation_returns_none() -> None:
    trades = [
        StubTrade(quantity=2, cost=1.0),
        StubTrade(quantity=2, cost=-1.1),
    ]
    out = compute_side_avg_cost(trades)  # type: ignore[arg-type]
    assert out.quantity == 0
    assert out.avg_cost is None


def test_market_avg_costs_do_not_mix_sides() -> None:
    yes_trades = [StubTrade(quantity=2, cost=1.0)]
    no_trades = [StubTrade(quantity=3, cost=2.1)]
    yes_avg, no_avg = compute_market_avg_costs(yes_trades=yes_trades, no_trades=no_trades)  # type: ignore[arg-type]
    assert yes_avg == 0.5
    assert no_avg == pytest.approx(0.7)
