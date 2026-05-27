from fastapi.testclient import TestClient

from server.server import fastapi_app


def test_trade_route_serves_spa_shell_on_get() -> None:
    client = TestClient(fastapi_app)
    res = client.get("/trade")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<!doctype html" in res.text.lower()


def test_app_trade_route_serves_spa_shell_on_get() -> None:
    client = TestClient(fastapi_app)
    res = client.get("/app/trade")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "<!doctype html" in res.text.lower()


def test_post_trade_still_uses_api_contract() -> None:
    client = TestClient(fastapi_app)
    res = client.post("/trade", json={"direction": "yes", "quantity": 1})
    assert res.status_code == 401
    assert res.json().get("detail") == "Not authenticated"
