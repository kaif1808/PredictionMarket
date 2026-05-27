from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest


def _local_socket_capable() -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return True
    except PermissionError:
        return False


@pytest.mark.integration
def test_prelaunch_evidence_script_spawn_local_generates_report(tmp_path: Path) -> None:
    if not _local_socket_capable():
        pytest.skip("Local socket bind not permitted in this environment.")

    out = tmp_path / "prelaunch_evidence.json"
    cmd = [
        sys.executable,
        "scripts/prelaunch_evidence.py",
        "--spawn-local",
        "--sessions",
        "1",
        "--subject-count",
        "8",
        "--trades-per-participant",
        "1",
        "--require-state-sync-ratio",
        "1.0",
        "--require-price-update-ratio",
        "1.0",
        "--max-trade-p99-ms",
        "5000",
        "--max-state-sync-p99-ms",
        "5000",
        "--reconnect-latency-budget-ms",
        "5000",
        "--output",
        str(out),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["checks"]["deployment_readiness"]["ok"] is True
    assert payload["checks"]["load_smoke"]["ok"] is True
    assert payload["checks"]["reconnect_probe"]["ok"] is True
    assert payload["checks"]["restart_resume_probe"]["ok"] is True
    assert payload["checks"]["restart_resume_probe"]["skipped"] is False
