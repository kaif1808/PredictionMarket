"""tests/test_abm_watch.py — Tests for calibration/abm/watch.py and the /abm/watch/run endpoint."""
from __future__ import annotations

import pytest

from calibration.abm.watch import run_single_market


# ---------------------------------------------------------------------------
# Test 1: Well-formed payload
# ---------------------------------------------------------------------------

def test_run_single_market_well_formed_payload() -> None:
    result = run_single_market(seed=42)

    # Top-level keys
    assert set(result.keys()) == {"market", "bots", "rounds", "trades"}

    market = result["market"]
    # Required market keys
    for key in (
        "true_probability",
        "outcome",
        "b",
        "round_duration_s",
        "subject_count",
        "scenario",
        "treated_count",
        "treated_share",
        "informed_count",
        "informed_share",
        "informed_only_count",
        "informed_whale_count",
        "whale_count",
        "whale_share",
        "whale_only_count",
        "overlap_count",
        "overlap_share",
        "uninformed_count",
        "uninformed_share",
    ):
        assert key in market, f"market missing key: {key}"

    # Outcome is binary
    assert market["outcome"] in (0, 1)

    # Default subject_count is 9
    assert len(result["bots"]) == market["subject_count"]
    assert market["subject_count"] == 9

    # Each bot has required keys
    for bot in result["bots"]:
        for key in ("id", "profile", "role_tier", "role_group", "is_informed", "is_whale", "risk_aversion"):
            assert key in bot, f"bot missing key: {key}"

    # Exactly 5 rounds
    assert len(result["rounds"]) == 5

    # Each round has required keys
    for rnd in result["rounds"]:
        for key in ("round_number", "opening_price", "closing_price", "benchmark", "duration_s"):
            assert key in rnd, f"round missing key: {key}"

    # Trades sorted by t_ms ascending
    trades = result["trades"]
    t_ms_list = [t["t_ms"] for t in trades]
    assert t_ms_list == sorted(t_ms_list)

    # Every trade has required keys
    for trade in trades:
        for key in ("side", "profile", "belief"):
            assert key in trade, f"trade missing key: {key}"

    # Default b is 36.0
    assert market["b"] == 36.0


# ---------------------------------------------------------------------------
# Test 2: Determinism — same seed → identical payload
# ---------------------------------------------------------------------------

def test_run_single_market_determinism() -> None:
    r1 = run_single_market(seed=99)
    r2 = run_single_market(seed=99)
    assert r1["trades"] == r2["trades"]
    assert r1["market"]["outcome"] == r2["market"]["outcome"]


# ---------------------------------------------------------------------------
# Test 3: Different seeds produce different results
# ---------------------------------------------------------------------------

def test_run_single_market_different_seeds_differ() -> None:
    r1 = run_single_market(seed=1)
    r2 = run_single_market(seed=2)
    # Trades must differ — the full event sequence is a function of the seed.
    # Outcome equality is NOT asserted: both seeds can legitimately draw the same
    # binary outcome from the same true_probability distribution.
    assert r1["trades"] != r2["trades"]


# ---------------------------------------------------------------------------
# Test 3b: market 2 true probability splits by seed-parity rotation
# ---------------------------------------------------------------------------

def test_run_single_market_market2_true_probability_splits_by_seed() -> None:
    odd_seed = run_single_market(seed=41, market_number=2)
    even_seed = run_single_market(seed=42, market_number=2)
    assert odd_seed["market"]["scenario"] != "market_default"
    assert even_seed["market"]["scenario"] != "market_default"
    assert odd_seed["market"]["true_probability"] != even_seed["market"]["true_probability"]


# ---------------------------------------------------------------------------
# Test 3c: Explicit scenario override drives true probability
# ---------------------------------------------------------------------------

def test_run_single_market_scenario_override() -> None:
    result = run_single_market(seed=42, market_number=2, scenario="very_no")
    assert result["market"]["scenario"] == "very_no"
    assert result["market"]["true_probability"] == 0.10


# ---------------------------------------------------------------------------
# Test 3d: Extended agent profile range is accepted
# ---------------------------------------------------------------------------

def test_run_single_market_extended_agent_profiles() -> None:
    result = run_single_market(
        seed=42,
        market_number=2,
        profile_mix="aggressive:2,cautious:2,contrarian:2,momentum:3",
    )
    profiles = {bot["profile"] for bot in result["bots"]}
    assert {"aggressive", "cautious", "contrarian", "momentum"}.issubset(profiles)


# ---------------------------------------------------------------------------
# Test 3e: Exact bucket counts are honored
# ---------------------------------------------------------------------------

def test_run_single_market_explicit_bucket_counts_are_honored() -> None:
    result = run_single_market(
        seed=42,
        market_number=2,
        subject_count=9,
        informed_only_count=3,
        informed_whale_count=3,
        whale_only_count=3,
    )

    assert result["market"]["informed_only_count"] == 3
    assert result["market"]["informed_whale_count"] == 3
    assert result["market"]["whale_only_count"] == 3
    assert result["market"]["informed_count"] == 6
    assert result["market"]["whale_count"] == 6
    assert result["market"]["overlap_count"] == 3
    assert result["market"]["uninformed_count"] == 0

    informed_only = sum(1 for b in result["bots"] if b["role_group"] == "informed")
    overlap = sum(1 for b in result["bots"] if b["role_group"] == "informed_whale")
    whale_only = sum(1 for b in result["bots"] if b["role_group"] == "whale")
    uninformed = sum(1 for b in result["bots"] if b["role_group"] == "uninformed")
    assert informed_only == 3
    assert overlap == 3
    assert whale_only == 3
    assert uninformed == 0


def test_run_single_market_rejects_bucket_overflow() -> None:
    with pytest.raises(ValueError):
        run_single_market(
            seed=42,
            market_number=2,
            subject_count=9,
            informed_only_count=4,
            informed_whale_count=3,
            whale_only_count=3,
        )


# ---------------------------------------------------------------------------
# Test 4: market_number validation
# ---------------------------------------------------------------------------

def test_run_single_market_invalid_market_number() -> None:
    with pytest.raises(ValueError):
        run_single_market(market_number=5)
    with pytest.raises(ValueError):
        run_single_market(market_number=0)


# ---------------------------------------------------------------------------
# Test 5: on_trade=None unchanged — regression guard for batch runner
# ---------------------------------------------------------------------------

def test_run_abm_unchanged() -> None:
    from calibration.abm.runner import run_abm
    from calibration.abm.config import SimConfig

    config = SimConfig(
        seed=42,
        subject_count=4,
        treated_count=2,
        b=36.0,
        num_sessions=1,
        include_practice=False,
    ).validated()
    result = run_abm(config)
    assert len(result.session_ids) == 1


# ---------------------------------------------------------------------------
# Test 6: Backend endpoint smoke test
# ---------------------------------------------------------------------------

def test_abm_watch_endpoint_smoke() -> None:
    from fastapi.testclient import TestClient
    from server.server import fastapi_app

    client = TestClient(fastapi_app)
    resp = client.get(
        "/abm/watch/run",
        params={
            "seed": "42",
            "subject_count": "4",
            "market_number": "2",
            "b": "36.0",
            "informed_only_count": "1",
            "informed_whale_count": "1",
            "whale_only_count": "1",
            "reaction_delay_s": "0.9",
            "reaction_delay_jitter_s": "0.0",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) >= {"market", "bots", "rounds", "trades"}
    assert data["market"]["outcome"] in (0, 1)
    if data["trades"]:
        assert min(t["event_time_s"] for t in data["trades"]) >= 0.9


# ---------------------------------------------------------------------------
# Test 7: Invalid endpoint params → 422
# ---------------------------------------------------------------------------

def test_abm_watch_endpoint_invalid_params() -> None:
    from fastapi.testclient import TestClient
    from server.server import fastapi_app

    client = TestClient(fastapi_app)
    resp = client.get("/abm/watch/run", params={"market_number": "9"})
    assert resp.status_code == 422
