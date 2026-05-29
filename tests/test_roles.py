from __future__ import annotations

from server.roles import MarketAssignment, get_assignment, get_market_config, get_scenario_for_market, validate_rotation_matrix


def test_stage_1_is_uninformed_and_100() -> None:
    a = get_assignment(1, 1, "P01", 1, subject_count=9)
    assert a.role_tier == "uninformed"
    assert a.endowment_tokens == 100.0


def test_market_2_has_three_informed_under_default_nine() -> None:
    rows = [get_assignment(1, 1, f"P{i:02d}", 2, subject_count=9) for i in range(1, 10)]
    informed = sum(1 for r in rows if r.role_tier == "informed")
    assert informed == 3


def test_market_3_whales() -> None:
    rows = [get_assignment(1, 1, f"P{i:02d}", 3, subject_count=9) for i in range(1, 10)]
    whales = sum(1 for r in rows if r.endowment_tokens == 400.0)
    assert whales == 3
    assert all(r.role_tier == "uninformed" for r in rows)


def test_scenario_assignment() -> None:
    assert get_scenario_for_market(1, 1) == "C"
    assert get_scenario_for_market(1, 4) == "D"


def test_market_config_uses_shared_b_parameter_across_stages() -> None:
    configs = [get_market_config(1, market_number, lmsr_b_parameter=19.5) for market_number in [1, 2, 3, 4]]
    assert all(c.b_parameter == 19.5 for c in configs)


def test_validate_rotation_matrix() -> None:
    good = {
        1: [MarketAssignment("uninformed", 100.0) for _ in range(9)],
        2: [MarketAssignment("informed", 100.0) for _ in range(3)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(6)],
        3: [MarketAssignment("uninformed", 400.0) for _ in range(3)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(6)],
        4: [MarketAssignment("informed", 400.0) for _ in range(3)]
        + [MarketAssignment("uninformed", 100.0) for _ in range(6)],
    }
    assert validate_rotation_matrix(good) == []

    bad = dict(good)
    bad[2] = [MarketAssignment("informed", 100.0) for _ in range(2)] + [MarketAssignment("uninformed", 100.0) for _ in range(7)]
    errs = validate_rotation_matrix(bad)
    assert any("Market 2" in e for e in errs)


def test_other_subject_sizes_are_supported() -> None:
    for subject_count in [9, 12]:
        rows_m2 = [get_assignment(1, 1, f"P{i:02d}", 2, subject_count=subject_count) for i in range(1, subject_count + 1)]
        rows_m3 = [get_assignment(1, 1, f"P{i:02d}", 3, subject_count=subject_count) for i in range(1, subject_count + 1)]
        rows_m4 = [get_assignment(1, 1, f"P{i:02d}", 4, subject_count=subject_count) for i in range(1, subject_count + 1)]
        assert sum(1 for r in rows_m2 if r.role_tier == "informed") == min(3, subject_count)
        assert sum(1 for r in rows_m3 if r.endowment_tokens == 400.0) == min(3, subject_count)
        assert sum(1 for r in rows_m4 if r.endowment_tokens == 400.0 and r.role_tier == "informed") == min(3, subject_count)


def test_default_randomized_treatment_not_fixed_to_first_three_ids() -> None:
    treated = {
        pid
        for pid in [f"P{i:02d}" for i in range(1, 10)]
        if get_assignment(1, 1, pid, 2, subject_count=9).role_tier == "informed"
    }
    assert treated != {"P01", "P02", "P03"}
