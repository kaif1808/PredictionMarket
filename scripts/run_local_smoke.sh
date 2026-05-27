#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/6] Running backend tests"
pytest

echo "[2/6] Building frontend"
(
  cd client
  npm run build
)

echo "[3/6] Applying migrations"
DATABASE_URL=sqlite:///./tmp_smoke_migration.db alembic upgrade head

echo "[4/6] Running calibration signal validator (quick)"
python3 calibration/signal_validator.py --samples 2000 --theta 0.85 --true-outcome 1

echo "[5/6] Exporting analysis metrics for session 1 if present"
python3 analysis/export_session_metrics.py --session-id 1 --outdir analysis/output || true
python3 analysis/export_robustness_check.py --session-id 1 --outdir analysis/output || true
python3 calibration/benchmark_validator.py --session-id 1 || true

echo "[6/6] Reconnect E2E check"
pytest tests/test_socket_reconnect_e2e.py

echo "Local smoke checks completed."
