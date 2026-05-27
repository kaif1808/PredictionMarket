from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

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
        assert ps is not None
        assert ps.join_token is not None
        return ps.join_token


def test_three_sessions_are_isolated() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")

    session_ids: list[int] = []
    for i in range(3):
        r = admin.post(
            "/admin/sessions",
            auth=auth,
            json={"label": f"isolation-{i}", "rotation_id": 1, "subject_count": 8},
        )
        assert r.status_code == 200
        sid = r.json()["session_id"]
        session_ids.append(sid)
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

    participant_clients: list[TestClient] = []
    directions = ["yes", "no", "yes"]
    for sid in session_ids:
        c = TestClient(fastapi_app)
        token = _join_token(sid, "P01")
        join = c.post("/auth/join", json={"join_token": token})
        assert join.status_code == 200
        participant_clients.append(c)

    for idx, c in enumerate(participant_clients):
        t = c.post("/trade", json={"direction": directions[idx], "quantity": idx + 1})
        assert t.status_code == 200

    for sid in session_ids:
        export = admin.get(f"/admin/sessions/{sid}/export.json", auth=auth)
        assert export.status_code == 200
        payload = export.json()
        assert len(payload["trades"]) == 1
        assert all(tr["participant_id"] == "P01" for tr in payload["trades"])


def test_concurrent_trade_burst_persists_all_trades() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")
    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "burst", "rotation_id": 1, "subject_count": 8},
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

    participants = [f"P{i:02d}" for i in range(1, 9)]
    clients: dict[str, TestClient] = {}
    for pid in participants:
        c = TestClient(fastapi_app)
        token = _join_token(sid, pid)
        assert c.post("/auth/join", json={"join_token": token}).status_code == 200
        clients[pid] = c

    def _trade(pid: str) -> int:
        res = clients[pid].post("/trade", json={"direction": "yes", "quantity": 1})
        return res.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(_trade, participants))
    assert statuses.count(200) == 8

    export = admin.get(f"/admin/sessions/{sid}/export.json", auth=auth)
    assert export.status_code == 200
    payload = export.json()
    assert len(payload["trades"]) == 8
    assert all(tr["direction"] == "yes" and tr["quantity"] == 1 for tr in payload["trades"])
