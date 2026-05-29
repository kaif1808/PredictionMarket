import pytest
import random
from server.scenarios import PRIMING_POOLS, build_priming_bulletin, get_priming_bulletin

SLOT_ORDER = ("wire", "social", "official", "tabloid", "analyst", "markets", "intel", "field")


def test_all_scenarios_present():
    for sid in ("A", "B", "C", "D"):
        assert sid in PRIMING_POOLS, f"scenario {sid} missing from PRIMING_POOLS"


def test_all_slots_have_minimum_two_candidates():
    for sid, pool in PRIMING_POOLS.items():
        for slot in SLOT_ORDER:
            cands = pool["slots"][slot]["candidates"]
            assert len(cands) >= 2, f"{sid}.{slot} needs ≥2 candidates, got {len(cands)}"


def test_built_bulletin_has_eight_sources_correct_tier_counts():
    b = build_priming_bulletin("A", random.Random(42))
    assert len(b["sources"]) == 8
    tiers = [s["tier"] for s in b["sources"]]
    assert tiers.count("public") == 4
    assert tiers.count("analytical") == 2
    assert tiers.count("intelligence") == 2


def test_gating_stage1_returns_only_public():
    b = get_priming_bulletin("A", role_tier="informed", stage=1, seed="s1:m1:priming")
    assert all(s["tier"] == "public" for s in b["sources"])
    assert len(b["sources"]) == 4


def test_gating_uninformed_returns_only_public():
    b = get_priming_bulletin("A", role_tier="uninformed", stage=2, seed="s1:m1:priming")
    assert all(s["tier"] == "public" for s in b["sources"])
    assert len(b["sources"]) == 4


def test_gating_informed_stage2_returns_all_eight():
    b = get_priming_bulletin("A", role_tier="informed", stage=2, seed="s1:m1:priming")
    assert len(b["sources"]) == 8


def test_bad_scenario_raises():
    with pytest.raises(ValueError, match="scenario_id"):
        get_priming_bulletin("Z", role_tier="informed", stage=2, seed="x")


def test_bad_role_tier_raises():
    with pytest.raises(ValueError, match="role_tier"):
        get_priming_bulletin("A", role_tier="whale", stage=2, seed="x")


def test_determinism_same_seed_same_result():
    seed = "3:17:priming"
    b1 = get_priming_bulletin("A", role_tier="informed", stage=2, seed=seed)
    b2 = get_priming_bulletin("A", role_tier="informed", stage=2, seed=seed)
    assert b1 == b2


def test_variety_different_seeds_produce_different_texts():
    texts = {
        get_priming_bulletin("A", role_tier="informed", stage=2, seed=f"{i}:{i}:priming")["sources"][0]["text"]
        for i in range(20)
    }
    assert len(texts) > 1, "Expected variety across seeds for wire slot"


def test_composition_bands_public_subset():
    expected = {"A": (3, 1), "B": (1, 3), "C": (2, 2), "D": (3, 1)}
    for sid, (exp_yes, exp_no) in expected.items():
        b = get_priming_bulletin(sid, role_tier="uninformed", stage=2, seed="test")
        yes = sum(1 for s in b["sources"] if s["lean"] == "yes")
        no  = sum(1 for s in b["sources"] if s["lean"] == "no")
        assert yes == exp_yes, f"{sid}: expected {exp_yes} yes sources, got {yes}"
        assert no  == exp_no,  f"{sid}: expected {exp_no} no sources, got {no}"


def test_at_least_one_contrarian_in_full_bulletin():
    for sid in ("A", "B", "C", "D"):
        b = get_priming_bulletin(sid, role_tier="informed", stage=2, seed="test")
        leans = [s["lean"] for s in b["sources"]]
        assert "yes" in leans and "no" in leans, f"{sid}: missing contrarian source"
