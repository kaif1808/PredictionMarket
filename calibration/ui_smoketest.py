from __future__ import annotations

import argparse
import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import httpx
import socketio


def _auth_header(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def _participant_id(idx: int) -> str:
    return f"P{idx:02d}"


@dataclass(frozen=True)
class WorkerResult:
    session_id: int
    participant_id: str
    trades_ok: int
    saw_state_sync: bool
    saw_round_started: bool
    saw_price_update: bool
    join_latency_ms: float
    state_sync_latency_ms: float | None
    trade_latencies_ms: list[float]
    first_price_update_latency_ms: float | None


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    xs = sorted(float(v) for v in values)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return float(xs[lo] + (xs[hi] - xs[lo]) * frac)


def _latency_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None}
    return {
        "count": len(values),
        "p50_ms": _percentile(values, 0.50),
        "p95_ms": _percentile(values, 0.95),
        "p99_ms": _percentile(values, 0.99),
        "max_ms": max(values),
    }


def _participant_worker(base_url: str, session_id: int, participant_id: str, trades_per_participant: int) -> WorkerResult:
    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        join_t0 = time.perf_counter()
        join = client.post("/auth/join", json={"join_token": f"{session_id}:{participant_id}"})
        join.raise_for_status()
        join_latency_ms = (time.perf_counter() - join_t0) * 1000.0
        cookie = client.cookies.get("valdoria_auth")
        if not cookie:
            raise RuntimeError(f"Missing auth cookie for {session_id}:{participant_id}")

        state_sync_seen = threading.Event()
        round_started_seen = threading.Event()
        price_update_seen = threading.Event()
        trade_started_seen = threading.Event()

        state_sync_t: dict[str, float | None] = {"t": None}
        first_trade_t: dict[str, float | None] = {"t": None}
        first_price_update_t: dict[str, float | None] = {"t": None}
        price_update_count = 0
        trade_latencies_ms: list[float] = []

        sio = socketio.Client(reconnection=False, logger=False, engineio_logger=False)
        connect_t0 = time.perf_counter()

        @sio.on("state_sync")
        def _on_state_sync(_payload: dict[str, Any]) -> None:
            if state_sync_t["t"] is None:
                state_sync_t["t"] = time.perf_counter()
            state_sync_seen.set()

        @sio.on("round_started")
        def _on_round_started(_payload: dict[str, Any]) -> None:
            round_started_seen.set()

        @sio.on("price_update")
        def _on_price_update(_payload: dict[str, Any]) -> None:
            nonlocal price_update_count
            price_update_count += 1
            if trade_started_seen.is_set() and first_price_update_t["t"] is None:
                first_price_update_t["t"] = time.perf_counter()
            price_update_seen.set()

        sio.connect(
            base_url,
            headers={"Cookie": f"valdoria_auth={cookie}"},
            wait=True,
            wait_timeout=5,
            transports=["polling", "websocket"],
        )

        state_sync_seen.wait(timeout=3.0)

        trades_ok = 0
        for _ in range(trades_per_participant):
            if first_trade_t["t"] is None:
                first_trade_t["t"] = time.perf_counter()
                trade_started_seen.set()
            trade_t0 = time.perf_counter()
            t = client.post("/trade", json={"direction": "yes", "quantity": 1})
            trade_latencies_ms.append((time.perf_counter() - trade_t0) * 1000.0)
            if t.status_code == 200:
                trades_ok += 1

        price_update_seen.wait(timeout=1.0)

        state_sync_latency_ms = None
        if state_sync_t["t"] is not None:
            state_sync_latency_ms = (state_sync_t["t"] - connect_t0) * 1000.0

        first_price_update_latency_ms = None
        if first_trade_t["t"] is not None and first_price_update_t["t"] is not None:
            first_price_update_latency_ms = (first_price_update_t["t"] - first_trade_t["t"]) * 1000.0

        sio.disconnect()
        return WorkerResult(
            session_id=session_id,
            participant_id=participant_id,
            trades_ok=trades_ok,
            saw_state_sync=state_sync_seen.is_set(),
            saw_round_started=round_started_seen.is_set(),
            saw_price_update=price_update_seen.is_set(),
            join_latency_ms=join_latency_ms,
            state_sync_latency_ms=state_sync_latency_ms,
            trade_latencies_ms=trade_latencies_ms,
            first_price_update_latency_ms=first_price_update_latency_ms,
        )


def run_load_smoke(
    base_url: str,
    admin_user: str,
    admin_pass: str,
    sessions: int,
    subject_count: int,
    trades_per_participant: int,
    require_state_sync_ratio: float = 1.0,
    require_price_update_ratio: float = 1.0,
    max_trade_p99_ms: float | None = None,
    max_state_sync_p99_ms: float | None = None,
) -> dict[str, Any]:
    headers = _auth_header(admin_user, admin_pass)
    with httpx.Client(base_url=base_url, timeout=30.0) as admin:
        health = admin.get("/health")
        health.raise_for_status()

        session_ids: list[int] = []
        for i in range(sessions):
            created = admin.post(
                "/admin/sessions",
                headers=headers,
                json={"label": f"ui-smoke-{i}", "rotation_id": 1, "subject_count": subject_count},
            )
            created.raise_for_status()
            sid = int(created.json()["session_id"])
            session_ids.append(sid)
            admin.post(f"/admin/sessions/{sid}/markets", headers=headers, json={"market_number": 1}).raise_for_status()
            admin.post(f"/admin/sessions/{sid}/rounds", headers=headers, json={"round_number": 1}).raise_for_status()

        futures = []
        with ThreadPoolExecutor(max_workers=max(8, sessions * subject_count)) as pool:
            for sid in session_ids:
                for n in range(1, subject_count + 1):
                    pid = _participant_id(n)
                    futures.append(pool.submit(_participant_worker, base_url, sid, pid, trades_per_participant))

            results: list[WorkerResult] = []
            for fut in as_completed(futures):
                results.append(fut.result())

        for sid in session_ids:
            admin.post(f"/admin/sessions/{sid}/rounds/1/end", headers=headers).raise_for_status()
            export = admin.get(f"/admin/sessions/{sid}/export.json", headers=headers)
            export.raise_for_status()
            payload = export.json()
            expected_trades = subject_count * trades_per_participant
            actual_trades = len(payload["trades"])
            if actual_trades != expected_trades:
                raise RuntimeError(
                    f"Session {sid} trade mismatch: expected {expected_trades}, got {actual_trades}"
                )

        total_workers = sessions * subject_count
        workers_state_sync_ok = sum(1 for r in results if r.saw_state_sync)
        workers_price_update_seen = sum(1 for r in results if r.saw_price_update)

        all_trade_latencies_ms = [lat for r in results for lat in r.trade_latencies_ms]
        state_sync_latencies_ms = [lat for r in results if r.state_sync_latency_ms is not None for lat in [r.state_sync_latency_ms]]
        first_price_update_latencies_ms = [
            lat for r in results if r.first_price_update_latency_ms is not None for lat in [r.first_price_update_latency_ms]
        ]
        join_latencies_ms = [r.join_latency_ms for r in results]

        trade_summary = _latency_summary(all_trade_latencies_ms)
        state_sync_summary = _latency_summary(state_sync_latencies_ms)
        first_price_update_summary = _latency_summary(first_price_update_latencies_ms)
        join_summary = _latency_summary(join_latencies_ms)

        summary = {
            "sessions": sessions,
            "subject_count": subject_count,
            "participants_total": total_workers,
            "workers_state_sync_ok": workers_state_sync_ok,
            "workers_round_started_seen": sum(1 for r in results if r.saw_round_started),
            "workers_price_update_seen": workers_price_update_seen,
            "trades_ok": sum(r.trades_ok for r in results),
            "trades_expected": sessions * subject_count * trades_per_participant,
            "state_sync_ratio": workers_state_sync_ok / total_workers if total_workers else 0.0,
            "price_update_ratio": workers_price_update_seen / total_workers if total_workers else 0.0,
            "latency_ms": {
                "join": join_summary,
                "state_sync": state_sync_summary,
                "trade_http": trade_summary,
                "first_price_update_after_trade": first_price_update_summary,
            },
        }

        if summary["state_sync_ratio"] < require_state_sync_ratio:
            raise RuntimeError(
                f"state_sync ratio {summary['state_sync_ratio']:.3f} below threshold {require_state_sync_ratio:.3f}"
            )
        if summary["price_update_ratio"] < require_price_update_ratio:
            raise RuntimeError(
                f"price_update ratio {summary['price_update_ratio']:.3f} below threshold {require_price_update_ratio:.3f}"
            )

        trade_p99 = summary["latency_ms"]["trade_http"]["p99_ms"]
        if max_trade_p99_ms is not None and trade_p99 is not None and trade_p99 > max_trade_p99_ms:
            raise RuntimeError(
                f"trade HTTP p99 {trade_p99:.2f}ms exceeds threshold {max_trade_p99_ms:.2f}ms"
            )

        sync_p99 = summary["latency_ms"]["state_sync"]["p99_ms"]
        if max_state_sync_p99_ms is not None and sync_p99 is not None and sync_p99 > max_state_sync_p99_ms:
            raise RuntimeError(
                f"state_sync p99 {sync_p99:.2f}ms exceeds threshold {max_state_sync_p99_ms:.2f}ms"
            )

        return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Concurrent session + websocket smoke harness for pre-session runtime checks."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin")
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--subject-count", type=int, default=16)
    parser.add_argument("--trades-per-participant", type=int, default=1)
    parser.add_argument("--require-state-sync-ratio", type=float, default=1.0)
    parser.add_argument("--require-price-update-ratio", type=float, default=1.0)
    parser.add_argument("--max-trade-p99-ms", type=float, default=None)
    parser.add_argument("--max-state-sync-p99-ms", type=float, default=None)
    args = parser.parse_args()

    summary = run_load_smoke(
        base_url=args.base_url,
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
    print(summary)


if __name__ == "__main__":
    main()
