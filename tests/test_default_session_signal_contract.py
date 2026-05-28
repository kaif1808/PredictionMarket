from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from server.db import SessionLocal
from server.db_models import Market, MarketRole, ParticipantSession, Round, Signal
from server.server import fastapi_app


def _signal_counts_for_round(round_id: int) -> tuple[int, int]:
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(Signal).where(Signal.round_id == round_id)) or 0
        delivered = (
            db.scalar(
                select(func.count()).select_from(Signal).where(Signal.round_id == round_id, Signal.delivered == True)  # noqa: E712
            )
            or 0
        )
    return int(total), int(delivered)


def test_default_session_nine_participants_and_signal_contracts() -> None:
    client = TestClient(fastapi_app)
    auth = ("admin", "admin")

    create = client.post("/admin/sessions", auth=auth, json={"label": "default-contract", "rotation_id": 1})
    assert create.status_code == 200
    session_id = int(create.json()["session_id"])

    with SessionLocal() as db:
        participants = db.scalars(
            select(ParticipantSession).where(ParticipantSession.session_id == session_id)
        ).all()
    assert len(participants) == 9

    # Market 1: stage 1 signals are drawn but not delivered.
    assert client.post(f"/admin/sessions/{session_id}/markets", auth=auth, json={"market_number": 1}).status_code == 200
    m1_round = client.post(f"/admin/sessions/{session_id}/rounds", auth=auth, json={"round_number": 1})
    assert m1_round.status_code == 200
    m1_round_id = int(m1_round.json()["round_id"])
    m1_total, m1_delivered = _signal_counts_for_round(m1_round_id)
    assert m1_total == 9
    assert m1_delivered == 0
    assert client.post(f"/admin/sessions/{session_id}/rounds/1/end", auth=auth).status_code == 200
    assert client.post(f"/admin/sessions/{session_id}/markets/1/resolve", auth=auth).status_code == 200

    # Market 2: exactly 3 informed signals delivered under default schedule.
    assert client.post(f"/admin/sessions/{session_id}/markets", auth=auth, json={"market_number": 2}).status_code == 200
    m2_round = client.post(f"/admin/sessions/{session_id}/rounds", auth=auth, json={"round_number": 1})
    assert m2_round.status_code == 200
    m2_round_id = int(m2_round.json()["round_id"])
    _m2_total, m2_delivered = _signal_counts_for_round(m2_round_id)
    assert m2_delivered == 3
    assert client.post(f"/admin/sessions/{session_id}/rounds/1/end", auth=auth).status_code == 200
    assert client.post(f"/admin/sessions/{session_id}/markets/2/resolve", auth=auth).status_code == 200

    # Market 3: uninformed-only, so delivered signals stay zero.
    assert client.post(f"/admin/sessions/{session_id}/markets", auth=auth, json={"market_number": 3}).status_code == 200
    m3_round = client.post(f"/admin/sessions/{session_id}/rounds", auth=auth, json={"round_number": 1})
    assert m3_round.status_code == 200
    m3_round_id = int(m3_round.json()["round_id"])
    _m3_total, m3_delivered = _signal_counts_for_round(m3_round_id)
    assert m3_delivered == 0

    # Benchmarks should be populated whenever rounds are ended.
    assert client.post(f"/admin/sessions/{session_id}/rounds/1/end", auth=auth).status_code == 200
    assert client.post(f"/admin/sessions/{session_id}/markets/3/resolve", auth=auth).status_code == 200

    # Market 4 runtime role allocation under default schedule.
    assert client.post(f"/admin/sessions/{session_id}/markets", auth=auth, json={"market_number": 4}).status_code == 200
    with SessionLocal() as db:
        market4 = db.scalar(
            select(Market).where(Market.session_id == session_id, Market.market_number == 4)
        )
        assert market4 is not None
        roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market4.id)).all()
    assert sum(1 for r in roles if r.role_tier == "informed") == 3
    assert sum(1 for r in roles if r.endowment_tokens == 400) == 2

    with SessionLocal() as db:
        ended_rounds = db.scalars(
            select(Round)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == session_id, Round.closed_at.is_not(None))
            .order_by(Round.id.asc())
        ).all()
    assert len(ended_rounds) >= 3
    assert all(r.bayesian_benchmark is not None for r in ended_rounds)
