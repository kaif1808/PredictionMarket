# Valdoria Prediction Market — Agent Instructional Bible
### Production specification for parallel AI coding agents
*Version 1.1 · May 2026*

---

## Changelog

**v1.1 (this revision):**
- All ten Part 11 decisions ratified by project lead. Section reformatted from "open" to "ratified."
- **Multi-session concurrency added.** Architecture, orchestrator, server, and admin panel updated to support multiple sessions running concurrently. Database schema unchanged (already supported it).
- **Configurable subject count** (default 16, range 8–20). Role rotation matrix becomes a function rather than a lookup table.
- **Review Agent formalised** as a seventh role in Part 6 with explicit workflow, ownership, and gate criteria.
- **Stage 1 signal handling clarified:** signals are drawn and stored but not delivered to subjects. Suppression layer added to Bayesian service.
- **Tournament payment structure ratified:** end-of-session top-3 by total tokens across all 4 markets win €5 / €3 / €2 respectively. `tournament_rankings` table added; orchestrator computes at session close; admin panel displays and supports "mark paid." Payment processing remains manual.

**v1.0:** Initial release.

---

## How to Read This Document

This bible is the single source of truth for building the Valdoria prediction market experiment. It exists for two audiences:

- **The project lead** (you) — to verify decisions, resolve open questions, and ratify the build sequence.
- **AI coding subagents** — to receive scoped, contract-bound work packages they can execute in parallel without merging conflicts.

Sections are ordered from "what" to "how" to "do." Subagents should read Parts 0–3 fully, then jump to the module specifications they own in Part 5 and the build sequence in Part 7.

**A note on certainty.** Some recommendations in this document depend on framework behaviour I cannot fully verify from inside this drafting context (notably: Heroku's current WebSocket handling on standard dynos, and oTree LiveMethods' performance under load). Where this is the case, I mark the claim with **[VERIFY]** and the agent responsible should confirm against current docs before relying on it.

---

## Part 0 — Provenance and Conflicts

This bible derives from two source documents and three reference papers:

- **`prediction_market_design.md`** — the experimental design (the *spec*).
- **`VALDORIA_CODE_INSTRUCTIONS.md`** — an existing reference implementation (the *scaffold*).
- Deck, Lin & Porter (2013); Mantovani & Filippin (2026); Saguillo et al. (2025) — empirical and methodological context.

The spec and the scaffold diverge in seven material ways. The bible resolves each:

| # | Spec says | Scaffold does | Resolution |
|---|---|---|---|
| 1 | 4 markets per session | 3 markets per session | Extend to 4. Add Market 1 as symmetric baseline. |
| 2 | Insider receives Bayesian posterior P(conflict) drawn from θ=0.85 | Insider sees next round's classified narrative | Add a Bayesian signal layer alongside the narrative. Narrative is engagement; posterior is the actionable signal. |
| 3 | Semi-informed tier with θ=0.65 | "Partial" tier with scripted "Analytical assessment: 65% probability the next update will report…" | Replace scripted partial-tier text with computed posterior for informed subjects. Retain narrative for engagement. |
| 4 | Whales (400 tokens) in Markets 3 and 4 | Single endowment tier (100 tokens) | Add `endowment_size` field per participant per market. |
| 5 | Symmetric baseline (all uninformed, Market 1) | Mixed roles in Market 1 | Override Market 1 role assignment to "uninformed" for all. Suppress signal draws. |
| 6 | Local LAN deployment | Local LAN deployment | Override: web deployment to Heroku, per project lead direction. |
| 7 | Formal Bayesian benchmark price computed and stored | No benchmark computation | New module: `bayesian.py`. |

Each resolution is implemented as a discrete task in Part 7.

---

## Part 1 — Framing Decisions

These are the decisions everything else hangs on. The project lead should ratify or override before agents begin work.

### 1.1 Stack: extend Valdoria, do not migrate to oTree

**Recommendation: extend the existing FastAPI + python-socketio + React scaffold and deploy that to Heroku.**

Reasons:

- The scaffold already implements LMSR maths, scenario data, role rotation, role-gated bulletins, the database schema, and the admin control surface. Migrating to oTree means rewriting all of that against oTree's session/group/round model.
- oTree's page-based flow is awkward for continuous 90-second trading windows. Real-time updates require its LiveMethods feature, and **[VERIFY]** I am not certain LiveMethods sustains sub-second broadcasts to 16 simultaneous traders without performance issues. This is a load-test question, not a feature question, and bearing that risk on the trading core is a poor trade.
- oTree's *strengths* are the auxiliary phases (consent, instructions, comprehension quiz, risk elicitation, debrief). Those can be implemented as additional React screens in the existing stack for far less than the cost of porting the trading engine.
- Heroku supports both stacks equally well. The framework choice is independent of the deployment platform.

**Fallback path (if you want oTree anyway):** Part 9.4 sketches what a pure-oTree build would look like and where the load-test would need to land before commit.

### 1.2 Information structure: layered narrative + computed posterior

For informed subjects (semi-informed and insider tiers) in Stages 2, 3 (insider-whale only), and 4:

- A signal is drawn each round from the Bernoulli distribution conditional on the true outcome, with precision θ matched to tier (0.65 semi, 0.85 insider).
- The cumulative posterior P(YES | signals received so far) is computed server-side and delivered to the participant as the *intelligence assessment*.
- The Valdoria narrative bulletin is delivered to **all** participants alongside, providing context and engagement but no actionable probability content (per the design doc).

For uninformed subjects in any stage: narrative only, no signal, no posterior.

For all subjects in the symmetric baseline (Stage 1, Market 1): narrative only, no signal, no posterior, regardless of role rotation matrix. Stage 1 overrides individual roles.

### 1.3 The LLM narrator question

**Recommendation: no LLM in the live loop. Pre-written, frozen narrative only.**

Reasoning:

- Within-subject design demands that the same scenario reads identically across sessions and subjects.
- LLM stochasticity is an unmeasured confound that mixes with the very treatment effects you are measuring.
- The narrative is already written (`scenarios.py`). There is no production need to regenerate it.
- The risk is asymmetric: tiny upside (varied language) vs material downside (uncontrolled scenario variance).

**Productive offline uses of an LLM** (not blocked, but kept out of the experimental loop):

- Generating candidate variant scenarios for piloting before the production text is locked.
- Stress-testing existing bulletin language for ambiguity or unintended leakage of the answer.
- Producing synthetic transcripts for analysis-pipeline development before any real subjects run.

These are dev-time tools, not session-time services. They should not touch the production server.

### 1.4 Deployment: Heroku, Postgres, WebSockets

- Backend: Heroku web dyno running `uvicorn` with the combined ASGI app (FastAPI + python-socketio).
- Database: **switch SQLite → Postgres**. Heroku Postgres add-on. SQLite's single-writer model is acceptable in a single-laptop LAN deployment but is fragile under web concurrency and is wiped on dyno restart.
- Frontend: static React build served from a separate static-hosting layer (Heroku static buildpack, Vercel, or Netlify), or co-served from FastAPI under `/`. Co-serving is simplest.
- WebSockets: python-socketio supports WebSocket transport. **[VERIFY]** Confirm Heroku's current support for long-lived WebSocket connections on the dyno tier you choose; verify the 30-second router timeout does not break Socket.io's heartbeat.

### 1.5 Subjects, auth, and identifiers

Lab IDs alone are not appropriate for web deployment with multiple concurrent sessions. Replace with:

- Per-session join tokens generated by the experimenter and distributed before each session. A token encodes `(session_id, slot_index)` and resolves to an internal participant ID scoped to that session.
- Internal participant IDs remain `P01`..`Pnn` for analysis continuity with the role rotation matrix, BUT are scoped per session. `P01` in Session 42 is a different person from `P01` in Session 43.
- Tokens are one-time-use. Re-joining after disconnect uses the session cookie set by the original token exchange.

### 1.6 Ratified scope decisions (formerly Part 11)

The ten decisions in Part 11 are now ratified. The headline architectural commitments:

- **Default 16 subjects per session, configurable 8–20.** Multiple concurrent sessions supported.
- **Stage 1 signals drawn but not delivered.** Server stores them for analytical benchmark; subjects do not see them.
- **No Stage 3b variant.** Ship as designed; flag null risk in analysis.
- **3 rotation matrices,** parameterised by subject count.
- **Holt-Laury risk elicitation, 10 rows.**
- **No pre-registration before pilot.** Project lead's call.
- **Same B parameter across all stages within a session.**
- **Max trade size 20 contracts per submission.**
- **Resolution shown publicly; payouts shown privately.**
- **Payment infrastructure deferred** — stubbed but unimplemented. See risk note in Part 11.

---

## Part 2 — Architecture

### 2.1 Component diagram (textual)

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (React)                            │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────────────┐    │
│  │  Auxiliary   │  │   Trading      │  │  Admin Console          │    │
│  │  Flow:       │  │   View:        │  │  (experimenter only)    │    │
│  │  Consent,    │  │   - Price      │  │  - Session start        │    │
│  │  Instructions│  │   - Posterior  │  │  - Market start         │    │
│  │  Quiz,       │  │   - Narrative  │  │  - Round start/stop     │    │
│  │  Holt-Laury, │  │   - Trade form │  │  - Resolution           │    │
│  │  Debrief     │  │   - Portfolio  │  │  - Export               │    │
│  └──────┬───────┘  └────────┬───────┘  └────────────┬────────────┘    │
│         │ HTTPS              │ HTTPS+WS              │ HTTPS+WS         │
└─────────┼────────────────────┼───────────────────────┼─────────────────┘
          │                    │                       │
┌─────────▼────────────────────▼───────────────────────▼─────────────────┐
│                          SERVER (FastAPI + Socket.io)                  │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │  Auth /      │  │  Orchestrator│  │  Admin handlers          │    │
│  │  Tokens      │  │  (state      │  │  (start/stop/resolve)    │    │
│  │              │  │  machine)    │  │                          │    │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘    │
│         │                  │                       │                   │
│         └──────────┬───────┴───────────────────────┘                   │
│                    │                                                    │
│  ┌─────────────────▼────────────────────────────────────────────┐     │
│  │                Domain services                               │     │
│  │  ┌─────────┐  ┌────────────┐  ┌─────────────┐  ┌──────────┐ │     │
│  │  │  LMSR   │  │  Signal &  │  │  Scenario   │  │  Role &  │ │     │
│  │  │  engine │  │  Bayesian  │  │  data       │  │  Endow-  │ │     │
│  │  │         │  │  benchmark │  │             │  │  ment    │ │     │
│  │  └─────────┘  └────────────┘  └─────────────┘  └──────────┘ │     │
│  └────────────────────────┬─────────────────────────────────────┘     │
│                           │                                            │
│  ┌────────────────────────▼─────────────────────────────────────┐     │
│  │              Persistence (SQLAlchemy → Postgres)             │     │
│  └──────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          ANALYSIS PIPELINE                             │
│  (Offline, post-session — Python / R notebooks consuming CSV exports)  │
│  - Bayesian benchmark recomputation (sanity check)                     │
│  - Price-path deviation metric                                         │
│  - Convergence speed                                                   │
│  - Return inequality (Gini) by role type                               │
│  - Price impact regressions                                            │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data flow for one trading round

1. Admin POSTs `/admin/start_round` with round number.
2. Orchestrator advances state, locks `trading_open = True`.
3. For each participant: signal module draws a signal (if their tier warrants), computes posterior, stores both server-side, and emits a private `round_started` event with `{ narrative, posterior?, balance, role, current_price }`.
4. Participants trade via `POST /trade`. Server validates, calls LMSR engine for cost and new price, persists trade, broadcasts `price_update`.
5. After 90 seconds (or admin-triggered), admin POSTs `/admin/end_round`. Orchestrator locks `trading_open = False`, computes Bayesian benchmark price for the round given all signal realisations, persists snapshot, broadcasts `round_ended`.
6. Repeat for rounds 2–5.
7. After round 5, admin POSTs `/admin/resolve_market`. Server draws outcome ~ Bernoulli(true_probability), pays off contracts, broadcasts private `market_resolved` to each participant.

### 2.3 State boundaries

- **Authoritative state** lives in Postgres. The server's in-memory `sessions_by_id` dict is a *cache* of all currently-active sessions, keyed by session ID. On dyno restart, the cache must be rebuildable from the database within five seconds; the database schema in Part 4 supports this for any number of concurrent sessions.
- **Subject's local state** (React) is read-only mirrors of server state plus UI ephemera (form input). Never trust client-side balance or holdings; always re-validate server-side.
- **Admin state** is privileged read+write across all sessions. The admin panel scopes operations by session ID picked from a selector.

### 2.4 Concurrency model

The server runs as a single uvicorn worker. Inside that worker, FastAPI handles request concurrency via asyncio; Socket.io rooms are partitioned by session to keep broadcasts scoped.

Socket.io room naming convention:

```
session:{session_id}:all                    # all participants in a session
session:{session_id}:participant:{pid}      # private to one participant
session:{session_id}:admin                  # admin observers of that session
```

A participant connecting with cookie `(session_id=42, participant_id=P03)` is auto-joined to `session:42:all` and `session:42:participant:P03`. Admins joining a session subscribe to that session's `:admin` room.

For ≤ 5 concurrent sessions of 16 subjects each (≈ 80 simultaneous WebSocket connections plus admin observers), a single basic Heroku dyno is expected to be sufficient. **[VERIFY under load test in Phase 4.]** Beyond that, you'd need to move state out of in-process memory (Redis pub/sub) and run multiple workers — out of scope for v1.1.

---

## Part 3 — Stack and Tooling

| Layer | Technology | Source |
|---|---|---|
| Backend framework | FastAPI | Existing |
| Real-time | python-socketio (ASGI mode) | Existing |
| ORM / DB driver | SQLAlchemy 2.x + `psycopg[binary]` | **New** (was raw `sqlite3`) |
| Database | Postgres 15+ (Heroku Postgres add-on) | **New** (was SQLite) |
| Migrations | Alembic | **New** |
| Frontend framework | React 18 + Vite | Existing |
| Real-time client | `socket.io-client` v4 | Existing |
| Component style | TailwindCSS | **New** for auxiliary screens; existing trading view keeps its inline styles |
| Forms | React Hook Form | **New** for consent, quiz, Holt-Laury |
| Build | Vite static build → served by FastAPI | Existing pattern, new step |
| Hosting | Heroku (eco or basic dyno + Heroku Postgres mini) **[VERIFY]** | **New** |
| Process manager | `uvicorn` invoked via Procfile | **New** |
| Secrets | Heroku config vars | **New** |
| Logging | Python `logging` to stdout (Heroku log drain) | **New** |
| Monitoring | Heroku metrics; optionally Sentry for exception tracking | **New** |
| Analysis | Python (pandas, scipy, statsmodels) | **New** |

### 3.1 Why SQLAlchemy + Alembic, not raw `sqlite3` ported to Postgres

- SQLAlchemy isolates the Postgres-vs-SQLite swap behind a connection string. The scaffold's raw `sqlite3` calls hard-code the dialect and would need rewriting anyway.
- Alembic makes schema evolution safe in production. Without it, the first time you need to add a column on a live Heroku Postgres instance, you lose data.
- Per the user preferences I'm working under: I do not invent SQLAlchemy 2.x APIs. The agent implementing this module verifies syntax against current SQLAlchemy docs before using it.

### 3.2 Why Vite, not Create React App

CRA is deprecated. Vite is the current React community default for new projects. The existing `valdoria_market.jsx` is framework-agnostic and ports trivially.

### 3.3 Python and Node versions

- Python: 3.11 (Heroku supported; matches FastAPI requirements; 3.10 also acceptable per scaffold).
- Node: 20 LTS.
- Pin both in `runtime.txt` and `.nvmrc` to ensure reproducible builds.

---

## Part 4 — Data Model

### 4.1 Entities and relationships

```
session
  ├── 1..* participant_session   (one row per participant per session)
  ├── 1..* market                (4 markets per session)
  │        ├── 1..* market_role  (one row per participant per market: role, endowment)
  │        ├── 1..* round        (5 rounds per market)
  │        │       ├── 1..* signal     (one row per informed participant per round)
  │        │       ├── 1..* trade      (zero-or-more per participant per round)
  │        │       └── 1   round_snapshot  (closing state per round)
  │        └── 1   market_resolution
  ├── 1   risk_elicitation (Holt-Laury result per participant, session-level)
  └── 1   debrief_response  (free-text feedback)
```

### 4.2 Schema (Postgres DDL — Alembic-managed)

```sql
-- sessions
CREATE TABLE sessions (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    session_label   TEXT NOT NULL,        -- e.g. "S2026-05-27-A"
    rotation_id     INT NOT NULL,         -- which rotation matrix (1, 2, 3, ...)
    scenario_order  TEXT NOT NULL,        -- e.g. "C,A,B,C" — 4 markets
    notes           TEXT
);

-- participants (long-lived identifiers; one row per unique person)
CREATE TABLE participants (
    id              TEXT PRIMARY KEY,     -- e.g. "P01"
    join_token      TEXT UNIQUE,          -- web-deploy auth token
    external_id     TEXT,                 -- Prolific ID etc., nullable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- participant_session: which participants are in which session
CREATE TABLE participant_sessions (
    session_id      BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id  TEXT   REFERENCES participants(id),
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, participant_id)
);

-- markets
CREATE TABLE markets (
    id                  BIGSERIAL PRIMARY KEY,
    session_id          BIGINT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    market_number       SMALLINT NOT NULL CHECK (market_number BETWEEN 1 AND 4),
    scenario_id         CHAR(1) NOT NULL,
    true_probability    NUMERIC(5,4) NOT NULL,
    stage               SMALLINT NOT NULL,        -- 1 baseline, 2 info, 3 endow, 4 combined
    b_parameter         NUMERIC(8,4) NOT NULL,    -- LMSR liquidity for this market
    q_yes               NUMERIC(12,4) NOT NULL DEFAULT 0,
    q_no                NUMERIC(12,4) NOT NULL DEFAULT 0,
    opened_at           TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    UNIQUE (session_id, market_number)
);

-- market_roles: per-participant per-market assignment
CREATE TABLE market_roles (
    market_id           BIGINT REFERENCES markets(id) ON DELETE CASCADE,
    participant_id      TEXT   REFERENCES participants(id),
    role_tier           TEXT NOT NULL CHECK (role_tier IN ('uninformed','semi_informed','insider')),
    endowment_tokens    NUMERIC(10,2) NOT NULL,
    starting_balance    NUMERIC(12,4) NOT NULL,
    final_balance       NUMERIC(12,4),
    yes_held            NUMERIC(12,4) NOT NULL DEFAULT 0,
    no_held             NUMERIC(12,4) NOT NULL DEFAULT 0,
    PRIMARY KEY (market_id, participant_id)
);

-- rounds
CREATE TABLE rounds (
    id                  BIGSERIAL PRIMARY KEY,
    market_id           BIGINT NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    round_number        SMALLINT NOT NULL CHECK (round_number BETWEEN 1 AND 5),
    opened_at           TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ,
    opening_price       NUMERIC(7,6),
    closing_price       NUMERIC(7,6),
    bayesian_benchmark  NUMERIC(7,6),         -- computed at round close
    UNIQUE (market_id, round_number)
);

-- signals (private; may or may not be delivered to subject)
CREATE TABLE signals (
    id                  BIGSERIAL PRIMARY KEY,
    round_id            BIGINT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    participant_id      TEXT   NOT NULL REFERENCES participants(id),
    signal_value        CHAR(1) NOT NULL CHECK (signal_value IN ('H','L')),
    theta               NUMERIC(4,3) NOT NULL,   -- 0.650 or 0.850
    posterior           NUMERIC(7,6) NOT NULL,   -- cumulative posterior after this signal
    delivered           BOOLEAN NOT NULL DEFAULT TRUE, -- FALSE for Stage 1 suppression
    delivered_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (round_id, participant_id)
);

-- trades
CREATE TABLE trades (
    id                  BIGSERIAL PRIMARY KEY,
    round_id            BIGINT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    participant_id      TEXT   NOT NULL REFERENCES participants(id),
    direction           CHAR(3) NOT NULL CHECK (direction IN ('yes','no')),
    quantity            INT    NOT NULL CHECK (quantity > 0),
    cost                NUMERIC(12,4) NOT NULL,
    price_before        NUMERIC(7,6) NOT NULL,
    price_after         NUMERIC(7,6) NOT NULL,
    q_yes_after         NUMERIC(12,4) NOT NULL,
    q_no_after          NUMERIC(12,4) NOT NULL,
    executed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX trades_round_idx ON trades(round_id);
CREATE INDEX trades_participant_idx ON trades(participant_id);

-- market resolution
CREATE TABLE market_resolutions (
    market_id           BIGINT PRIMARY KEY REFERENCES markets(id) ON DELETE CASCADE,
    outcome             SMALLINT NOT NULL CHECK (outcome IN (0,1)),
    resolved_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    rng_seed            TEXT                       -- for audit
);

-- risk elicitation (session-level, one per participant per session)
CREATE TABLE risk_elicitations (
    session_id          BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id      TEXT   REFERENCES participants(id),
    instrument          TEXT NOT NULL,          -- 'holt_laury_10' or 'binary_lottery'
    switch_point        SMALLINT,               -- for HL: row where switched A→B
    raw_choices         JSONB,
    PRIMARY KEY (session_id, participant_id)
);

-- comprehension quiz attempts
CREATE TABLE quiz_attempts (
    session_id          BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id      TEXT   REFERENCES participants(id),
    quiz_name           TEXT NOT NULL,
    attempts            SMALLINT NOT NULL,
    final_correct       BOOLEAN NOT NULL,
    raw_answers         JSONB,
    PRIMARY KEY (session_id, participant_id, quiz_name)
);

-- debrief
CREATE TABLE debrief_responses (
    session_id          BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id      TEXT   REFERENCES participants(id),
    answers             JSONB NOT NULL,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, participant_id)
);

-- tournament: end-of-session top-3 by total tokens across all 4 markets
-- Prizes: rank 1 → €5, rank 2 → €3, rank 3 → €2
CREATE TABLE tournament_rankings (
    session_id          BIGINT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id      TEXT   REFERENCES participants(id),
    total_tokens        NUMERIC(14,4) NOT NULL,  -- sum of final_balance across 4 markets
    rank                INT NOT NULL,
    prize_eur           NUMERIC(6,2) NOT NULL DEFAULT 0.00,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    paid_at             TIMESTAMPTZ,             -- set when payment processed (manual or vendor)
    PRIMARY KEY (session_id, participant_id)
);
CREATE INDEX tournament_rank_idx ON tournament_rankings(session_id, rank);
```

### 4.3 Reconstruction from DB after dyno restart

The `state` cache can be rebuilt by reading:

- The latest `sessions` row with `closed_at IS NULL`.
- The current `markets` row for that session with the highest `market_number` where `closed_at IS NULL`.
- The current `rounds` row similarly.
- All `market_roles` for that market.
- Sum `trades` per participant to recover holdings.

The orchestrator MUST implement this on startup. Acceptance: kill the dyno mid-session, restart, all clients reconnect and resume within five seconds.

---

## Part 5 — Module Specifications

Each module below is owned by exactly one subagent. Module boundaries are tight to enable parallel work without merge conflicts. Where modules depend on each other, the *interface* is frozen first (contracts in Part 6).

### 5.1 LMSR Engine — `server/lmsr.py`

**Status:** Exists. Minor extensions only.

**Interface:**

```python
def price(q_yes: float, q_no: float, b: float) -> float
def cost(q_yes: float, q_no: float, d_yes: float, d_no: float, b: float) -> float
def price_after(q_yes: float, q_no: float, d_yes: float, d_no: float, b: float) -> float
```

**Extension required:**
- Take `b` as a parameter (currently a module-level constant). Different markets within a session may use different B values during calibration.
- Add `price_impact(q_yes, q_no, d_yes, d_no, b) -> float` returning `price_after - price_before`.
- Add `max_purchasable(q_yes, q_no, balance, direction, b) -> int` returning the largest integer quantity the participant can afford in that direction.

**Acceptance tests (`tests/test_lmsr.py`):**
- Starting price at q_yes = q_no = 0 is exactly 0.5 for any B > 0.
- `cost(...)` is strictly positive for any positive purchase.
- `price_after` is strictly between 0 and 1.
- `price(q, q, b) == 0.5` for all q.
- Buying YES strictly increases price; buying NO strictly decreases.
- `max_purchasable` never returns a quantity whose cost exceeds balance.
- Numerical stability: handle q values up to 10000 without overflow (use `logsumexp`-style stabilisation if needed).

**Owned by:** MarketEngine Agent.

---

### 5.2 Bayesian Signal & Benchmark Service — `server/bayesian.py` (NEW)

**Purpose:** Draw private signals, compute posteriors, compute the rational benchmark price at round close.

**Interface:**

```python
@dataclass
class SignalDraw:
    value: Literal["H", "L"]
    theta: float
    posterior: float                 # P(YES | all signals received by this participant so far)
    delivered: bool                  # True for tiers in stages 2-4; False for Stage 1 (drawn-but-suppressed)

def draw_signal(true_outcome: int, theta: float, rng: Random) -> Literal["H","L"]
    """Draws H with probability theta if true_outcome=1, else with probability 1-theta."""

def update_posterior(prior: float, signal: Literal["H","L"], theta: float) -> float
    """Bayesian update. Returns new posterior."""

def benchmark_price(prior: float, all_signals: list[tuple[str, float]]) -> float
    """Computes the rational risk-neutral price given all signals delivered to all
    informed subjects up to round close. `all_signals` is a list of (signal_value, theta)
    pairs across every informed participant. Returns the posterior assuming all
    private information were pooled."""

def draw_for_round(
    session_id: int,
    market_id: int,
    round_id: int,
    market_roles: list[MarketAssignment],
    true_outcome: int,
    stage: int,
) -> list[SignalDraw]:
    """For each participant in the market, draws a signal at their tier's precision.
    Stage 1: signals drawn for all participants at θ=0.65, stored with delivered=False.
    Stages 2-4: signals drawn at each participant's tier precision (uninformed = no draw)
    with delivered=True. Returns all draws; caller persists and decides what to emit."""
```

**Stage 1 signal-suppression rule:**
The design doc's Stage 1 says no signals are delivered to subjects. v1.1 extends this: signals ARE drawn at θ=0.65 for all participants and persisted to the `signals` table with a flag (`delivered=False`). The orchestrator suppresses delivery to clients (no `posterior` in `round_started`, no `analytical` bulletin field). The analysis pipeline can then compute a benchmark for Stage 1 on the same footing as Stages 2–4, which makes the price-path-deviation metric directly comparable across stages. This is a v1.1 decision made on the project lead's direction; it is not in the original design doc.

**Implementation notes:**

The Bayesian update for a single signal with precision θ:
- If signal = H: posterior = (prior · θ) / (prior · θ + (1 - prior) · (1 - θ))
- If signal = L: posterior = (prior · (1 - θ)) / (prior · (1 - θ) + (1 - prior) · θ)

The aggregate benchmark price assumes signals are conditionally independent given the true outcome. Likelihood ratios multiply:

```
L_aggregate = ∏_i L(s_i, θ_i)
posterior   = prior · L_aggregate / (prior · L_aggregate + (1 - prior) · (1 / L_aggregate_complement))
```

where L(H, θ) = θ / (1-θ) and L(L, θ) = (1-θ) / θ. Implementation must use log-likelihoods for numerical stability when signal counts are large.

**Random source:**
- Use `random.Random(seed)` seeded per `(session_id, market_id, round_id, participant_id)` so runs are deterministically reproducible from logs. Store the seed in the `signals` table for audit.

**Acceptance tests:**
- Drawing 100,000 signals with θ=0.85 and true_outcome=1 yields ~85% H signals (binomial within tolerance).
- Posterior monotonically moves toward 1 with each H signal, toward 0 with each L signal.
- After many signals, posterior approaches truth — for θ=0.85 and true_outcome=1, posterior > 0.99 after 20 H signals.
- Benchmark computation matches a hand-checked example (provided in Appendix A).
- Determinism: same seed → identical signal sequence.

**Owned by:** MarketEngine Agent (same agent as 5.1 — these are tightly coupled mathematical modules).

---

### 5.3 Scenario Data — `server/scenarios.py`

**Status:** Exists with three scenarios (A, B, C) and three roles (uninformed, partial, insider). Requires modification.

**Changes:**

- Remove the scripted "Analytical assessment: 65% probability the next update will…" from the `partial` field — this conflicts with the formal Bayesian signal layer. Replace with a generic narrative bulletin appropriate for an analyst tier (commentary on the public situation, no embedded probability number).
- Remove the next-round-classified peek from the `insider` field. The narrative for `insider` becomes a more detailed analytical commentary, still no embedded probability number.
- Add a `stage_1_baseline` mode where all participants see only the `public` field regardless of role.

**New interface:**

```python
def get_bulletin(scenario_id: str, round_number: int, role_tier: str, stage: int) -> dict:
    """
    Returns: {
        "public":   str,         # always present
        "analytical": str | None # only for semi_informed and insider; None for uninformed
        "intelligence": str | None # only for insider; richer commentary
    }
    Stage 1 overrides: always returns only {"public": ..., "analytical": None, "intelligence": None}.
    """
```

The posterior P(YES) is delivered SEPARATELY via the round_started event payload — it is not embedded in the bulletin text. This separates engagement content from actionable signal.

**Acceptance tests:**
- All four scenarios (A, B, C, plus a placeholder fourth if needed for Market 1 rotation) return six rounds of bulletins (rounds 1–5 plus a resolution narrative for round 6).
- No bulletin text contains a number that could be interpreted as the answer (no "75%", "85%", etc.).
- Stage 1 returns identical content for all role tiers.

**Owned by:** Scenarios Agent.

---

### 5.4 Role Rotation & Endowment Assignment — `server/roles.py`

**Status:** Exists for 3 markets × 10 participants × 3 sessions. Must extend to 4 markets and add endowment field.

**New interface:**

```python
@dataclass
class MarketAssignment:
    role_tier: Literal["uninformed", "semi_informed", "insider"]
    endowment_tokens: float

def get_assignment(session_rotation_id: int, participant_id: str, market_number: int) -> MarketAssignment

def get_scenario_for_market(session_rotation_id: int, market_number: int) -> str
    # Stage 1 always uses scenario C (symmetric baseline, true_p = 0.50)
    # Stages 2, 3, 4 cycle A, B with a fourth scenario for combined.

def validate_rotation_matrix(rotation: dict) -> list[str]
    """Returns list of validation errors. Used at server startup."""
```

**Constraints to validate:**

- Every participant experiences at least two distinct role tiers across the four markets.
- Stage 1 (Market 1) is always "uninformed" + 100 tokens for everyone.
- Stage 2 (Market 2) has exactly 2 insiders + 4 semi-informed + 4–6 uninformed.
- Stage 3 (Market 3) has exactly 2 whales (400 tokens) + 8–10 normals (100 tokens), all uninformed.
- Stage 4 (Market 4) has exactly 2 insider-whales (400 tokens + θ=0.85) + 4 semi-normal + 4–6 uninformed-normal.
- Across N sessions, the assignment matrix should be permuted so subjects who were insiders in Session 1 are not also insiders in Session 2 (where the same participant ID is reused — typically not the case if subjects are recruited per-session, but the rotation supports it).

**Acceptance tests:**
- `validate_rotation_matrix(ROTATION_1)` returns empty list.
- Hand-crafted bad matrix (e.g. three insiders in Stage 2) returns appropriate error strings.
- All stage-2/3/4 endowment+role combinations sum to expected totals.

**Owned by:** Scenarios Agent (same owner as 5.3 — tightly coupled).

---

### 5.5 Session Orchestrator — `server/orchestrator.py` (NEW)

**Purpose:** State machine for session → market → round transitions, supporting multiple concurrent sessions. Lifts orchestration logic out of `server.py` and gives it a clean unit-testable interface.

**Interface:**

```python
class SessionPhase(Enum):
    IDLE = "idle"
    SESSION_OPEN = "session_open"
    MARKET_OPEN = "market_open"
    ROUND_OPEN = "round_open"
    ROUND_CLOSED = "round_closed"
    MARKET_RESOLVED = "market_resolved"
    SESSION_CLOSED = "session_closed"

@dataclass
class SessionState:
    session_id: int
    phase: SessionPhase
    current_market_number: int | None
    current_round_number: int | None
    market_cache: dict          # in-memory cache of market state
    participants_cache: dict    # participant_id -> {balance, yes_held, no_held, role, endowment}

class Orchestrator:
    def __init__(self, db_session_factory, lmsr_engine, bayesian_service):
        self.sessions: dict[int, SessionState] = {}    # keyed by session_id

    # --- Lifecycle ---
    def start_session(self, label: str, rotation_id: int, subject_count: int) -> int: ...
    def start_market(self, session_id: int, market_number: int) -> Market: ...
    def start_round(self, session_id: int, round_number: int) -> Round: ...
    def record_trade(self, session_id: int, trade: TradeRequest) -> TradeResult: ...
    def end_round(self, session_id: int) -> RoundSnapshot: ...   # Triggers benchmark
    def resolve_market(self, session_id: int) -> MarketResolution: ...
    def close_session(self, session_id: int) -> TournamentResult: ...  # Computes tournament

    # --- Tournament (Option 2 payment structure) ---
    def compute_tournament(self, session_id: int) -> list[TournamentRanking]:
        """Sums each participant's final_balance across all 4 markets.
        Ranks descending. Assigns prizes: rank 1 → €5, 2 → €3, 3 → €2.
        Ties broken by random number seeded with session_id (recorded for audit).
        Persists to tournament_rankings table. Idempotent."""

    # --- Recovery ---
    def restore_from_db(self) -> None:
        """On dyno restart: load all sessions with closed_at IS NULL into self.sessions."""
```

**Invariants enforced (per session):**

- Cannot start a round if the previous round is not ended.
- Cannot start a market if the previous market is not resolved.
- Cannot trade if `session.phase != ROUND_OPEN`.
- Cannot trade more contracts than balance allows.
- Cannot trade outside `[1, 20]` quantity range.
- Cannot operate on a `session_id` not present in `self.sessions` — caller must `start_session` first or `restore_from_db` must have hydrated it.

**Tournament-specific rules:**

- Tournament computed exactly once per session, at `close_session`. Recomputing on the same session_id returns the same result (idempotent).
- Ties: if two participants tie at rank 1, 2, or 3, both receive the higher prize, and the next rank is skipped. Document this in subject instructions. Alternative tie-break (random) is supported via a config flag for project lead's choice — default is shared-prize.
- A participant with zero markets completed (e.g. disconnected before Market 1 resolved) is excluded from ranking.

**Acceptance tests:**

- Full session simulation × 3 concurrent sessions: each runs to closure independently, no state crossover.
- Tournament test: hand-crafted final balances → expected rankings and prize assignments.
- Tie test: two participants identical → shared first place, no rank 2.
- Restoration: after simulated mid-round crash with 3 concurrent sessions, calling `restore_from_db` recovers all three.

**Owned by:** Orchestrator Agent.

---

### 5.6 Server API — `server/server.py`

**Status:** Exists. Substantial extension required.

**HTTP endpoints (multi-session):**

All admin endpoints are scoped by `session_id` in the URL path. Participant endpoints derive their `session_id` from their auth cookie.

```
POST   /auth/join                                  — exchange join_token (carries session_id + slot) for cookie
POST   /admin/sessions                             — start_session (returns new session_id)
GET    /admin/sessions                             — list all active sessions
POST   /admin/sessions/{session_id}/close          — close_session (triggers tournament computation)
POST   /admin/sessions/{session_id}/markets        — start_market
POST   /admin/sessions/{session_id}/markets/{n}/resolve  — resolve_market
POST   /admin/sessions/{session_id}/rounds         — start_round
POST   /admin/sessions/{session_id}/rounds/{n}/end — end_round
GET    /admin/sessions/{session_id}/tournament     — read computed rankings
POST   /admin/sessions/{session_id}/tournament/mark_paid — record manual payment confirmation
POST   /trade                                      — execute trade (session inferred from cookie)
GET    /state                                      — current state for cookie-authenticated participant
POST   /quiz/{quiz_name}/submit                    — comprehension quiz
POST   /risk_elicitation/submit                    — Holt-Laury
POST   /debrief/submit                             — debrief
GET    /tournament/final                           — participant view of final tournament (post-close)
GET    /admin/sessions/{session_id}/export.csv     — full trade log
GET    /admin/sessions/{session_id}/export.json    — full session including signals, benchmarks, tournament
```

**Auth model:**

- Admin endpoints: HTTP Basic auth from Heroku config var (`ADMIN_USER`, `ADMIN_PASS`). Admin sees all sessions.
- Participant endpoints: session cookie set after `/auth/join` exchanges a one-time join_token. Cookie carries `{session_id, participant_id}`. Cookies are HTTP-only, secure, sameSite=Lax. **Cookie is scoped to its session** — a participant whose session has closed cannot use the cookie to access another session.
- Socket.io connections: cookie-authenticated on handshake. Participant joins rooms `session:{sid}:all` and `session:{sid}:participant:{pid}`.

**Acceptance tests:**

- 3 concurrent sessions running simultaneously: trades in Session 42 do not appear in Session 43's price stream. Sessions are fully isolated.
- All endpoints return 401/403 with appropriate auth boundaries.
- Trade endpoint rejects invalid quantities, invalid direction, closed rounds, insufficient balance, unknown participant.
- Concurrent trade requests from 16 participants within one session land atomically — no double-spends. Use `SELECT ... FOR UPDATE` on `market_roles` row when computing the trade.
- Tournament endpoint returns 404 until session is closed and computation has completed.

**Owned by:** Server Agent.

---

### 5.7 Socket.io Event Contracts

These are the wire-format contracts between server and client. Any agent changing these must update the contract registry in `/server/events.py` and notify all client agents.

**Server → Client events:**

```jsonc
// "session_started"
{ "session_id": 42, "session_label": "S2026-05-27-A" }

// "market_started" (private to each participant)
{
  "market_number": 2,
  "stage": 2,
  "scenario_description": "Will Valdoria enter armed conflict within 12 months?",
  "role_tier": "semi_informed",
  "endowment_tokens": 100.0,
  "starting_balance": 100.0,
  "current_price": 0.5,
  "max_rounds": 5
}

// "round_started" (private to each participant)
{
  "round_number": 1,
  "trading_open": true,
  "current_price": 0.5,
  "balance": 92.4,
  "yes_held": 4,
  "no_held": 0,
  "bulletin": {
    "public": "Valdoria and Norheim exchange harsh diplomatic words…",
    "analytical": null,                      // null unless semi_informed or insider
    "intelligence": null                     // null unless insider
  },
  "posterior": null,                          // null unless informed; e.g. 0.71
  "round_deadline_unix_ms": 1740655800000     // when the round will auto-close
}

// "price_update" (broadcast)
{
  "current_price": 0.537,
  "q_yes": 10.0,
  "q_no": 0.0,
  "last_trade": {
    "participant_id_hashed": "a7f...",         // hashed for privacy
    "direction": "yes",
    "quantity": 10,
    "price_before": 0.500,
    "price_after": 0.537
  }
}

// "round_ended" (broadcast)
{
  "round_number": 1,
  "closing_price": 0.537,
  "round_volume": 23
}

// "market_resolved" (private)
{
  "outcome": 1,
  "outcome_label": "YES — Conflict occurred",
  "true_probability": 0.75,
  "payout": 400.0,
  "final_balance": 492.4,
  "pnl": 392.4
}

// "state_sync" (sent on connect/reconnect — full state)
{ /* combination of market_started + round_started + portfolio */ }

// "error" (private)
{ "code": "ROUND_CLOSED", "message": "Trading is currently closed." }
```

**Client → Server events:** only `trade` (HTTP, not Socket.io). All other client → server messages are HTTP REST.

**Acceptance:** Event schemas validated via Pydantic models on the server, and via TypeScript types on the client (generate from Pydantic via `pydantic-to-typescript` or hand-write — agents must keep them in sync).

**Owned by:** Server Agent owns the contract definitions. All other agents consume.

---

### 5.8 Frontend Trading View — `client/src/views/TradingView.jsx`

**Status:** Exists as `valdoria_market.jsx`. Major adaptation required.

**Changes from scaffold:**

- Remove all local LMSR state; price comes only from server via `price_update`.
- Add **posterior panel** that displays `intelligence_assessment: P(YES) = 71%` when present in `round_started.posterior`. Make it visually distinct from the narrative — different border, different colour, prefixed clearly. Subjects must understand this is *their private assessment*, not the market price.
- Add countdown timer driven by `round_deadline_unix_ms`. Show seconds remaining. When timer hits 0, disable trade form (UI hint; authoritative close still comes from server's `round_ended`).
- Replace participant ID with the cookie-authenticated session.
- Replace inline-style design system with Tailwind (optional but recommended for consistency with new aux screens).

**Layout (top to bottom):**

1. Header: market number, stage label, round number, countdown.
2. Narrative panel: current round's `public` bulletin.
3. Analytical panel (if visible): the `analytical` bulletin string. Header text: "Analyst commentary".
4. Intelligence panel (if visible): the `intelligence` bulletin string. Header text: "Intelligence brief".
5. Posterior panel (if visible): "Your private assessment: P(YES) = 71%". Visually separated.
6. Market state: current price (large), price chart of the round so far.
7. Portfolio: balance, YES held, NO held.
8. Trade form: direction toggle, quantity input, cost preview, submit.

**Acceptance tests (client unit + Cypress E2E):**

- All panels render conditionally based on role tier — uninformed never sees analytical or posterior.
- Price chart updates within 100ms of `price_update` event.
- Submitting a trade with insufficient balance shows server error message, does not double-submit.
- Reconnecting after WebSocket drop restores state via `state_sync` within five seconds.

**Owned by:** Frontend-Trading Agent.

---

### 5.9 Frontend Auxiliary Screens — `client/src/views/aux/` (NEW)

**Five new screens** in order of subject flow:

| Screen | Purpose | Persistence |
|---|---|---|
| `ConsentScreen.jsx` | IRB-approved consent form, checkbox + name | `debrief_responses.answers.consent = {timestamp, consented: true}` initially recorded; full form on debrief side |
| `InstructionsScreen.jsx` | Multi-page walkthrough of the experiment, including the tournament prize structure (€5/€3/€2 to top-3 by total tokens at session end). Last page links to quiz. | Read-only |
| `ComprehensionQuizScreen.jsx` | 5–8 multiple-choice questions on LMSR mechanics, role semantics, payoff structure, and tournament rules. Loops until 100% correct. | `quiz_attempts` |
| `HoltLauryScreen.jsx` | 10-row binary lottery choice. Records switch point. | `risk_elicitations` |
| `DebriefScreen.jsx` | Free-text + structured questions on strategy, perceived information, satisfaction. Final screen also reveals the participant's final tournament rank and whether they won a prize. Subjects who place top-3 see prize amount and that payment will be processed manually. | `debrief_responses` |

**Routing:**

Use React Router. Flow:
`/consent` → `/instructions` → `/quiz` → `/risk` → `/lobby` → `/trade` (when admin starts session) → `/debrief` (when session closed).

Server tracks each participant's progress in `participant_sessions` table (add a `flow_step` column).

**Acceptance:**
- All screens are keyboard-navigable.
- Quiz cannot be skipped; only proceeds on 100% correct.
- Holt-Laury enforces monotonicity check (warn but don't block on non-monotone switch).
- All form data POSTed to server and persisted before navigation.

**Owned by:** Frontend-Aux Agent.

---

### 5.10 Admin Panel — `client/src/views/AdminPanel.jsx`

**Status:** Exists. Extend for 4 markets, multi-session, new aux phases, and tournament display.

**Sections:**

1. **Session list**: all sessions (active and closed). Click to drill in. "Start new session" button.
2. **Session control (per drilled session)**: scenario order, rotation matrix used, subject count, end-session button.
3. **Phase control**: which phase is each participant in (consent / instructions / quiz / risk / lobby / market-N / debrief). Override "advance all" button.
4. **Market control**: start market 1..4; for each, see scenario assigned, true_probability (admin-only), B parameter; start round; end round; resolve market.
5. **Live trading monitor**: real-time price chart per market; current trade volume; per-participant balance + holdings table.
6. **Bayesian benchmark display** (admin only, post-round): shows computed benchmark and price-path deviation at round close.
7. **Tournament display** (admin only): on demand, shows running tally of total tokens per participant across markets completed so far. After session close, shows the locked ranking and assigned prizes. "Mark paid" button per row to record manual payment confirmation.
8. **Export**: CSV (trades only) and JSON (full session including signals, benchmarks, tournament).

**Critical: subjects do not see interim tournament rankings.** Only the admin panel surfaces the running tally. Subjects see their own per-market balances and learn the final ranking only at the debrief screen (Part 5.9). This is to keep the tournament effect as a within-subject constant rather than a between-market motivator — see the Part 11 design note.

**Acceptance:**
- All admin actions atomic — clicking "start round" twice does not create two rounds.
- Multi-session: admin can switch between live sessions without page reload; the live trading monitor rebinds to the new session.
- "Emergency override" buttons: force-close a round, force-resolve a market, force-end a session. Each requires a confirm dialog with the reason logged to a `admin_actions` audit log (add to schema if not present — Orchestrator Agent's call).

**Owned by:** Admin Agent (formerly part of Frontend-Aux Agent; see updated Part 6 roster).

---

### 5.11 Analysis Pipeline — `analysis/` (NEW, Python notebooks + scripts)

**Purpose:** Convert raw session data into the outcome variables enumerated in §8 of the design doc.

**Structure:**

```
analysis/
├── load.py                   # DB → pandas DataFrames
├── benchmark_recompute.py    # Independently recomputes Bayesian benchmark from signals.
│                             #   Acts as a sanity check on server-side computation.
├── outcomes.py               # Computes:
│                             #   - price_accuracy
│                             #   - convergence_speed
│                             #   - price_path_deviation
│                             #   - insider_returns
│                             #   - return_inequality (Gini)
│                             #   - trading_volume
│                             #   - price_impact
│                             #   - information_revelation_correlation
├── plots/
│   ├── price_paths.py        # Per-market price vs benchmark plots
│   ├── return_dist.py        # Return distribution by role tier
│   └── ...
├── tests.py                  # Statistical tests across treatment markets
└── notebooks/
    ├── 01_pilot_review.ipynb
    ├── 02_main_analysis.ipynb
    └── 03_robustness.ipynb
```

**Implementation notes:**

- All metrics keyed on `(session_id, market_id, round_id)` so the pipeline can be run partial-session (e.g. after pilot before full data collection).
- The Bayesian benchmark recomputation in `benchmark_recompute.py` MUST be an independent implementation from `server/bayesian.py`. If they ever disagree, halt and debug. This catches bugs in either.

**Owned by:** Analysis Agent.

---

### 5.12 Calibration Harness — `calibration/` (NEW)

**Purpose:** Pre-session tooling to validate the B parameter, signal-draw distributions, and resolution behaviour before any human subjects run.

**Components:**

```
calibration/
├── simulate_market.py    # N synthetic traders, configurable strategies, runs full market
├── b_sweep.py            # Sweeps B ∈ [10, 20, 30, 50, 100], reports price-impact metrics
├── signal_validator.py   # Confirms drawn signal distributions match θ
├── benchmark_validator.py# Confirms server benchmark matches analysis-pipeline benchmark
└── ui_smoketest.py       # Selenium/Playwright: 10 fake browsers complete a full session
```

**Acceptance:**
- `b_sweep.py` produces a table that the project lead reviews to choose final B per stage.
- `signal_validator.py` runs 10,000 simulated rounds and confirms empirical signal frequencies match θ within tolerance.
- `ui_smoketest.py` runs to completion without errors before each real session.

**Owned by:** Calibration Agent.

---

## Part 6 — Subagent Allocation

### 6.1 Agent roster

Seven subagents. Six implement; one reviews. Boundaries are drawn to minimise cross-agent dependencies and merge conflicts.

| Agent | Owns | Reads (but does not modify) |
|---|---|---|
| **MarketEngine Agent** | `server/lmsr.py`, `server/bayesian.py`, `tests/test_lmsr.py`, `tests/test_bayesian.py` | — |
| **Scenarios Agent** | `server/scenarios.py`, `server/roles.py`, `tests/test_scenarios.py`, `tests/test_roles.py` | — |
| **Orchestrator Agent** | `server/orchestrator.py`, `server/events.py` (event contracts), `server/db_models.py`, Alembic migrations, `tests/test_orchestrator.py` | `lmsr.py`, `bayesian.py`, `scenarios.py`, `roles.py` |
| **Server Agent** | `server/server.py`, `server/auth.py`, `server/socketio_handlers.py`, integration tests | `orchestrator.py`, `events.py`, `lmsr.py`, `bayesian.py` |
| **Frontend-Trading Agent** | `client/src/views/TradingView.jsx`, `client/src/socket.js`, `client/src/api.js`, `client/src/store/` (trading store), `client/src/types/events.ts` | `server/events.py` (read for contract sync) |
| **Frontend-Aux Agent** | `client/src/views/aux/*.jsx`, `client/src/views/AdminPanel.jsx`, routing, layout shell | `server/events.py` |
| **Analysis Agent** | `analysis/**`, `calibration/**` | — (works only against exported CSVs / direct DB reads) |
| **DevOps Agent** | `Procfile`, `runtime.txt`, `requirements.txt`, `client/package.json`, Heroku config, GitHub Actions CI, `Dockerfile` (if used), `README.md` | — |
| **Review Agent** | Nothing — read-only across all of the above | All files |

That is nine roles. Practical roster: **six concurrent implementers + one synchronous reviewer** (Scenarios + MarketEngine can be the same agent; Analysis + Calibration can be the same agent).

### 6.2 Review Agent — formal role specification

**Purpose.** The Review Agent is the only agent that can approve a merge to `main`. It does not write production code. Its existence prevents the six implementing agents from approving each other and drifting from spec.

**Workflow.** For every pull request raised by an implementing agent:

1. **Spec conformance check.** Read the relevant module specification in Part 5 of this bible. Verify the PR's diff matches the spec's interface, persistence, and acceptance criteria. Specifically check:
   - Public function signatures match the spec verbatim
   - Event contract changes (if any) propagated to `server/events.py` AND `client/src/types/events.ts`
   - Tests exist for every acceptance criterion listed in the spec
   - No undeclared file modifications outside the agent's ownership scope in 6.1
2. **CI gate.** All CI checks must be green: unit tests, integration tests, smoke test, lint, type checks (mypy on Python, tsc on TypeScript).
3. **Cross-cutting impact check.** If the PR touches one of the cross-cutting files (`events.py`, `db_models.py`, Alembic migrations, `socket.js`), explicitly verify that consumers in other agents' code are not broken. Run the integration test suite locally if CI did not.
4. **Open-decision check.** Reject any PR that introduces a new design decision not recorded in Part 11. Force escalation to project lead instead.
5. **Approve or request changes.** Approval is binary; partial approval is not allowed. Request-changes comments must cite the specific bible section being violated.

**Boundaries.**

- The Review Agent does NOT write code, even to "just fix this small thing." All fixes go back to the originating implementer.
- The Review Agent does NOT make design decisions. Any ambiguity escalates to project lead (you).
- The Review Agent SHOULD push back on scope creep — if an implementer's PR includes work not specified in Part 5, request that the extra work be split into a separate PR and surfaced to project lead for ratification.

**Rejection-reason taxonomy** (use these labels in PR comments):

- `SPEC_MISMATCH` — interface or behaviour diverges from Part 5 spec
- `CONTRACT_DESYNC` — event contract changed in one place not the other
- `MISSING_TEST` — acceptance criterion not covered
- `OUT_OF_SCOPE` — PR includes work not in the agent's ownership
- `UNDECLARED_DECISION` — introduces a design choice not in Part 11
- `CI_FAILURE` — tests, lint, or types failing
- `BIBLE_AMENDMENT_NEEDED` — implementer found a genuine spec gap; reviewer approves PR but requires Part 11 update first

**Escalation triggers.** The Review Agent escalates to project lead when:

- An implementer disputes a `SPEC_MISMATCH` ruling
- Three or more `UNDECLARED_DECISION` PRs land in any 48-hour period (signals the bible is incomplete)
- A `BIBLE_AMENDMENT_NEEDED` ruling requires a substantive design call
- Two implementing agents disagree about which one owns a file

**What the Review Agent is NOT.** It is not a manager. It is not a tie-breaker between implementers (project lead is). It is not a second coding agent in disguise. Its job is narrow: enforce the bible, gate merges, escalate uncertainty.

### 6.3 Conflict-avoidance protocol

- Each implementing agent works on a long-lived branch named `agent/<name>`.
- The `main` branch is protected. Merges to main require:
  - All tests passing in CI
  - Contract sync verified (no event schema mismatch between server and client types)
  - **Approval from Review Agent** (or escalation to project lead)
- File-level ownership is exclusive. If two agents need to touch the same file, the bible explicitly grants ownership to one; the other opens a request-for-change comment.
- `server/events.py` and `client/src/types/events.ts` are the only files multiple agents read; the Server Agent owns the source of truth, others mirror.
- The Review Agent has read access to every branch but writes to none.

### 6.4 Sequential dependencies that cannot be parallelised

Despite the parallel structure, three hard sequences exist:

1. **Schema before everything.** The Orchestrator Agent's `db_models.py` and the first Alembic migration must land before any other agent can write code that touches persistence. Estimated: half a day of focused work, plus Review Agent gate.
2. **Event contracts before server↔client coupling.** The Server Agent must publish `events.py` before Frontend agents can write socket handlers. Estimated: half a day after schema lands, plus Review Agent gate.
3. **MarketEngine before Orchestrator.** Orchestrator imports LMSR and Bayesian services. The interfaces in §5.1 and §5.2 are pre-frozen in this document; MarketEngine Agent implements behind a stable interface, so Orchestrator can begin against mocks immediately and swap to real implementations when ready.

Everything else parallelises.

---

## Part 7 — Build Sequence

The Review Agent gates every merge to `main`. Where a phase below says "exit gate," that gate includes Review Agent approval, not just CI green.

### Phase 0 — Project bootstrap *(½ day, single agent: DevOps; Review Agent active)*

- Initialise Git repo with `main` + `develop` branches, branch protection rules, GitHub Actions workflow.
- Set up Review Agent's read access to all branches.
- Create directory structure per scaffold + new modules per Part 5.
- Set up Python virtualenv with FastAPI + python-socketio + SQLAlchemy + Alembic + pytest; freeze `requirements.txt`.
- Set up Vite React app with TailwindCSS, React Router, React Hook Form, socket.io-client; freeze `package.json`.
- Create empty Heroku app, attach Heroku Postgres mini, set config vars (`DATABASE_URL` auto-set, plus `ADMIN_USER`, `ADMIN_PASS`, `SESSION_SECRET`).
- Write a minimal "hello world" Heroku-deploy that exercises FastAPI + Postgres + a single Socket.io connection. Confirm WebSocket handshake works on the chosen dyno tier **[VERIFY]**.

**Exit gate:** A blank-but-deployed app responds at the Heroku URL. Review Agent confirms project structure matches Part 5 file map.

### Phase 1 — Foundations *(parallel, 2–3 days)*

| Track | Agent | Output |
|---|---|---|
| 1a | Orchestrator Agent (acting as data-layer lead first) | `db_models.py` including `tournament_rankings`, initial Alembic migration, `tests/test_models.py` |
| 1b | MarketEngine Agent | Extended `lmsr.py` + tests; full `bayesian.py` + tests (including Stage 1 signal-suppression path) |
| 1c | Scenarios Agent | Revised `scenarios.py` (narrative-only, no embedded numbers), extended `roles.py` (4-market, whales, parameterised by subject count 8–20), tests |
| 1d | DevOps Agent | CI pipeline runs all of the above on every push; Review Agent integrated into PR workflow |

**Exit gate:** All four tracks have passing tests and Review Agent approval. No integration yet; everything in isolation works.

### Phase 2 — Backend integration *(sequential, 2 days)*

| Step | Agent | Output |
|---|---|---|
| 2a | Orchestrator Agent | `orchestrator.py` integrating LMSR + Bayesian + scenarios + roles, with the multi-session state model, tournament computation, and `restore_from_db()` |
| 2b | Server Agent | `events.py` contracts published; `server.py` with session-scoped endpoints; Socket.io handlers with session-room partitioning; auth |
| 2c | DevOps Agent | Integration test: 3 simulated concurrent sessions of 16 participants each running end-to-end via HTTP + Socket.io clients in test |

**Exit gate:** Backend smoke test passes. Review Agent confirms event contracts in `events.py` match consumer expectations in any frontend draft.

### Phase 3 — Frontend *(parallel with end of Phase 2, 3 days)*

| Track | Agent | Output |
|---|---|---|
| 3a | Frontend-Trading Agent | `TradingView.jsx`, socket handlers, posterior panel, countdown, price chart |
| 3b | Frontend-Aux Agent | Consent / instructions / quiz / Holt-Laury / debrief screens (debrief reveals tournament rank), routing |
| 3c | Frontend-Aux Agent | `AdminPanel.jsx` extension with session selector and tournament display |

**Exit gate:** Manual full-flow walkthrough by project lead with one simulated subject. All screens render. All data persists. Review Agent confirms no `localStorage`/`sessionStorage` usage (per Anthropic artifact constraints) and no IP/branded content in scenarios.

### Phase 4 — Calibration *(1–2 days, Calibration/Analysis Agent)*

- Run `b_sweep.py` with synthetic traders, choose B per stage.
- Run `signal_validator.py`, confirm distributions.
- Run `ui_smoketest.py` with 16 headless browsers across 2 concurrent sessions, confirm no crashes under concurrent load.
- Project lead reviews and ratifies B values; commit them to `roles.py`.

**Exit gate:** Calibration report PDF accepted by project lead. Review Agent confirms the B value committed to `roles.py` matches the report's recommendation.

### Phase 5 — Pilot session *(real subjects, 1 session)*

- Recruit 16 subjects (pilot rate, or whatever you can secure).
- Run full session live on production Heroku.
- Project lead observes; admin panel records.
- Post-session: pull data, run `01_pilot_review.ipynb`, identify any UX or measurement issues.
- Fix any P0 issues; defer P1+ to a fix-iteration sprint before main sessions.

**Exit gate:** Pilot data is clean; benchmark recomputation in analysis matches server-side computation; tournament computed correctly; no subject reported confusion the protocol cannot explain.

### Phase 6 — Main data collection

Out of scope for the bible. Standard data-collection logistics. Multiple concurrent sessions can run on the same Heroku app.

### Phase 7 — Analysis pipeline maturation *(parallel with Phase 6)*

- Analysis Agent develops `02_main_analysis.ipynb` against accumulating session data.
- All eight outcome variables computed; hypothesis tests applied.
- Tournament-effect robustness check: regress price-path-deviation on cumulative interim balance position (post-hoc) to confirm tournament-induced risk-seeking is not driving treatment effects.

---

## Part 8 — Acceptance Criteria and Testing

### 8.1 Per-module unit-test coverage targets

| Module | Coverage |
|---|---|
| `lmsr.py` | 100% |
| `bayesian.py` | 100% |
| `orchestrator.py` | ≥ 90% |
| `scenarios.py`, `roles.py` | 100% (small modules, deterministic) |
| `server.py` | ≥ 80% via integration tests |
| Frontend trading view | ≥ 70% (component + interaction tests) |
| Frontend aux | ≥ 60% |
| Analysis pipeline | ≥ 80% on pure functions; notebooks ad hoc |

### 8.2 Integration test scenarios (must pass before any pilot)

1. **Happy path session.** Start → 4 markets × 5 rounds × resolution → close. All snapshots, trades, benchmarks recorded.
2. **Mid-round dyno restart.** Kill the server during a trading window. Restart. All clients reconnect via `state_sync`. Trading resumes within five seconds. No double-counting of trades.
3. **Concurrent trades.** Fire 16 trade requests within a single 50ms window. All execute serially in the database. Final `q_yes`, `q_no` match the sum of executed deltas. No race-condition double-spends.
4. **Insufficient balance.** Participant attempts trade exceeding balance. Server rejects with `INSUFFICIENT_FUNDS`. State unchanged.
5. **Closed round.** Trade submitted after round_ended emitted. Rejected with `ROUND_CLOSED`.
6. **Role gating.** Uninformed participant receives `posterior: null`; semi-informed receives a number; insider receives a number with higher absolute likelihood-ratio shift.
7. **Stage 1 override.** Even if rotation matrix assigns insider to a participant in Market 1, the bulletin contains only `public` and posterior is `null`.
8. **Benchmark sanity.** Server-computed Bayesian benchmark equals the analysis-pipeline recomputation for 100 simulated rounds.

### 8.3 Pilot session pass criteria

- All 10 subjects complete consent → quiz → risk → 4 markets → debrief without manual intervention.
- No subject's view freezes for > five seconds during a trading window.
- Final database export contains, per market: 5 rounds, ≥ 0 trades per participant (zero is OK), one snapshot per round, one resolution.
- Bayesian benchmark recomputation matches server-side computation exactly.
- Stage 1 closing price within ±0.05 of 0.50 in the pilot session, OR a documented hypothesis for why not (e.g. one subject traded irrationally — record as data, do not "fix").

---

## Part 9 — Deployment

### 9.1 Heroku configuration

```
# Procfile
web: uvicorn server.server:combined_app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 75
release: alembic upgrade head
```

Notes:

- **Workers = 1** (not the typical 4). Multi-worker breaks the in-memory `state` cache because workers don't share memory. Either accept single-worker (fine for a 16-participant session) or move *all* state to Postgres and run multi-worker (more engineering for no scale benefit at this size). Recommendation: stay single-worker.
- **Timeout-keep-alive = 75s.** Heroku's router closes idle connections after 55 seconds **[VERIFY current value]**; setting uvicorn's keep-alive longer ensures the WebSocket heartbeat (Socket.io default ping every 25s) keeps the connection live.

### 9.2 Config vars

```
DATABASE_URL              # auto-set by Heroku Postgres
SESSION_SECRET            # 32-byte random; generated once and never rotated mid-session
ADMIN_USER, ADMIN_PASS    # HTTP basic auth for /admin/*
ALLOWED_ORIGINS           # comma-separated list of frontend origins
PYTHON_VERSION            # 3.11.x
LOG_LEVEL                 # INFO (production) / DEBUG (dev)
SENTRY_DSN                # optional; only set if Sentry is enabled
```

### 9.3 Dyno sizing recommendation

The expected production load is **up to 5 concurrent sessions × 16 subjects = ~80 simultaneous WebSocket connections, plus admin observers.**

For this load: **basic dyno (formerly hobby)** should be sufficient based on the workload (low memory, modest CPU). **[VERIFY current Heroku dyno tier names and pricing.]** Postgres mini is sufficient up to the row-count ceiling of that tier.

For piloting (1 session at a time), eco dyno saves cost. For production data-collection with multiple concurrent sessions, basic or higher to avoid cold-start issues and to ensure WebSocket connection limits do not bite.

If you anticipate routinely running > 5 concurrent sessions, the architecture needs the changes flagged in §2.4: move state out of in-process memory to Redis, run multiple workers. This is a follow-up project, not v1.1.

### 9.4 oTree fallback (if 9.1–9.3 prove infeasible)

If you choose oTree instead of extending Valdoria:

- Use oTree 5.x with `LiveMethods` for the trading rounds.
- Replace `valdoria_market.jsx` with an oTree `Page` whose `live_method` handler implements LMSR.
- Persist trades in a custom Django model attached to the `Group`.
- Use oTree's built-in Bot system for synthetic-trader testing.
- **Load test before committing:** simulate 16 bots posting trades every 500ms for 90 seconds across a market. If p99 latency on the live update stays < 250ms and there are no dropped messages, oTree is viable. **[VERIFY this empirically — I cannot from inside this drafting context.]**

If load testing fails, return to the FastAPI/Socket.io path.

---

## Part 10 — The LLM Narrator Question

### 10.1 Why not in production

Already covered in Part 1.3 — the short version:

- Within-subject design demands narrative reproducibility.
- LLM stochasticity creates an unmeasured treatment-confound.
- Existing narratives in `scenarios.py` are sufficient and locked.

### 10.2 Sanctioned offline uses

The following uses of LLMs are explicitly permitted in the development workflow:

1. **Variant scenario generation.** Before locking scenarios for production, generate 5–10 candidate variants per scenario via an LLM, have the project lead review and choose, then freeze. Code the chosen variant into `scenarios.py`. After freeze, no LLM touches that text.
2. **Ambiguity testing.** Pass existing narrative to an LLM with prompts like "rank these bulletins by how strongly they suggest YES" and see whether the answer pattern matches the intended scenario direction. If a "p = 0.25" scenario bulletin scores high-YES, the language is leaking.
3. **Synthetic transcript generation for analysis pipeline development.** Useful before any real data exists.
4. **Comprehension quiz item generation.** Have the LLM propose distractor options for the comprehension quiz, then project lead curates.

### 10.3 Forbidden uses

- Live regeneration of scenario text during a session.
- Generating per-subject personalised narratives.
- Using an LLM to generate the "intelligence assessment" probabilities. These are computed by `bayesian.py` deterministically.

---

## Part 11 — Ratified Decisions and Outstanding Risks

### 11.1 Ratified decisions (v1.1)

All ten Part 11 decisions ratified by project lead on 2026-05-27.

| # | Decision | Ratified value | Implementation site |
|---|---|---|---|
| 1 | Stage 3b robustness variant | **No** — ship as designed | Roles agent |
| 2 | Stage 1 baseline signal handling | **Signals drawn at θ=0.65 for all participants, persisted with `delivered=False`, not delivered to clients** | Bayesian agent + Orchestrator |
| 3 | Subjects per session | **Default 16, configurable 8–20; multiple concurrent sessions supported** | Roles agent, Orchestrator, Server, Admin Panel |
| 4 | Number of rotation matrices | **3** (parameterised by subject count) | Roles agent |
| 5 | Payment infrastructure | **Tournament structure: end-of-session top-3 by total tokens across all 4 markets win €5 / €3 / €2 respectively. Payment vendor deferred — bible specifies schema, computation, and admin "mark paid" workflow; integration with a payment processor is OUT OF SCOPE for v1.1. Project lead pays manually post-session.** | Orchestrator (computation), Admin Panel (display, mark-paid), Frontend-Aux (debrief reveal) |
| 6 | Risk elicitation | **Holt-Laury 10-row** | Aux agent |
| 7 | Pre-registration | **No** before pilot | Project lead only |
| 8 | B parameter per stage | **Same across all stages** within a session | Calibration agent, Roles agent |
| 9 | Max trade size per submission | **20 contracts** | LMSR + Server agent |
| 10 | Resolution outcome display | **Outcome shown publicly; payouts shown privately** | Server + Frontend-Trading |

### 11.2 Outstanding risks recorded against ratified decisions

These are not blockers — they are research-risk notes the analysis pipeline and write-up should acknowledge.

**Decision 5 (tournament payment) introduces:**

- **Reduced incentive salience per market.** Total prize pool is €10/session against trading stakes in tokens, with no token-to-money conversion outside the top-3 prize. Subjects ranked 4+ have zero marginal incentive from any single trade once they realise they cannot catch the top 3. Mantovani & Filippin (2026) and §10.9 of the design doc are both relevant references for write-up.
- **Tournament-induced risk-seeking.** Subjects falling behind have weak incentive to trade conservatively; subjects in the lead have weak incentive to trade at all. Both distort price discovery away from a risk-neutral benchmark. The Holt-Laury risk-aversion covariate cannot fully net this out because the distortion is endogenous to interim ranking rather than baseline preference.
- **Mitigation: subjects do not see interim rankings.** They see only their own per-market balances and learn the final ranking at the debrief screen. This pushes the tournament effect toward being a within-subject constant rather than a between-market motivator. It does not eliminate it.
- **Mitigation: analysis robustness check.** Phase 7 includes a regression of price-path-deviation on cumulative interim balance position. If the coefficient is significant, the tournament effect is contaminating treatment effects and the data should be treated as exploratory.

**Decision 7 (no pre-registration) introduces:**

- All inference is post-hoc. The eight outcome variables in §8 of the design doc remain the planned primary measures, but they are not bound by a public commitment. If the project's audience cares about pre-registration (most experimental-economics journals do), consider registering after pilot data is collected but before main sessions begin.

**Decision 2 (Stage 1 suppressed signals) introduces:**

- A subtle deviation from the design doc as originally written. v1.1 records this as an explicit project-lead decision rather than a silent change. The reason for the deviation (analytical benchmark parity across stages) is documented; the experimental-design effect (none, since subjects don't see the signals) is recorded.

### 11.3 Decisions that remain ambiguous and need project lead attention

- **Tournament tie-breaking rule.** Default: shared prize at tied rank, next rank skipped. Alternative: random tie-break recorded with a logged seed. Orchestrator implements the default; the alternative is gated by a config flag. **Confirm preference or accept default.**
- **Whether to display tournament prize structure in the consent screen as part of the inducement disclosure.** IRB practice varies. Default in v1.1: yes, disclosed in consent and reiterated in instructions. **Confirm preference.**
- **Payment processing mechanism for the €5 / €3 / €2 prizes.** Bible defers this to manual processing. If you want it automated (PayPal API, Wise, Stripe Connect), a follow-up spec is needed.

---

## Part 12 — Appendices

### Appendix A — Bayesian benchmark math, worked example

Prior: P(YES) = 0.5. Insider precision θ_I = 0.85. Semi precision θ_S = 0.65.

Suppose in round 1:
- Insider 1: signal H
- Insider 2: signal L
- Semi 1: signal H
- Semi 2: signal H
- Semi 3: signal L
- Semi 4: signal H

Likelihood ratios L(s, θ) = P(s | YES) / P(s | NO):
- L(H, 0.85) = 0.85 / 0.15 = 5.667
- L(L, 0.85) = 0.15 / 0.85 = 0.176
- L(H, 0.65) = 0.65 / 0.35 = 1.857
- L(L, 0.65) = 0.35 / 0.65 = 0.538

Joint likelihood ratio across all signals:
LR = 5.667 × 0.176 × 1.857 × 1.857 × 0.538 × 1.857 = 3.469 (approximately)

Posterior odds = prior odds × LR = (0.5 / 0.5) × 3.469 = 3.469
Posterior probability = 3.469 / (1 + 3.469) ≈ 0.776

So the rational round-1 benchmark price is ≈ 0.776. Implement and unit-test this exact example.

### Appendix B — Heroku-specific gotchas

- Dynos restart at least once every 24 hours. Your session must survive this (covered by `restore_from_db`).
- The free Postgres tier has connection limits and row limits **[VERIFY current Heroku Postgres mini limits — they change]**. Confirm before scheduling sessions with > 10 subjects.
- File-system writes do not persist across restarts. Anything written to disk is gone. The `valdoria.db` SQLite file from the scaffold is gone on restart; this is the second reason (after concurrency) to move to Postgres.
- Time zones: Heroku runs UTC. Display in local time on the admin UI; store UTC in the database.

### Appendix C — Holt-Laury 10-row table

| Row | Option A (£) | Option B (£) | P(high) |
|---|---|---|---|
| 1 | £2.00 safe / £1.60 unsafe | £3.85 safe / £0.10 unsafe | 0.10 |
| 2 | same | same | 0.20 |
| 3 | same | same | 0.30 |
| 4 | same | same | 0.40 |
| 5 | same | same | 0.50 |
| 6 | same | same | 0.60 |
| 7 | same | same | 0.70 |
| 8 | same | same | 0.80 |
| 9 | same | same | 0.90 |
| 10 | same | same | 1.00 |

Switch-point row is recorded as the risk-aversion proxy. Holt & Laury (2002) is the standard reference; **I do not have a verified URL** for the canonical version — the Aux agent should obtain the canonical table from the published source before implementation rather than typing from this rough sketch, which may not match the original exactly.

### Appendix D — File-by-file ownership map

```
/server/
  lmsr.py                  MarketEngine Agent
  bayesian.py              MarketEngine Agent
  scenarios.py             Scenarios Agent
  roles.py                 Scenarios Agent
  db_models.py             Orchestrator Agent
  orchestrator.py          Orchestrator Agent
  events.py                Server Agent (source of truth)
  server.py                Server Agent
  auth.py                  Server Agent
  socketio_handlers.py     Server Agent
  alembic/                 Orchestrator Agent

/client/src/
  views/TradingView.jsx        Frontend-Trading Agent
  views/AdminPanel.jsx         Frontend-Aux Agent
  views/aux/*.jsx              Frontend-Aux Agent
  store/                       Frontend-Trading Agent (trading store), Frontend-Aux (aux store)
  socket.js                    Frontend-Trading Agent
  api.js                       Frontend-Trading + Frontend-Aux (split by endpoint)
  types/events.ts              Server Agent publishes; frontends consume
  routing.tsx                  Frontend-Aux Agent
  App.jsx                      Frontend-Aux Agent (shell)

/analysis/                     Analysis Agent
/calibration/                  Analysis Agent

/tests/                        Each agent owns tests for their modules

Procfile, runtime.txt,
requirements.txt,
package.json,
.github/                       DevOps Agent
README.md                      DevOps Agent
```

---

## Part 13 — Closing Notes for the Project Lead

This bible is dense by design. v1.1 has resolved the ten Part 11 decisions and formalised the Review Agent. Two items still require your attention (see Part 11.3) and three architectural risks are recorded against the ratified payment structure (Part 11.2).

If you want a shorter version for distribution to subagents directly, the natural cleavage points are:

- **Common preamble for all agents:** Parts 0, 1, 2, 6 (their row only), 11.
- **Per-agent instruction packet:** the relevant module specs from Part 5 + the build-sequence phases that involve them.
- **Review Agent packet:** Parts 0, 1, 2, 5 (all), 6 (full), 7 (all gates), 11.

I recommend you spend an hour before kicking off agents to:

1. Read Part 11.3 and confirm the three remaining ambiguities (tie-break rule, consent disclosure of prizes, payment processing path).
2. Walk through Part 6 with your team — particularly the Review Agent role — and confirm the approval workflow.
3. Decide whether you (project lead) will act as the Review Agent personally, or delegate it to a separate Claude Code/Cursor session whose system prompt is the Review Agent specification in 6.2.

**My recommendation: delegate Review Agent to a dedicated agent session, not yourself.** Reasoning:

- Volume. Six implementing agents generate PRs at a pace that will absorb 1–2 hours/day of your time during Phase 1–3 if you're the reviewer. That time is better spent on the open decisions and on observing pilots.
- Consistency. A dedicated session with the Part 6.2 specification as its system prompt is more consistent than a human pulled in and out of context.
- Risk. Your job is to spot the things the bible doesn't cover. A Review Agent's job is to enforce the bible. Mixing them is what produces spec drift.

You remain the escalation target for any `BIBLE_AMENDMENT_NEEDED` or `UNDECLARED_DECISION` PR.

If you'd like, I can produce: (a) the per-agent instruction packets ready to paste into individual Claude Code/Cursor sessions; (b) a tighter executive summary for stakeholders; (c) a calibration-only sub-document; (d) the Review Agent's system prompt as a standalone document; (e) the consent form draft including prize disclosure.

Tell me which (if any), and I will produce it. If anything in this v1.1 document conflicts with your intent — I want to hear that before agents start writing code, not after.

*— End of Bible v1.1*
