from __future__ import annotations

from server.roles import MarketAssignment, get_assignment, get_market_config, get_scenario_for_market, validate_rotation_matrix


def test_stage_1_is_uninformed_and_100() -> None:
    a = get_assignment(1, "P01", 1)
    assert a.role_tier == "uninformed"
    assert a.endowment_tokens == 100.0


def test_market_2_counts() -> None:
    rows = [get_assignment(1, f"P{i:02d}", 2) for i in range(1, 17)]
    insiders = sum(1 for r in rows if r.role_tier == "insider")
    semi = sum(1 for r in rows if r.role_tier == "semi_informed")
    assert insiders == 2
    assert semi == 6


def test_market_3_whales() -> None:
    rows = [get_assignment(1, f"P{i:02d}", 3) for i in range(1, 17)]
    whales = sum(1 for r in rows if r.endowment_tokens == 400.0)
    assert whales == 2
    assert all(r.role_tier == "uninformed" for r in rows)


def test_scenario_assignment() -> None:
    assert get_scenario_for_market(1, 1) == "C"
    assert get_scenario_for_market(1, 4) == "D"


def test_market_config_uses_shared_b_parameter_across_stages() -> None:
    configs = [get_market_config(1, market_number, lmsr_b_parameter=19.5) for market_number in [1, 2, 3, 4]]
    assert all(c.b_parameter == 19.5 for c in configs)


def test_validate_rotation_matrix() -> None:
    good = {
        1: [MarketAssignment("uninformed", 100.0) for _ in range(16)],
        2: [MarketAssignment("insider", 100.0) for _ in range(2)]
        + [MarketAssignment("semi_informed", 100.0) for _ in range(6)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(8)],
        3: [MarketAssignment("uninformed", 400.0) for _ in range(2)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(14)],
        4: [MarketAssignment("insider", 400.0) for _ in range(2)]
        + [MarketAssignment("semi_informed", 100.0) for _ in range(6)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(8)],
    }
    assert validate_rotation_matrix(good) == []

    bad = dict(good)
    bad[2] = [MarketAssignment("insider", 100.0) for _ in range(3)] + bad[2][3:]
    errs = validate_rotation_matrix(bad)
    assert any("Market 2" in e for e in errs)


def test_each_participant_gets_at_least_two_role_tiers_across_four_markets() -> None:
    for subject_count in [8, 12, 16, 20]:
        for idx in range(1, subject_count + 1):
            pid = f"P{idx:02d}"
            tiers = {
                get_assignment(1, pid, market, subject_count=subject_count).role_tier
                for market in [1, 2, 3, 4]
            }
            assert len(tiers) >= 2


def test_informed_coverage_union_spans_all_participants() -> None:
    for subject_count in [8, 12, 16, 20]:
        informed_union = set()
        for idx in range(1, subject_count + 1):
            pid = f"P{idx:02d}"
            m2 = get_assignment(1, pid, 2, subject_count=subject_count).role_tier
            m4 = get_assignment(1, pid, 4, subject_count=subject_count).role_tier
            if m2 != "uninformed" or m4 != "uninformed":
                informed_union.add(pid)
        assert len(informed_union) == subject_count
