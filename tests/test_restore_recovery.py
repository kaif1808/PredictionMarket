from __future__ import annotations

from fastapi.testclient import TestClient

from server.db import SessionLocal
from server.orchestrator import Orchestrator, SessionPhase
from server.server import fastapi_app


def test_restore_from_db_recovers_three_live_sessions_mid_round() -> None:
    admin = TestClient(fastapi_app)
    auth = ("admin", "admin")

    created_ids: list[int] = []
    for i in range(3):
        create = admin.post(
            "/admin/sessions",
            auth=auth,
            json={"label": f"restore-{i}", "rotation_id": 1, "subject_count": 8},
        )
        assert create.status_code == 200
        sid = create.json()["session_id"]
        created_ids.append(sid)
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

    restarted = Orchestrator(SessionLocal)
    restarted.restore_from_db()

    for sid in created_ids:
        assert sid in restarted.sessions
        restored = restarted.sessions[sid]
        assert restored.phase == SessionPhase.ROUND_OPEN
        assert restored.current_market_number == 1
        assert restored.current_round_number == 1
