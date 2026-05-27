from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import ParticipantSession
from server.server import fastapi_app


def _join(client: TestClient, session_id: int, participant_id: str) -> None:
    with SessionLocal() as db:
        ps = db.scalar(
            select(ParticipantSession).where(
                ParticipantSession.session_id == session_id,
                ParticipantSession.participant_id == participant_id,
            )
        )
        assert ps is not None and ps.join_token
        token = ps.join_token
    res = client.post("/auth/join", json={"join_token": token})
    assert res.status_code == 200


def test_full_four_market_five_round_flow_and_tournament() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = admin.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "full-flow", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    p1 = TestClient(fastapi_app)
    p2 = TestClient(fastapi_app)
    _join(p1, sid, "P01")
    _join(p2, sid, "P02")

    for market in [1, 2, 3, 4]:
        r = admin.post(f"/admin/sessions/{sid}/markets", auth=auth, json={"market_number": market})
        assert r.status_code == 200
        for rnd in [1, 2, 3, 4, 5]:
            r = admin.post(f"/admin/sessions/{sid}/rounds", auth=auth, json={"round_number": rnd})
            assert r.status_code == 200
            t1 = p1.post("/trade", json={"direction": "yes", "quantity": 1})
            t2 = p2.post("/trade", json={"direction": "no", "quantity": 1})
            assert t1.status_code == 200
            assert t2.status_code == 200
            r = admin.post(f"/admin/sessions/{sid}/rounds/{rnd}/end", auth=auth)
            assert r.status_code == 200

        r = admin.post(f"/admin/sessions/{sid}/markets/{market}/resolve", auth=auth)
        assert r.status_code == 200

    provisional = admin.get(f"/admin/sessions/{sid}/tournament/provisional", auth=auth)
    assert provisional.status_code == 200
    assert len(provisional.json()) >= 1
    assert all(row.get("provisional") for row in provisional.json())

    r = admin.post(f"/admin/sessions/{sid}/close", auth=auth)
    assert r.status_code == 200
    tournament = r.json()
    assert len(tournament) >= 1
    assert all("rank" in row and "prize_eur" in row for row in tournament)

    t = admin.get(f"/admin/sessions/{sid}/tournament", auth=auth)
    assert t.status_code == 200
    rankings = t.json()
    assert len(rankings) >= 1

    exported = admin.get(f"/admin/sessions/{sid}/export.json", auth=auth)
    assert exported.status_code == 200
    payload = exported.json()
    assert len(payload["markets"]) == 4
    assert len(payload["rounds"]) == 20
    assert len(payload["trades"]) == 40
