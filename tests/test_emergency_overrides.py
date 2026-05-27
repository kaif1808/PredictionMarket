from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import AdminAction
from server.server import fastapi_app


def test_emergency_overrides_require_reason_and_log_actions() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post(
        "/admin/sessions",
        auth=auth,
        json={"label": "emergency", "rotation_id": 1, "subject_count": 8},
    )
    assert create.status_code == 200
    sid = create.json()["session_id"]

    assert client.post(f"/admin/sessions/{sid}/markets", auth=auth, json={"market_number": 1}).status_code == 200
    assert client.post(f"/admin/sessions/{sid}/rounds", auth=auth, json={"round_number": 1}).status_code == 200

    missing_reason = client.post(f"/admin/sessions/{sid}/emergency/round_close", auth=auth, json={"reason": ""})
    assert missing_reason.status_code == 422

    force_round = client.post(
        f"/admin/sessions/{sid}/emergency/round_close",
        auth=auth,
        json={"reason": "participant connectivity instability"},
    )
    assert force_round.status_code == 200
    assert force_round.json()["forced"] is True

    force_market = client.post(
        f"/admin/sessions/{sid}/emergency/market_resolve",
        auth=auth,
        json={"reason": "time budget exceeded"},
    )
    assert force_market.status_code == 200
    assert force_market.json()["forced"] is True

    force_session = client.post(
        f"/admin/sessions/{sid}/emergency/session_close",
        auth=auth,
        json={"reason": "lab closing"},
    )
    assert force_session.status_code == 200
    assert force_session.json()["forced"] is True

    with SessionLocal() as db:
        rows = db.scalars(
            select(AdminAction)
            .where(AdminAction.session_id == sid)
            .order_by(AdminAction.id)
        ).all()
    assert [r.action_type for r in rows] == [
        "emergency_round_close",
        "emergency_market_resolve",
        "emergency_session_close",
    ]
    assert all((r.reason or "").strip() for r in rows)
