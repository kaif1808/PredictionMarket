# Valdoria Prediction Market

Backend-first implementation aligned to `VALDORIA_AGENT_BIBLE.md`.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server.server:combined_app --reload --port 8000
```

Run migrations explicitly:

```bash
alembic upgrade head
```

Frontend (new terminal):

```bash
cd client
npm install
npm run dev
```

Production-style frontend build served by FastAPI at `/app`:

```bash
cd client
npm run build
cd ..
uvicorn server.server:combined_app --reload --port 8000
# open http://127.0.0.1:8000/app
```

## Current scope implemented

**Core infrastructure & runtime semantics:**
- SQLAlchemy schema for sessions, markets, rounds, signals, trades, tournament rankings, and aux flow tables.
- LMSR engine (`server/lmsr.py`) with `b` parameter, `price_impact`, and `max_purchasable`.
- Bayesian signal service (`server/bayesian.py`) including Stage 1 drawn-but-suppressed signals.
- Rotation/endowment logic (`server/roles.py`) and scenario bulletins (`server/scenarios.py`).
- Session orchestrator (`server/orchestrator.py`) for session → market → round flow and tournament computation.
- Alembic migration setup with deterministic initial schema revision (`alembic/`).

**FastAPI + Socket.io server runtime (`server/server.py`):**
- Session-scoped admin and participant endpoints with request/response validation.
- One-time join-token exchange (POST `/auth/join` invalidates token after first use; cookie reconnect preserved).
- 90-second round windows with real-time round deadline (`round_deadline_unix_ms`).
- Market resolution with public outcome event + private per-participant payout payloads.
- Real `round_volume` emission and return values on round close.

**Participant flow & lifecycle:**
- `/flow_step` endpoint with metadata persistence (consent seed stored in `debrief_responses.answers.consent`).
- Quiz, risk elicitation, and debrief submission endpoints.
- Admin session/market/round control endpoints.

**Admin operations & safety:**
- Emergency override endpoints with mandatory reason logging to `admin_actions` audit trail:
  - `/admin/sessions/{id}/emergency/round_close`
  - `/admin/sessions/{id}/emergency/market_resolve`
  - `/admin/sessions/{id}/emergency/session_close`
- Admin export endpoints: `/export.csv`, `/export.json`.
- Provisional tournament running tally: `/admin/sessions/{id}/tournament/provisional` (running balance before session close).
- Tournament mark-paid workflow.

**Analysis & calibration tooling:**
- Benchmark recomputation (`analysis/benchmark_recompute.py`): independent verification of Bayesian benchmarks against signal posteriors.
- Outcome variables module (`analysis/outcomes.py`): price accuracy, convergence speed, trading volume, price impact, insider returns, return inequality, information revelation correlation.
- Extended export pipeline (`analysis/export_session_metrics.py`): treatment panel, benchmark recompute, all outcome CSVs.
- Benchmark validator CLI (`calibration/benchmark_validator.py`): end-to-end verification of signal generation and benchmark computation.
- Analysis notebooks: `analysis/01_pilot_review.ipynb`, `analysis/02_main_analysis.ipynb`, `analysis/03_robustness.ipynb`.

**Client UI (`client/`):**
- React/Vite app with participant flow screens, trading screen, lobby, and admin panel.
- Real-time market price/trade updates via Socket.io.
- Emergency override UI with mandatory reason prompts.
- Provisional vs. final tournament display.

**Test coverage:**
- Core math & LMSR tests.
- Benchmark recomputation validation (`tests/test_benchmark_recompute.py`).
- Outcome metrics tests (`tests/test_outcomes.py`).
- API smoke tests with flow metadata and token invalidation (`tests/test_api_smoke.py`).
- Dashboard & Socket.io event emission (`tests/test_dashboard_and_socket.py`).
- Emergency overrides with audit log verification (`tests/test_emergency_overrides.py`).
- Full session flow end-to-end (`tests/test_full_session_flow.py`).

## Run tests

```bash
pytest
```

## Calibration tooling

```bash
python3 calibration/signal_validator.py --samples 10000 --theta 0.85 --true-outcome 1
python3 calibration/b_sweep.py --b-values 10,15,18,20,25 --runs 100
python3 calibration/simulate_market.py --num-traders 16 --rounds 5 --b 18 --true-probability 0.65
```

If backend is running locally:

```bash
python3 calibration/ui_smoketest.py --base-url http://127.0.0.1:8000 --admin-user admin --admin-pass admin
```

## Analysis exports

After a session has data:

```bash
python3 analysis/export_session_metrics.py --session-id 1 --outdir analysis/output
python3 analysis/export_robustness_check.py --session-id 1 --outdir analysis/output
python3 calibration/benchmark_validator.py --session-id 1
```

Notebook artifacts:

- `analysis/01_pilot_review.ipynb`
- `analysis/02_main_analysis.ipynb`
- `analysis/03_robustness.ipynb`

## Ops runbook

- Deployment and pilot protocol: `docs/deployment_runbook.md`
- One-command local smoke checks: `scripts/run_local_smoke.sh`
- Reconnect runtime evidence: `pytest tests/test_socket_reconnect_e2e.py`
