from __future__ import annotations

import math


def _validate_b(b: float) -> None:
    if b <= 0:
        raise ValueError("b must be > 0")


def _cost_function(q_yes: float, q_no: float, b: float) -> float:
    _validate_b(b)
    a = q_yes / b
    c = q_no / b
    m = max(a, c)
    return b * (m + math.log(math.exp(a - m) + math.exp(c - m)))


def price(q_yes: float, q_no: float, b: float) -> float:
    _validate_b(b)
    diff = (q_yes - q_no) / b
    if diff >= 0:
        z = math.exp(-diff)
        return 1.0 / (1.0 + z)
    z = math.exp(diff)
    return z / (1.0 + z)


def cost(q_yes: float, q_no: float, d_yes: float, d_no: float, b: float) -> float:
    before = _cost_function(q_yes, q_no, b)
    after = _cost_function(q_yes + d_yes, q_no + d_no, b)
    return after - before


def price_after(q_yes: float, q_no: float, d_yes: float, d_no: float, b: float) -> float:
    return price(q_yes + d_yes, q_no + d_no, b)


def price_impact(q_yes: float, q_no: float, d_yes: float, d_no: float, b: float) -> float:
    return price_after(q_yes, q_no, d_yes, d_no, b) - price(q_yes, q_no, b)


def max_purchasable(q_yes: float, q_no: float, balance: float, direction: str, b: float) -> int:
    if balance <= 0:
        return 0
    if direction not in {"yes", "no"}:
        raise ValueError("direction must be yes or no")
    lo, hi = 0, 1
    while True:
        d_yes = float(hi) if direction == "yes" else 0.0
        d_no = float(hi) if direction == "no" else 0.0
        c = cost(q_yes, q_no, d_yes, d_no, b)
        if c > balance:
            break
        hi *= 2
        if hi > 1_000_000:
            break
    while lo < hi:
        mid = (lo + hi + 1) // 2
        d_yes = float(mid) if direction == "yes" else 0.0
        d_no = float(mid) if direction == "no" else 0.0
        c = cost(q_yes, q_no, d_yes, d_no, b)
        if c <= balance:
            lo = mid
        else:
            hi = mid - 1
    return lo

