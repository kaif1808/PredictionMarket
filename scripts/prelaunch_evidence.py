#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import socketio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibration.ui_smoketest import run_load_smoke
from scripts.deployment_readiness_check import run_checks


def _free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return int(s.getsockname()[1])
    except PermissionError as exc:
        raise RuntimeError(
            "Local socket bind is not permitted in this environment. "
            "Use --base-url against an already-running server instead of --spawn-local."
        ) from exc


def _wait_for_health(base_url: str, timeout_s: float = 20.0) -> None:
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


def _start_local_server(port: int, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
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
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _run_reconnect_probe(
    base_url: str,
    admin_user: str,
    admin_pass: str,
    subject_count: int = 9,
    latency_budget_ms: float = 5000.0,
) -> dict[str, Any]:
    auth = (admin_user, admin_pass)
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        create = client.post(
            "/admin/sessions",
            auth=auth,
            json={"label": "prelaunch-reconnect", "rotation_id": 1, "subject_count": subject_count},
        )
        create.raise_for_status()
        session_id = int(create.json()["session_id"])

        client.post(
            f"/admin/sessions/{session_id}/markets",
            auth=auth,
            json={"market_number": 1},
        ).raise_for_status()
        client.post(
            f"/admin/sessions/{session_id}/rounds",
            auth=auth,
            json={"round_number": 1},
        ).raise_for_status()

        join = client.post("/auth/join", json={"join_token": f"{session_id}:P01"})
        join.raise_for_status()
        cookie_value = client.cookies.get("valdoria_auth")
        if not cookie_value:
            raise RuntimeError("Missing valdoria_auth cookie after join")

    sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
    state_event = threading.Event()
    phase = {"count": 0}
    first_sync_t = {"t": None}
    second_sync_t = {"t": None}
    first_payload: dict[str, Any] = {}
    second_payload: dict[str, Any] = {}

    @sio.on("state_sync")
    def _on_state_sync(data: dict[str, Any]) -> None:
        phase["count"] += 1
        if phase["count"] == 1:
            first_sync_t["t"] = time.monotonic()
            first_payload.update(data)
        else:
            second_sync_t["t"] = time.monotonic()
            second_payload.update(data)
        state_event.set()

    headers = {"Cookie": f"valdoria_auth={cookie_value}"}

    t0 = time.monotonic()
    sio.connect(base_url, headers=headers, wait=True, wait_timeout=5, transports=["polling", "websocket"])
    if not state_event.wait(timeout=5.0) or first_sync_t["t"] is None:
        raise RuntimeError("Did not receive first state_sync in time")
    first_ms = (first_sync_t["t"] - t0) * 1000.0
    sio.disconnect()

    state_event.clear()
    t1 = time.monotonic()
    sio.connect(base_url, headers=headers, wait=True, wait_timeout=5, transports=["polling", "websocket"])
    if not state_event.wait(timeout=5.0) or second_sync_t["t"] is None:
        raise RuntimeError("Did not receive reconnect state_sync in time")
    second_ms = (second_sync_t["t"] - t1) * 1000.0
    sio.disconnect()

    payload_ok = (
        int(first_payload.get("session_id", -1)) == session_id
        and first_payload.get("participant_id") == "P01"
        and int(second_payload.get("session_id", -1)) == session_id
        and second_payload.get("participant_id") == "P01"
    )
    within_budget = first_ms <= latency_budget_ms and second_ms <= latency_budget_ms

    return {
        "ok": bool(payload_ok and within_budget),
        "session_id": session_id,
        "first_state_sync_ms": round(first_ms, 3),
        "second_state_sync_ms": round(second_ms, 3),
        "latency_budget_ms": latency_budget_ms,
        "payload_ok": payload_ok,
        "within_budget": within_budget,
    }


def _run_restart_resume_probe(
    base_url: str,
    admin_user: str,
    admin_pass: str,
    restart_proc: subprocess.Popen[str] | None,
    restart_env: dict[str, str] | None,
    restart_port: int | None,
    latency_budget_ms: float = 5000.0,
) -> tuple[dict[str, Any], subprocess.Popen[str] | None]:
    if restart_proc is None or restart_env is None or restart_port is None:
        return (
            {
                "ok": True,
                "skipped": True,
                "reason": "restart probe requires --spawn-local managed server",
            },
            restart_proc,
        )

    auth = (admin_user, admin_pass)
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        create = client.post(
            "/admin/sessions",
            auth=auth,
            json={"label": "prelaunch-restart", "rotation_id": 1, "subject_count": 8},
        )
        create.raise_for_status()
        session_id = int(create.json()["session_id"])

        client.post(
            f"/admin/sessions/{session_id}/markets",
            auth=auth,
            json={"market_number": 1},
        ).raise_for_status()
        client.post(
            f"/admin/sessions/{session_id}/rounds",
            auth=auth,
            json={"round_number": 1},
        ).raise_for_status()

        join = client.post("/auth/join", json={"join_token": f"{session_id}:P01"})
        join.raise_for_status()
        cookie_value = client.cookies.get("valdoria_auth")
        if not cookie_value:
            raise RuntimeError("Missing valdoria_auth cookie after join")

        pre_trade = client.post("/trade", json={"direction": "yes", "quantity": 1})
        pre_trade.raise_for_status()

    _stop_process(restart_proc)
    restart_proc = _start_local_server(restart_port, restart_env)
    _wait_for_health(base_url)

    sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
    state_event = threading.Event()
    sync_t = {"t": None}
    payload: dict[str, Any] = {}

    @sio.on("state_sync")
    def _on_state_sync(data: dict[str, Any]) -> None:
        if sync_t["t"] is None:
            sync_t["t"] = time.monotonic()
            payload.update(data)
        state_event.set()

    t0 = time.monotonic()
    sio.connect(
        base_url,
        headers={"Cookie": f"valdoria_auth={cookie_value}"},
        wait=True,
        wait_timeout=5,
        transports=["polling", "websocket"],
    )
    if not state_event.wait(timeout=5.0) or sync_t["t"] is None:
        raise RuntimeError("No state_sync after restart within timeout")
    sync_ms = (sync_t["t"] - t0) * 1000.0
    sio.disconnect()

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        client.cookies.set("valdoria_auth", cookie_value)
        post_trade = client.post("/trade", json={"direction": "yes", "quantity": 1})
        post_trade.raise_for_status()

        export = client.get(f"/admin/sessions/{session_id}/export.json", auth=auth)
        export.raise_for_status()
        payload_export = export.json()
        trades = [
            tr
            for tr in payload_export.get("trades", [])
            if tr.get("participant_id") == "P01" and tr.get("direction") == "yes" and int(tr.get("quantity", 0)) == 1
        ]

    payload_ok = int(payload.get("session_id", -1)) == session_id and payload.get("participant_id") == "P01"
    within_budget = sync_ms <= latency_budget_ms
    no_double_count = len(trades) == 2
    ok = payload_ok and within_budget and no_double_count

    return (
        {
            "ok": ok,
            "skipped": False,
            "session_id": session_id,
            "state_sync_after_restart_ms": round(sync_ms, 3),
            "latency_budget_ms": latency_budget_ms,
            "payload_ok": payload_ok,
            "within_budget": within_budget,
            "post_restart_trade_count_for_p01_yes_qty1": len(trades),
            "no_double_count": no_double_count,
        },
        restart_proc,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a machine-readable prelaunch readiness evidence report."
    )
    parser.add_argument("--base-url", default="", help="Target server base URL. Omit when using --spawn-local.")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin")
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--subject-count", type=int, default=9)
    parser.add_argument("--trades-per-participant", type=int, default=1)
    parser.add_argument("--require-state-sync-ratio", type=float, default=1.0)
    parser.add_argument("--require-price-update-ratio", type=float, default=1.0)
    parser.add_argument("--max-trade-p99-ms", type=float, default=250.0)
    parser.add_argument("--max-state-sync-p99-ms", type=float, default=500.0)
    parser.add_argument("--reconnect-latency-budget-ms", type=float, default=5000.0)
    parser.add_argument("--strict-env-check", action="store_true")
    parser.add_argument("--spawn-local", action="store_true", help="Start an ephemeral local uvicorn server for the checks.")
    parser.add_argument("--output", default="results/prelaunch_evidence.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_url = args.base_url.strip()
    temp_dir_ctx = None
    proc: subprocess.Popen[str] | None = None
    local_db_path: str | None = None
    local_port: int | None = None
    local_env: dict[str, str] | None = None
    started_local = False

    try:
        if args.spawn_local:
            temp_dir_ctx = tempfile.TemporaryDirectory(prefix="valdoria-prelaunch-")
            db_file = Path(temp_dir_ctx.name) / "prelaunch.db"
            local_db_path = str(db_file)
            local_port = _free_port()
            base_url = f"http://127.0.0.1:{local_port}"
            local_env = os.environ.copy()
            local_env["DATABASE_URL"] = f"sqlite:///{db_file}"
            local_env["SESSION_SECRET"] = "prelaunch-local-secret"
            local_env["ADMIN_USER"] = args.admin_user
            local_env["ADMIN_PASS"] = args.admin_pass
            local_env["ALLOWED_ORIGINS"] = "http://127.0.0.1:5173,http://localhost:5173"
            local_env["COOKIE_SECURE"] = "false"
            local_env["TOURNAMENT_TIE_BREAK_MODE"] = "shared_prize"

            proc = _start_local_server(local_port, local_env)
            _wait_for_health(base_url)
            started_local = True

        if not base_url:
            raise ValueError("--base-url is required unless --spawn-local is set.")

        report: dict[str, Any] = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "base_url": base_url,
            "spawn_local": args.spawn_local,
            "checks": {},
            "ok": True,
        }
        if local_db_path:
            report["local_db_path"] = local_db_path

        dep = run_checks(strict_env=args.strict_env_check)
        report["checks"]["deployment_readiness"] = asdict(dep)
        if not dep.ok:
            report["ok"] = False

        try:
            load_summary = run_load_smoke(
                base_url=base_url,
                admin_user=args.admin_user,
                admin_pass=args.admin_pass,
                sessions=args.sessions,
                subject_count=args.subject_count,
                trades_per_participant=args.trades_per_participant,
                require_state_sync_ratio=args.require_state_sync_ratio,
                require_price_update_ratio=args.require_price_update_ratio,
                max_trade_p99_ms=args.max_trade_p99_ms,
                max_state_sync_p99_ms=args.max_state_sync_p99_ms,
            )
            report["checks"]["load_smoke"] = {"ok": True, "summary": load_summary}
        except Exception as exc:
            report["checks"]["load_smoke"] = {"ok": False, "error": str(exc)}
            report["ok"] = False

        try:
            reconnect = _run_reconnect_probe(
                base_url=base_url,
                admin_user=args.admin_user,
                admin_pass=args.admin_pass,
                subject_count=min(max(args.subject_count, 8), 20),
                latency_budget_ms=args.reconnect_latency_budget_ms,
            )
            report["checks"]["reconnect_probe"] = reconnect
            if not reconnect["ok"]:
                report["ok"] = False
        except Exception as exc:
            report["checks"]["reconnect_probe"] = {"ok": False, "error": str(exc)}
            report["ok"] = False

        try:
            restart_probe, proc = _run_restart_resume_probe(
                base_url=base_url,
                admin_user=args.admin_user,
                admin_pass=args.admin_pass,
                restart_proc=proc,
                restart_env=local_env,
                restart_port=local_port,
                latency_budget_ms=args.reconnect_latency_budget_ms,
            )
            report["checks"]["restart_resume_probe"] = restart_probe
            if not restart_probe.get("ok", False):
                report["ok"] = False
        except Exception as exc:
            report["checks"]["restart_resume_probe"] = {"ok": False, "error": str(exc)}
            report["ok"] = False

        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"ok": report["ok"], "output": str(output_path)}, indent=2, sort_keys=True))
        return 0 if report["ok"] else 1
    finally:
        _stop_process(proc)
        if temp_dir_ctx is not None:
            temp_dir_ctx.cleanup()
        if started_local:
            time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
