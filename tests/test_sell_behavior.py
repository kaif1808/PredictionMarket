from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import ParticipantSession
from server.server import fastapi_app


def _join_p01(client: TestClient, session_id: int) -> None:
    with SessionLocal() as db:
        ps = db.scalar(
            select(ParticipantSession).where(
                ParticipantSession.session_id == session_id,
                ParticipantSession.participant_id == "P01",
            )
        )
        assert ps is not None and ps.join_token
        token = ps.join_token
    res = client.post("/auth/join", json={"join_token": token})
    assert res.status_code == 200


def test_sell_requires_existing_holdings_and_cannot_short_sell() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "sell-behavior", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    session_id = create.json()["session_id"]

    assert client.post(f"/admin/sessions/{session_id}/markets", auth=auth, json={"market_number": 1}).status_code == 200
    assert client.post(f"/admin/sessions/{session_id}/rounds", auth=auth, json={"round_number": 1}).status_code == 200

    _join_p01(client, session_id)

    buy = client.post("/trade", json={"side": "buy", "direction": "yes", "quantity": 2})
    assert buy.status_code == 200
    buy_payload = buy.json()
    assert buy_payload["yes_held"] == 2.0

    sell = client.post("/trade", json={"side": "sell", "direction": "yes", "quantity": 1})
    assert sell.status_code == 200
    sell_payload = sell.json()
    assert sell_payload["yes_held"] == 1.0
    assert sell_payload["balance_after"] > buy_payload["balance_after"]

    short_sell = client.post("/trade", json={"side": "sell", "direction": "yes", "quantity": 2})
    assert short_sell.status_code == 400
    assert short_sell.json()["detail"] == "SHORT_SELL_NOT_ALLOWED"
