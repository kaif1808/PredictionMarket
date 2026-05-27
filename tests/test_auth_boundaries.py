from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

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


def test_admin_endpoints_require_basic_auth() -> None:
    client = TestClient(fastapi_app)
    no_auth = client.get("/admin/sessions")
    assert no_auth.status_code == 401


def test_participant_endpoints_require_cookie_auth() -> None:
    client = TestClient(fastapi_app)
    assert client.get("/state").status_code == 401
    assert client.post("/trade", json={"direction": "yes", "quantity": 1}).status_code == 401
    assert client.post("/quiz/comprehension/submit", json={"attempts": 1, "final_correct": True, "raw_answers": {}}).status_code == 401


def test_session_cookie_does_not_control_other_session() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")

    s1 = admin.post("/admin/sessions", auth=auth, json={"label": "s1", "rotation_id": 1, "subject_count": 8}).json()["session_id"]
    s2 = admin.post("/admin/sessions", auth=auth, json={"label": "s2", "rotation_id": 1, "subject_count": 8}).json()["session_id"]

    assert admin.post(f"/admin/sessions/{s2}/markets", auth=auth, json={"market_number": 1}).status_code == 200
    assert admin.post(f"/admin/sessions/{s2}/rounds", auth=auth, json={"round_number": 1}).status_code == 200

    participant = TestClient(fastapi_app)
    token = _join_token(s1, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200

    # Cookie from session 1 cannot place trades in session 2; trade resolves against session 1 state only.
    blocked = participant.post("/trade", json={"direction": "yes", "quantity": 1})
    assert blocked.status_code == 400
    assert blocked.json()["detail"] in {"ROUND_CLOSED", "No active market/round", "unknown participant"}
