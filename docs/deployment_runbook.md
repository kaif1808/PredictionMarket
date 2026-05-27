# Valdoria Deployment Runbook

## 1. Pre-deploy checks

Run from repository root:

```bash
pytest
cd client && npm run build && cd ..
alembic upgrade head
python3 scripts/deployment_readiness_check.py --strict-env
```

Expected:
- all tests pass
- frontend build succeeds
- migrations apply cleanly

## 2. Required config vars

Set these on the target environment:

- `DATABASE_URL`
- `SESSION_SECRET`
- `ADMIN_USER`
- `ADMIN_PASS`
- `ALLOWED_ORIGINS`
- `COOKIE_SECURE`
- `TOURNAMENT_TIE_BREAK_MODE` (`shared_prize` default, optional `random`)
- `LMSR_B_PARAMETER` (single shared LMSR `b` across all stages; default `18.0`)
- `PYTHON_VERSION`
- `LOG_LEVEL`

## 3. Process model

`Procfile` must contain:

- `release: alembic upgrade head`
- `web: uvicorn server.server:combined_app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 75`

Keep `workers=1` unless shared state is externalized (e.g. Redis-backed pub/sub + state).

## 4. First-session smoke checklist

1. Start one session (`subject_count=8` or `16`).
2. Join at least two participants via join tokens.
3. Run one full market:
   - start market
   - start/end 5 rounds
   - resolve market
4. Close session and verify:
   - `/admin/sessions/{id}/dashboard` returns market summaries
   - `/admin/sessions/{id}/export.json` contains rounds/trades/signals
   - `/admin/sessions/{id}/tournament` returns rankings
5. Validate emergency controls (with reason):
   - `/admin/sessions/{id}/emergency/round_close`
   - `/admin/sessions/{id}/emergency/market_resolve`
   - `/admin/sessions/{id}/emergency/session_close`

## 5. Pilot execution protocol

Before pilot:

```bash
python3 calibration/signal_validator.py --samples 10000 --theta 0.85 --true-outcome 1
python3 calibration/b_sweep.py --b-values 10,15,18,20,25 --runs 100 --true-probability 0.65
# with backend running locally or on staging:
python3 calibration/ui_smoketest.py \
  --base-url http://127.0.0.1:8000 \
  --admin-user admin \
  --admin-pass admin \
  --sessions 2 \
  --subject-count 16 \
  --trades-per-participant 1 \
  --require-state-sync-ratio 1.0 \
  --require-price-update-ratio 1.0 \
  --max-trade-p99-ms 250 \
  --max-state-sync-p99-ms 500
# optional one-command evidence artifact for record-keeping:
python3 scripts/prelaunch_evidence.py \
  --base-url http://127.0.0.1:8000 \
  --admin-user admin \
  --admin-pass admin \
  --sessions 2 \
  --subject-count 16 \
  --trades-per-participant 1 \
  --require-state-sync-ratio 1.0 \
  --require-price-update-ratio 1.0 \
  --max-trade-p99-ms 250 \
  --max-state-sync-p99-ms 500 \
  --reconnect-latency-budget-ms 5000 \
  --output results/prelaunch_evidence.json
# to include managed mid-round restart/resume verification, run with --spawn-local instead of --base-url
```

After pilot session:

```bash
python3 analysis/export_session_metrics.py --session-id <pilot_session_id> --outdir analysis/output
python3 analysis/export_robustness_check.py --session-id <pilot_session_id> --outdir analysis/output
python3 calibration/benchmark_validator.py --session-id <pilot_session_id>
```

Then open notebooks:

- `analysis/01_pilot_review.ipynb`
- `analysis/02_main_analysis.ipynb`
- `analysis/03_robustness.ipynb`

## 6. Recovery check

If server restarts mid-session, run:

```bash
pytest tests/test_restore_recovery.py
pytest tests/test_socket_reconnect_e2e.py
```

This validates `orchestrator.restore_from_db()` for concurrent live sessions.
