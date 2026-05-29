from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlalchemy import select

import server.server as server_module
from server.db import SessionLocal
from server.db_models import ParticipantSession
from server.server import fastapi_app


def _join_token(session_id: int, participant_id: str) -> str:
    with SessionLocal() as db:
        ps = db.scalar(
            select(ParticipantSession).where(
                ParticipantSession.session_id == session_id,
                ParticipantSession.participant_id == participant_id,
            )
        )
        assert ps is not None and ps.join_token
        return ps.join_token


def test_practice_round_auto_closes_and_returns_to_session_open(monkeypatch) -> None:
    admin = TestClient(fastapi_app)
    participant = TestClient(fastapi_app)
    auth = ("admin", "admin")

    monkeypatch.setattr(server_module, "PRACTICE_ROUND_DURATION_SECONDS", 1)

    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "practice-auto-close", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    token = _join_token(sid, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200

    start = admin.post(f"/admin/sessions/{sid}/practice_round", auth=auth)
    assert start.status_code == 200

    state_open = participant.get("/state")
    assert state_open.status_code == 200
    payload_open = state_open.json()
    assert payload_open["phase"] == "round_open"
    assert payload_open["is_practice_round"] is True
    assert payload_open["round_duration_seconds"] == 1
    assert payload_open["flow_step"] == "market-practice"

    time.sleep(1.4)

    state_closed = participant.get("/state")
    assert state_closed.status_code == 200
    payload_closed = state_closed.json()
    assert payload_closed["phase"] == "session_open"
    assert payload_closed["current_market_number"] is None
    assert payload_closed["current_round_number"] is None
    assert payload_closed["round_deadline_unix_ms"] is None
    assert payload_closed["is_practice_round"] is False
    assert payload_closed["flow_step"] == "lobby"


def test_practice_round_excluded_from_default_dashboard_and_exports(monkeypatch) -> None:
    admin = TestClient(fastapi_app)
    participant = TestClient(fastapi_app)
    auth = ("admin", "admin")

    monkeypatch.setattr(server_module, "PRACTICE_ROUND_DURATION_SECONDS", 300)

    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "practice-export-isolation", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    start = admin.post(f"/admin/sessions/{sid}/practice_round", auth=auth)
    assert start.status_code == 200

    token = _join_token(sid, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200
    assert participant.post("/trade", json={"direction": "yes", "quantity": 2}).status_code == 200

    assert admin.post(f"/admin/sessions/{sid}/rounds/1/end", auth=auth).status_code == 200

    dashboard_default = admin.get(f"/admin/sessions/{sid}/dashboard", auth=auth)
    assert dashboard_default.status_code == 200
    assert dashboard_default.json()["markets"] == []

    dashboard_with_practice = admin.get(f"/admin/sessions/{sid}/dashboard?include_practice=true", auth=auth)
    assert dashboard_with_practice.status_code == 200
    practice_markets = dashboard_with_practice.json()["markets"]
    assert len(practice_markets) == 1
    assert practice_markets[0]["is_practice"] is True

    export_csv_default = admin.get(f"/admin/sessions/{sid}/export.csv", auth=auth)
    assert export_csv_default.status_code == 200
    assert len([line for line in export_csv_default.text.splitlines() if line.strip()]) == 1

    export_csv_with_practice = admin.get(f"/admin/sessions/{sid}/export.csv?include_practice=true", auth=auth)
    assert export_csv_with_practice.status_code == 200
    assert len([line for line in export_csv_with_practice.text.splitlines() if line.strip()]) == 2

    export_json_default = admin.get(f"/admin/sessions/{sid}/export.json", auth=auth)
    assert export_json_default.status_code == 200
    payload_default = export_json_default.json()
    assert payload_default["markets"] == []
    assert payload_default["rounds"] == []
    assert payload_default["trades"] == []

    export_json_with_practice = admin.get(f"/admin/sessions/{sid}/export.json?include_practice=true", auth=auth)
    assert export_json_with_practice.status_code == 200
    payload_with_practice = export_json_with_practice.json()
    assert len(payload_with_practice["markets"]) == 1
    assert payload_with_practice["markets"][0]["is_practice"] is True
    assert len(payload_with_practice["rounds"]) == 1
    assert len(payload_with_practice["trades"]) == 1


def test_practice_round_requires_session_open_phase() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "practice-phase-gate", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    assert admin.post(f"/admin/sessions/{sid}/markets", auth=auth, json={"market_number": 1}).status_code == 200

    blocked = admin.post(f"/admin/sessions/{sid}/practice_round", auth=auth)
    assert blocked.status_code == 400
    assert "practice" in blocked.json()["detail"].lower()
