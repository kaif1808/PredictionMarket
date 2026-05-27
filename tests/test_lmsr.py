from __future__ import annotations

from server import lmsr


def test_price_at_origin_is_half() -> None:
    assert lmsr.price(0, 0, 10.0) == 0.5
    assert lmsr.price(0, 0, 25.0) == 0.5


def test_cost_positive_for_positive_purchase() -> None:
    assert lmsr.cost(0, 0, 1, 0, 10.0) > 0
    assert lmsr.cost(0, 0, 0, 1, 10.0) > 0


def test_price_after_between_zero_and_one() -> None:
    p = lmsr.price_after(5, 2, 3, 0, 10.0)
    assert 0 < p < 1


def test_price_symmetry() -> None:
    assert lmsr.price(10, 10, 5.0) == 0.5
    assert lmsr.price(1200, 1200, 20.0) == 0.5


def test_directional_effect() -> None:
    base = lmsr.price(0, 0, 10.0)
    assert lmsr.price_after(0, 0, 1, 0, 10.0) > base
    assert lmsr.price_after(0, 0, 0, 1, 10.0) < base


def test_max_purchasable_never_exceeds_balance() -> None:
    qty = lmsr.max_purchasable(0, 0, 15.0, "yes", 10.0)
    assert qty >= 0
    assert lmsr.cost(0, 0, qty, 0, 10.0) <= 15.0 + 1e-9
    assert lmsr.cost(0, 0, qty + 1, 0, 10.0) > 15.0 - 1e-9


def test_numerical_stability_large_q() -> None:
    p = lmsr.price(10000, 9999, 20.0)
    c = lmsr.cost(10000, 9999, 5, 0, 20.0)
    assert 0 < p < 1
    assert c > 0

