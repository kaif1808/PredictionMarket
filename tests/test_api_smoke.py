from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import DebriefResponse, Market, ParticipantSession, SessionModel
from server.server import fastapi_app, orchestrator


def test_create_session_defaults_subject_count_to_9() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "default-subject-count", "rotation_id": 1},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with SessionLocal() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.show_tournament_payout_screen is True
        assert session_row.treated_count == 3
        rows = db.scalars(
            select(ParticipantSession).where(ParticipantSession.session_id == session_id)
        ).all()
    assert len(rows) == 9


def test_create_session_liquidity_defaults_to_36_and_new_market_inherits() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "default-liquidity", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with SessionLocal() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.lmsr_b_parameter == Decimal("36")

    start_market = client.post(
        f"/admin/sessions/{session_id}/markets",
        auth=auth,
        json={"market_number": 1},
    )
    assert start_market.status_code == 200

    with SessionLocal() as db:
        market = db.scalar(
            select(Market).where(Market.session_id == session_id, Market.market_number == 1)
        )
        assert market is not None
        assert market.b_parameter == Decimal("36")


def test_create_session_liquidity_override_is_stored_and_used_for_market() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "custom-liquidity", "rotation_id": 1, "subject_count": 8, "lmsr_b_parameter": 12.5},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with SessionLocal() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.lmsr_b_parameter == Decimal("12.5")

    previous_default = orchestrator.lmsr_b_parameter
    try:
        # Simulate a changed process-level default after session creation.
        orchestrator.lmsr_b_parameter = 999.0
        start_market = client.post(
            f"/admin/sessions/{session_id}/markets",
            auth=auth,
            json={"market_number": 1},
        )
    finally:
        orchestrator.lmsr_b_parameter = previous_default
    assert start_market.status_code == 200

    with SessionLocal() as db:
        market = db.scalar(
            select(Market).where(Market.session_id == session_id, Market.market_number == 1)
        )
        assert market is not None
        assert market.b_parameter == Decimal("12.5")


def test_create_session_can_disable_tournament_payout_screen_and_exposes_state_flag() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={
            "label": "no-payout-screen",
            "rotation_id": 1,
            "subject_count": 8,
            "show_tournament_payout_screen": False,
        },
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with SessionLocal() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.show_tournament_payout_screen is False
        ps = db.scalar(
            select(ParticipantSession).where(
                ParticipantSession.session_id == session_id,
                ParticipantSession.participant_id == "P01",
            )
        )
        assert ps is not None
        token = ps.join_token
        assert token is not None

    join = client.post("/auth/join", json={"join_token": token})
    assert join.status_code == 200

    state = client.get("/state")
    assert state.status_code == 200
    assert state.json()["show_tournament_payout_screen"] is False


def test_create_session_rejects_non_positive_liquidity() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    for invalid_value in (0, -1):
        create = client.post(
            "/admin/sessions",
            auth=auth,
            json={"label": "invalid-liquidity", "rotation_id": 1, "subject_count": 8, "lmsr_b_parameter": invalid_value},
        )
        assert create.status_code == 422


def test_create_session_treated_count_override_is_stored_and_used() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "treated-override", "rotation_id": 1, "subject_count": 9, "treated_count": 4},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    with SessionLocal() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.treated_count == 4

    start_market = client.post(
        f"/admin/sessions/{session_id}/markets",
        auth=auth,
        json={"market_number": 2},
    )
    assert start_market.status_code == 200

    participants = client.get(f"/admin/sessions/{session_id}/participants", auth=auth).json()
    informed_count = sum(
        1
        for row in participants
        if row["markets"].get("2", {}).get("information_treated") is True
    )
    assert informed_count == 4


def test_create_session_rejects_invalid_treated_count_bounds() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    too_low = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "treated-low", "rotation_id": 1, "subject_count": 9, "treated_count": 1},
    )
    assert too_low.status_code == 422

    too_high = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "treated-high", "rotation_id": 1, "subject_count": 9, "treated_count": 10},
    )
    assert too_high.status_code == 422


def test_session_happy_path_smoke() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "pytest-smoke", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    start_market = client.post(
        f"/admin/sessions/{session_id}/markets",
        auth=auth,
        json={"market_number": 1},
    )
    assert start_market.status_code == 200

    start_round = client.post(
        f"/admin/sessions/{session_id}/rounds",
        auth=auth,
        json={"round_number": 1},
    )
    assert start_round.status_code == 200

    with SessionLocal() as db:
        ps = db.scalar(
            select(ParticipantSession).where(
                ParticipantSession.session_id == session_id,
                ParticipantSession.participant_id == "P01",
            )
        )
        assert ps is not None
        token = ps.join_token
        assert token is not None

    join = client.post("/auth/join", json={"join_token": token})
    assert join.status_code == 200
    set_cookie = join.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie or "samesite=lax" in set_cookie.lower()
    reused = client.post("/auth/join", json={"join_token": token})
    assert reused.status_code == 404

    trade = client.post("/trade", json={"direction": "yes", "quantity": 1})
    assert trade.status_code == 200

    quiz = client.post(
        "/quiz/comprehension/submit",
        json={"attempts": 1, "final_correct": True, "raw_answers": {"q1": "A"}},
    )
    assert quiz.status_code == 200

    risk = client.post(
        "/risk_elicitation/submit",
        json={"instrument": "holt_laury_10", "switch_point": 4, "raw_choices": {"rows": [1, 1, 1, 0]}},
    )
    assert risk.status_code == 200

    consent_flow = client.post(
        "/flow_step",
        json={"flow_step": "instructions", "metadata": {"consented": True, "name": "Test User"}},
    )
    assert consent_flow.status_code == 200
    with SessionLocal() as db:
        debrief_seed = db.scalar(
            select(DebriefResponse).where(
                DebriefResponse.session_id == session_id,
                DebriefResponse.participant_id == "P01",
            )
        )
        assert debrief_seed is not None
        assert debrief_seed.answers.get("consent", {}).get("consented") is True

    end_round = client.post(
        f"/admin/sessions/{session_id}/rounds/1/end",
        auth=auth,
    )
    assert end_round.status_code == 200
    assert end_round.json()["round_volume"] == 1

    export_csv = client.get(f"/admin/sessions/{session_id}/export.csv", auth=auth)
    assert export_csv.status_code == 200
    assert "trade_id" in export_csv.text

    export_json = client.get(f"/admin/sessions/{session_id}/export.json", auth=auth)
    assert export_json.status_code == 200
    assert export_json.json()["session"]["id"] == session_id
    assert export_json.json()["session"]["treated_count"] == 3

    close = client.post(f"/admin/sessions/{session_id}/close", auth=auth)
    assert close.status_code == 200

    debrief = client.post(
        "/debrief/submit",
        json={
            "answers": {
                "strategy": "trend following",
                "experimental_economics": "no",
                "prediction_market_literature": "yes",
                "prediction_market_use": "no",
            }
        },
    )
    assert debrief.status_code == 200


def test_start_round_invalid_phase_returns_400() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "invalid-phase", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]
    start_round = client.post(
        f"/admin/sessions/{session_id}/rounds",
        auth=auth,
        json={"round_number": 1},
    )
    assert start_round.status_code == 400
    assert start_round.json()["detail"] == "Cannot start round from current phase"


def test_admin_participants_include_actual_treatment_only_for_started_markets() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "participants-treatment", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    before_start = client.get(f"/admin/sessions/{session_id}/participants", auth=auth)
    assert before_start.status_code == 200
    before_rows = before_start.json()
    assert len(before_rows) == 8
    assert all(row["markets"] == {} for row in before_rows)

    start_market = client.post(
        f"/admin/sessions/{session_id}/markets",
        auth=auth,
        json={"market_number": 1},
    )
    assert start_market.status_code == 200

    after_start = client.get(f"/admin/sessions/{session_id}/participants", auth=auth)
    assert after_start.status_code == 200
    for row in after_start.json():
        assert "1" in row["markets"]
        assert "2" not in row["markets"]
        market1 = row["markets"]["1"]
        assert set(market1.keys()) == {
            "role_tier",
            "endowment_tokens",
            "information_treated",
            "endowment_treated",
            "treated",
        }
        assert market1["information_treated"] == (market1["role_tier"] != "uninformed")
        assert market1["endowment_treated"] == (market1["endowment_tokens"] > 100)
        assert market1["treated"] == (market1["information_treated"] or market1["endowment_treated"])
