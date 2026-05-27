from __future__ import annotations

from server.roles import MarketAssignment, get_assignment, get_scenario_for_market, validate_rotation_matrix


def test_stage_1_is_uninformed_and_100() -> None:
    a = get_assignment(1, "P01", 1)
    assert a.role_tier == "uninformed"
    assert a.endowment_tokens == 100.0


def test_market_2_counts() -> None:
    rows = [get_assignment(1, f"P{i:02d}", 2) for i in range(1, 17)]
    insiders = sum(1 for r in rows if r.role_tier == "insider")
    semi = sum(1 for r in rows if r.role_tier == "semi_informed")
    assert insiders == 2
    assert semi == 4


def test_market_3_whales() -> None:
    rows = [get_assignment(1, f"P{i:02d}", 3) for i in range(1, 17)]
    whales = sum(1 for r in rows if r.endowment_tokens == 400.0)
    assert whales == 2
    assert all(r.role_tier == "uninformed" for r in rows)


def test_scenario_assignment() -> None:
    assert get_scenario_for_market(1, 1) == "C"
    assert get_scenario_for_market(1, 4) == "D"


def test_validate_rotation_matrix() -> None:
    good = {
        1: [MarketAssignment("uninformed", 100.0) for _ in range(16)],
        2: [MarketAssignment("insider", 100.0) for _ in range(2)]
        + [MarketAssignment("semi_informed", 100.0) for _ in range(4)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(10)],
        3: [MarketAssignment("uninformed", 400.0) for _ in range(2)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(14)],
        4: [MarketAssignment("insider", 400.0) for _ in range(2)]
        + [MarketAssignment("semi_informed", 100.0) for _ in range(4)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(10)],
    }
    assert validate_rotation_matrix(good) == []

    bad = dict(good)
    bad[2] = [MarketAssignment("insider", 100.0) for _ in range(3)] + bad[2][3:]
    errs = validate_rotation_matrix(bad)
    assert any("Market 2" in e for e in errs)

