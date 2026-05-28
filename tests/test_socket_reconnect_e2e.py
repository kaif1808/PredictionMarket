from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import socketio


def _free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return int(s.getsockname()[1])
    except PermissionError as exc:
        pytest.skip(f"Local socket bind is not permitted in this environment: {exc}")


def _wait_for_health(base_url: str, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError("Server did not become healthy in time")


def _fetch_join_token(db_path: Path, session_id: int, participant_id: str, timeout_s: float = 10.0) -> str:
    deadline = time.monotonic() + timeout_s
    query = """
        SELECT join_token
        FROM participant_sessions
        WHERE session_id = ? AND participant_id = ?
    """
    while time.monotonic() < deadline:
        try:
            with sqlite3.connect(str(db_path)) as con:
                row = con.execute(query, (session_id, participant_id)).fetchone()
                if row and row[0]:
                    return str(row[0])
        except sqlite3.OperationalError:
            pass
        time.sleep(0.2)
    raise TimeoutError("join_token not found in time")


@pytest.mark.integration
def test_socket_reconnect_state_sync_under_five_seconds(tmp_path: Path) -> None:
    db_path = tmp_path / "reconnect_e2e.db"
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["ADMIN_USER"] = "admin"
    env["ADMIN_PASS"] = "admin"
    env["SESSION_SECRET"] = "test-secret"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server.server:combined_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
            "--timeout-keep-alive",
            "75",
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_for_health(base_url)

        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            auth = ("admin", "admin")
            create = client.post(
                "/admin/sessions",
                auth=auth,
                json={"label": "e2e-reconnect", "rotation_id": 1, "subject_count": 8},
            )
            assert create.status_code == 200
            session_id = create.json()["session_id"]

            assert (
                client.post(
                    f"/admin/sessions/{session_id}/markets",
                    auth=auth,
                    json={"market_number": 1},
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/admin/sessions/{session_id}/rounds",
                    auth=auth,
                    json={"round_number": 1},
                ).status_code
                == 200
            )

            token = _fetch_join_token(db_path, session_id=session_id, participant_id="P01")
            join = client.post("/auth/join", json={"join_token": token})
            assert join.status_code == 200
            cookie_value = client.cookies.get("valdoria_auth")
            assert cookie_value

        sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
        state_event = threading.Event()
        first_payload: dict[str, object] = {}
        reconnect_payload: dict[str, object] = {}
        first_time = {"t": None}
        second_time = {"t": None}
        phase = {"count": 0}

        @sio.on("state_sync")
        def _on_state_sync(data):
            phase["count"] += 1
            if phase["count"] == 1:
                first_payload.update(data)
                first_time["t"] = time.monotonic()
            else:
                reconnect_payload.update(data)
                second_time["t"] = time.monotonic()
            state_event.set()

        connect_headers = {"Cookie": f"valdoria_auth={cookie_value}"}

        t0 = time.monotonic()
        sio.connect(base_url, headers=connect_headers, wait=True, wait_timeout=5, transports=["polling", "websocket"])
        assert state_event.wait(timeout=5.0)
        assert first_time["t"] is not None
        first_latency = float(first_time["t"] - t0)
        assert first_latency < 5.0
        assert int(first_payload["session_id"]) == session_id
        assert first_payload["participant_id"] == "P01"
        assert "phase" in first_payload
        assert "current_price" in first_payload
        assert "round_deadline_unix_ms" in first_payload
        assert isinstance(first_payload["round_deadline_unix_ms"], int)
        sio.disconnect()

        state_event.clear()
        t1 = time.monotonic()
        sio.connect(base_url, headers=connect_headers, wait=True, wait_timeout=5, transports=["polling", "websocket"])
        assert state_event.wait(timeout=5.0)
        assert second_time["t"] is not None
        second_latency = float(second_time["t"] - t1)
        assert second_latency < 5.0
        assert int(reconnect_payload["session_id"]) == session_id
        assert reconnect_payload["participant_id"] == "P01"
        assert "phase" in reconnect_payload
        assert "current_price" in reconnect_payload
        assert "round_deadline_unix_ms" in reconnect_payload
        assert isinstance(reconnect_payload["round_deadline_unix_ms"], int)
        sio.disconnect()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
