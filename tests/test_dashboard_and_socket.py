from __future__ import annotations

import pytest
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


def test_dashboard_endpoint_returns_live_market_cards() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "dashboard", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    assert admin.post(
        f"/admin/sessions/{sid}/markets",
        auth=auth,
        json={"market_number": 1},
    ).status_code == 200
    assert admin.post(
        f"/admin/sessions/{sid}/rounds",
        auth=auth,
        json={"round_number": 1},
    ).status_code == 200

    participant = TestClient(fastapi_app)
    token = _join_token(sid, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200
    assert participant.post("/trade", json={"direction": "yes", "quantity": 2}).status_code == 200
    assert admin.post(f"/admin/sessions/{sid}/rounds/1/end", auth=auth).status_code == 200
    assert admin.post(f"/admin/sessions/{sid}/markets/1/resolve", auth=auth).status_code == 200

    dashboard = admin.get(f"/admin/sessions/{sid}/dashboard", auth=auth)
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["session_id"] == sid
    assert payload["participant_count"] == 8
    assert len(payload["markets"]) == 1
    m = payload["markets"][0]
    assert m["market_number"] == 1
    assert m["rounds_opened"] == 1
    assert m["total_volume"] == 2
    assert m["latest_round_number"] == 1
    assert m["outcome"] == 1
    assert m["outcome_label"] == "YES — Conflict occurred"


def test_state_includes_round_deadline_only_while_round_open() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "state-deadline", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    assert admin.post(
        f"/admin/sessions/{sid}/markets",
        auth=auth,
        json={"market_number": 1},
    ).status_code == 200
    assert admin.post(
        f"/admin/sessions/{sid}/rounds",
        auth=auth,
        json={"round_number": 1},
    ).status_code == 200

    participant = TestClient(fastapi_app)
    token = _join_token(sid, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200

    state_open = participant.get("/state")
    assert state_open.status_code == 200
    payload_open = state_open.json()
    assert payload_open["phase"] == "round_open"
    assert isinstance(payload_open["round_deadline_unix_ms"], int)
    assert payload_open["round_deadline_unix_ms"] > 0

    assert admin.post(f"/admin/sessions/{sid}/rounds/1/end", auth=auth).status_code == 200

    state_closed = participant.get("/state")
    assert state_closed.status_code == 200
    payload_closed = state_closed.json()
    assert payload_closed["phase"] == "round_closed"
    assert payload_closed["round_deadline_unix_ms"] is None


def test_market_resolution_emits_public_outcome_and_private_payouts(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "resolve-events", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    assert admin.post(f"/admin/sessions/{sid}/markets", auth=auth, json={"market_number": 1}).status_code == 200
    assert admin.post(f"/admin/sessions/{sid}/rounds", auth=auth, json={"round_number": 1}).status_code == 200

    participant = TestClient(fastapi_app)
    token = _join_token(sid, "P01")
    assert participant.post("/auth/join", json={"join_token": token}).status_code == 200
    assert participant.post("/trade", json={"direction": "yes", "quantity": 1}).status_code == 200
    assert admin.post(f"/admin/sessions/{sid}/rounds/1/end", auth=auth).status_code == 200

    emitted: list[tuple[str, str | None, dict]] = []

    async def fake_emit(event, data=None, room=None, **kwargs):
        emitted.append((event, room, data or {}))
        return None

    monkeypatch.setattr(server_module.sio, "emit", fake_emit)
    resolve = admin.post(f"/admin/sessions/{sid}/markets/1/resolve", auth=auth)
    assert resolve.status_code == 200

    assert any(evt == "market_outcome_public" and room == f"session:{sid}:all" for evt, room, _ in emitted)
    private_events = [(evt, room, data) for evt, room, data in emitted if evt == "market_resolved"]
    assert len(private_events) == 8
    for _, room, data in private_events:
        assert room.startswith(f"session:{sid}:participant:")
        assert data["outcome"] in {0, 1}
        assert data["outcome_label"] in {"YES — Conflict occurred", "NO — Conflict did not occur"}
        assert "payout" in data and "final_balance" in data and "pnl" in data


@pytest.mark.anyio
async def test_socket_connect_emits_full_state_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "socket-sync", "rotation_id": 1, "subject_count": 8},
    )
    sid = create.json()["session_id"]
    admin.post(f"/admin/sessions/{sid}/markets", auth=auth, json={"market_number": 1})
    admin.post(f"/admin/sessions/{sid}/rounds", auth=auth, json={"round_number": 1})

    participant = TestClient(fastapi_app)
    token = _join_token(sid, "P01")
    join = participant.post("/auth/join", json={"join_token": token})
    assert join.status_code == 200
    cookie = participant.cookies.get("valdoria_auth")
    assert cookie

    captured: dict[str, object] = {}

    async def fake_save_session(*args, **kwargs):
        return None

    async def fake_enter_room(*args, **kwargs):
        return None

    async def fake_emit(event, data=None, room=None, **kwargs):
        if event == "state_sync":
            captured["data"] = data
            captured["room"] = room
        return None

    monkeypatch.setattr(server_module.sio, "save_session", fake_save_session)
    monkeypatch.setattr(server_module.sio, "enter_room", fake_enter_room)
    monkeypatch.setattr(server_module.sio, "emit", fake_emit)

    ok = await server_module.connect("sid-test", {"HTTP_COOKIE": f"valdoria_auth={cookie}"}, None)
    assert ok is True
    assert "data" in captured
    state = captured["data"]
    assert isinstance(state, dict)
    assert state["session_id"] == sid
    assert state["participant_id"] == "P01"
    assert "phase" in state
    assert "current_price" in state
    assert "bulletin" in state
    assert "round_deadline_unix_ms" in state
    assert isinstance(state["round_deadline_unix_ms"], int)
