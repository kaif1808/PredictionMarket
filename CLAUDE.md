# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

**Backend startup (with database migrations):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn server.server:combined_app --reload --port 8000
```

**Frontend startup (new terminal):**
```bash
cd client
npm install
npm run dev
```

**Production-style frontend build (served by backend at `/app`):**
```bash
cd client && npm run build && cd ..
uvicorn server.server:combined_app --reload --port 8000
# open http://127.0.0.1:8000/app
```

**Run all tests:**
```bash
pytest
```

**Run specific test file:**
```bash
pytest tests/test_full_session_flow.py -v
```

**Run tests matching a keyword:**
```bash
pytest -k "emergency" -v
```

**Local smoke checks:**
```bash
./scripts/run_local_smoke.sh
```

**Calibration & analysis tools:**
```bash
# Signal validator
python3 calibration/signal_validator.py --samples 10000 --theta 0.85 --true-outcome 1

# Benchmark validator
python3 calibration/benchmark_validator.py --session-id 1

# Export session metrics
python3 analysis/export_session_metrics.py --session-id 1 --outdir analysis/output
```

## Architecture Overview

This is a **full-stack experimental economics platform** implementing the Valdoria prediction market experiment. The core responsibility is orchestrating multi-round trading sessions where participants trade on uncertain outcomes using an LMSR market maker, with information access determined by role-based signal delivery.

### Technology Stack

**Backend:**
- **FastAPI** (web framework) + **Uvicorn** (ASGI server)
- **python-socketio** (real-time WebSocket events)
- **SQLAlchemy** 2.0 (ORM) + **Alembic** (migrations)
- **PostgreSQL** (production) / SQLite (test)
- **Pydantic** (request/response validation)

**Frontend:**
- **React 18** (UI framework)
- **Vite** (bundler)
- **React Router DOM** (navigation)
- **socket.io-client** (real-time events)
- **Tailwind CSS** (styling)
- **React Hook Form** (form state)

**Deployment:**
- **Heroku** (production; see `Procfile`)
- Local SQLite/PostgreSQL for development

### Core Modules

**Backend (`server/`):**

- **`server.py`** — Main FastAPI + Socket.io app. Endpoints for:
  - Session/market/round admin control (`/admin/sessions/*`)
  - Participant flow (consent, quiz, risk elicitation, debrief)
  - Trading (`/trade`, `/fetch_market`)
  - Tournament provisioning and final rankings
  - Emergency overrides with audit logging
  - One-time join tokens with cookie reconnect

- **`orchestrator.py`** — State machine orchestrating session → market → round flow. Manages:
  - Phase transitions (inactive → trading → closed)
  - Round deadline tracking (90-second windows)
  - Market resolution (outcome determination, payout distribution)
  - Tournament ranking computation at session close
  - Recovery from database state on startup

- **`lmsr.py`** — LMSR market maker engine. Core functions:
  - `cost_function(holdings, b)` — cumulative cost
  - `price(holdings, b)` — marginal price
  - `price_impact(trade_amount, current_holdings, b)` — price elasticity
  - `max_purchasable(cash, holdings, b)` — liquidity constraint

- **`bayesian.py`** — Signal generation and posterior computation:
  - `draw_signal(true_outcome, theta)` — generates Bernoulli signals
  - `compute_posterior(signals, prior)` — Bayesian update with Beta conjugate
  - `get_intelligence_assessment(participant, market, round)` — delivers posterior to participant (Stage 1 signals are drawn but suppressed)

- **`roles.py`** — Role rotation and endowment assignment:
  - `assign_roles_for_market(participant_count)` — deterministic role matrix (uninformed, semi-informed θ=0.65, insider θ=0.85)
  - `stage_1_override` — all subjects uninformed in Market 1 (symmetric baseline)
  - Per-participant per-market endowments (default 100 tokens, whales get 400)

- **`scenarios.py`** — Pre-written narrative bulletins (engagement content, no actionable probability):
  - `get_bulletin(market, round, true_outcome)` — returns frozen scenario text

- **`db_models.py`** — SQLAlchemy schema:
  - `SessionModel`, `Market`, `Round`, `Trade`, `Signal`, `MarketRole`
  - `ParticipantSession`, `DebriefResponse`, `QuizAttempt`, `RiskElicitation`
  - `AdminAction` (audit trail for emergency overrides)
  - `TournamentRanking` (final standings with payment status)

- **`db.py`** — Database initialization and session management
- **`config.py`** — Environment variable loading (database URL, log level, etc.)
- **`events.py`** — Pydantic event type definitions for Socket.io payloads

**Frontend (`client/src/`):**

- **`views/` — Page/screen components:**
  - `ParticipantFlow.jsx` — Consent, instructions, quiz, risk elicitation, debrief
  - `TradingScreen.jsx` — Real-time market display, order placement, balance tracking
  - `Lobby.jsx` — Waiting room before round starts
  - `AdminPanel.jsx` — Session/market/round control, emergency overrides, tournament display

- **`types/events.ts`** — TypeScript interfaces for Socket.io events (type safety)

- **`App.jsx`** — Root router and Socket.io setup

**Analysis & Calibration (`analysis/`, `calibration/`):**

- **`analysis/benchmark_recompute.py`** — Independent verification of Bayesian benchmarks
- **`analysis/outcomes.py`** — Outcome variable functions (price accuracy, convergence, volume, etc.)
- **`analysis/export_session_metrics.py`** — Exports treatment panel + all outcome metrics as CSVs
- **`calibration/benchmark_validator.py`** — CLI tool to verify signal delivery and benchmark computation
- **`calibration/signal_validator.py`** — Validates signal generation under different θ values
- **`calibration/b_sweep.py`** — Sensitivity analysis on LMSR `b` parameter
- **`analysis/*.ipynb`** — Jupyter notebooks for exploratory analysis

**Tests (`tests/`):**

- `test_api_smoke.py` — API contract validation (join tokens, flow metadata, consent persistence)
- `test_emergency_overrides.py` — Emergency override endpoints and audit logging
- `test_benchmark_recompute.py` — Bayesian posterior computation verification
- `test_outcomes.py` — Outcome metric function tests
- `test_dashboard_and_socket.py` — Socket.io event emission
- `test_full_session_flow.py` — End-to-end participant flow
- Plus ~25 other tests covering LMSR, roles, orchestrator, etc.

### Data Flow

1. **Session Creation** → Admin creates session via POST `/admin/sessions`, specifying participant count and market configuration
2. **Join Phase** → Participants exchange one-time join token for session cookie at POST `/auth/join`
3. **Consent & Flow** → Participants navigate flow screens (consent, instructions, quiz, risk elicitation), state stored in `debrief_responses`
4. **Market Rounds** → For each market:
   - Round starts, 90-second deadline set (`round_deadline_unix_ms` in `round_started` event)
   - Participants trade via Socket.io `/trade` event
   - Prices update in real-time via `price_update` event
   - Round closes, `round_volume` emitted, market resolves with:
     - Public `market_outcome_public` event (outcome + true probability) broadcast to all
     - Private `market_resolved` event (payout + final balance + PnL) sent per-participant
5. **Debrief & Tournament** → After all markets, session closed, debrief responses collected, tournament rankings computed and displayed

### Key Design Patterns

**One-Time Join Tokens with Cookie Reconnect:**
- First POST `/auth/join` with token → token invalidated, cookie set
- Subsequent requests use cookie (allows reconnect on connection drop)
- Prevents token replay/sharing

**Public/Private Event Split:**
- Market resolution outcomes sent as public broadcast (all participants see same outcome)
- Payouts and PnL sent as private roomed events (each participant sees own numbers)

**Role-Gated Signal Delivery:**
- Signals drawn for all tiers in Stages 2–4, but:
  - Uninformed tier: no posterior delivered
  - Semi-informed (θ=0.65): posterior delivered
  - Insider (θ=0.85): posterior delivered
  - Stage 1 Market 1: ALL subjects uninformed (symmetric baseline), signals drawn but suppressed

**Emergency Overrides with Audit Logging:**
- Three endpoints: `emergency/round_close`, `emergency/market_resolve`, `emergency/session_close`
- All require mandatory reason string (1–500 chars)
- Logged to `admin_actions` table with timestamp, admin user, session/market context
- UI prompts for reason before allowing override

**Tournament Running Tally:**
- Provisional rankings via GET `/admin/sessions/{id}/tournament/provisional` (available mid-session)
- Final rankings via GET `/admin/sessions/{id}/tournament` (computed at session close)
- Top 3 by total tokens across all markets win €5 / €3 / €2 (payment manual)

## Important Notes

- **Heroku WebSocket Behavior:** [VERIFY] The production deployment assumes standard Heroku dynos support WebSocket persistence. Confirm against current Heroku docs before production deployment.
- **Database Migrations:** Always run `alembic upgrade head` after pulling new code; migrations are deterministic and tied to session state.
- **Real-time Expectations:** Socket.io events are emitted synchronously during round close; expect latency ≤1s for broadcast to 16 participants on local network. Load testing is a remaining gap for production readiness.
- **Consent Metadata:** Consent seed is stored in `debrief_responses.answers["consent"]` for downstream analysis; critical for GDPR compliance workflows.
- **Analysis Separation:** Backend is kept clean of analysis code; all recomputation, outcome metrics, and export logic lives in `analysis/` and `calibration/` for reproducibility.

## Test Coverage & Markers

All tests are integration-style (exercise real database + API paths). Markers available:

```bash
pytest -m integration  # future: tests marked @pytest.mark.integration
```

Current test categories:
- **API Smoke** (3 tests): token reuse, flow metadata, consent persistence
- **Emergency Overrides** (1 test): reason requirement, endpoint checks, audit log
- **Benchmark** (2 tests): Bayesian posterior recomputation
- **Outcomes** (1 test): outcome metric function validation
- **Full Flow** (1 test): end-to-end session orchestration
- **Math & Core** (~25 tests): LMSR, role rotation, scenarios, orchestrator state machine

## Verification Before Commit

- `pytest` should pass (35+ tests, all green)
- `npm --prefix client run build` should succeed (check bundle size in build log)
- `alembic upgrade head` should run cleanly (check that no schema conflicts exist)
- Manual smoke: `./scripts/run_local_smoke.sh` exercises key API paths end-to-end

## Production Readiness Gaps

Per VALDORIA_AGENT_BIBLE.md, these remain before "Experiment Ready":

1. **Full Contract Enforcement** — Socket.io event payloads validated against TypeScript interfaces; client-side type checking
2. **Load Testing** — Multi-session concurrency (16 participants × 3+ markets × 5 rounds), latency percentiles, graceful degradation
3. **Deployment-Realistic Verification** — Heroku WebSocket behavior, session persistence across dyno restarts, connection pooling under load, CORS/cookie hardening
