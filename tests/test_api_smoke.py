from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import DebriefResponse, ParticipantSession
from server.server import fastapi_app


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

    close = client.post(f"/admin/sessions/{session_id}/close", auth=auth)
    assert close.status_code == 200

    debrief = client.post("/debrief/submit", json={"answers": {"strategy": "trend following"}})
    assert debrief.status_code == 200
