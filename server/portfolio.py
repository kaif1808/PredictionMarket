from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from server.db_models import Trade


@dataclass(frozen=True)
class SideCostBasis:
    quantity: float
    avg_cost: float | None


def _apply_trade(
    quantity: float,
    cost_pool: float,
    trade_quantity: float,
    trade_cost: float,
) -> tuple[float, float]:
    if trade_cost >= 0:
        return quantity + trade_quantity, cost_pool + trade_cost

    if quantity <= 0:
        return 0.0, 0.0

    reduce_qty = min(trade_quantity, quantity)
    avg_cost = cost_pool / quantity if quantity > 0 else 0.0
    next_quantity = quantity - reduce_qty
    next_cost_pool = cost_pool - (avg_cost * reduce_qty)
    if next_quantity <= 1e-9:
        return 0.0, 0.0
    return next_quantity, max(0.0, next_cost_pool)


def compute_side_avg_cost(trades: Iterable[Trade]) -> SideCostBasis:
    quantity = 0.0
    cost_pool = 0.0

    for trade in trades:
        qty = float(trade.quantity)
        cost = float(trade.cost)
        quantity, cost_pool = _apply_trade(quantity, cost_pool, qty, cost)

    if quantity <= 1e-9:
        return SideCostBasis(quantity=0.0, avg_cost=None)
    return SideCostBasis(quantity=quantity, avg_cost=cost_pool / quantity)


def compute_market_avg_costs(
    yes_trades: Iterable[Trade],
    no_trades: Iterable[Trade],
) -> tuple[float | None, float | None]:
    yes = compute_side_avg_cost(yes_trades)
    no = compute_side_avg_cost(no_trades)
    return yes.avg_cost, no.avg_cost
