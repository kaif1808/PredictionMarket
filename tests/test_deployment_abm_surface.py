from __future__ import annotations

from fastapi.testclient import TestClient

from server.server import fastapi_app


def test_abm_watch_endpoint_is_disabled_by_default() -> None:
    client = TestClient(fastapi_app)

    res = client.get("/abm/watch/run")

    assert res.status_code == 404
    assert res.json()["detail"] == "ABM watch is disabled"
