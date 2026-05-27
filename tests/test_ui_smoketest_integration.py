from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from calibration.ui_smoketest import run_load_smoke


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


@pytest.mark.integration
def test_ui_smoketest_load_harness_runs(tmp_path: Path) -> None:
    db_path = tmp_path / "ui_smoke_e2e.db"
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
        out = run_load_smoke(
            base_url=base_url,
            admin_user="admin",
            admin_pass="admin",
            sessions=2,
            subject_count=8,
            trades_per_participant=1,
            require_state_sync_ratio=1.0,
            require_price_update_ratio=1.0,
            max_trade_p99_ms=5000.0,
            max_state_sync_p99_ms=5000.0,
        )
        assert out["participants_total"] == 16
        assert out["trades_ok"] == out["trades_expected"] == 16
        assert out["workers_state_sync_ok"] == 16
        assert out["workers_price_update_seen"] == 16
        assert out["state_sync_ratio"] == 1.0
        assert out["price_update_ratio"] == 1.0
        assert out["latency_ms"]["trade_http"]["p99_ms"] is not None
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
