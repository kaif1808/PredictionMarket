Valdoria Synthetic Observation ABM — Full Experiment Replication

 Context

 Analysis/calibration work currently depends on live human sessions or the thin toy loop in
 calibration/simulate_market.py. We want an offline agent-based simulator that fully
 replicates the online human experiment to produce comparable datasets for analysis
 development.

 The key architectural decision (revised after review): rather than reimplement market logic
 in a parallel loop, the ABM drives the real server/orchestrator.py Orchestrator with
 software agents standing in for human participants. It calls the exact same lifecycle methods
 the live socket/HTTP layer calls, writes the exact same DB rows, then exports via the existing
 analysis/export_session_metrics.py. Datasets are comparable by construction because they
 flow through identical code paths.

 Database: SQLite, no PostgreSQL, no setup

 Confirmed from tests/conftest.py + tests/test_full_session_flow.py: the orchestrator is
 already driven against SQLite via Base.metadata.create_all() — no alembic, no Postgres,
 no server. SQLite is stdlib (in-memory or a throwaway file). The ABM uses the same approach:
 ephemeral SQLite is just transport; CSVs are the deliverable. The user never installs or
 runs a database.

 Decisions locked with user

 - Full replication via the real Orchestrator (not a reimplemented in-memory loop).
 - SQLite (ephemeral file/in-memory), export to CSV. No Postgres.
 - 2 role tiers (uninformed | informed, θ=0.85) — matches current server/roles.py.
 - 5 rounds per market (DB constraint round_number BETWEEN 1 AND 5; full-flow test loops 1..5).
 - risk_aversion and LMSR b are the primary tunable/sweepable knobs; other behavioral
 params (bias, stubbornness, expertise, market_imitation, budget_variance) are profile-defined.
 - Keep simulate_market.py + b_sweep.py untouched; build new calibration/abm/ package.

 How the real engine is driven (verified facts)

 - Orchestrator(db_session_factory, tournament_tie_break_mode="shared_prize", lmsr_b_parameter=18.0).
 - Lifecycle (from tests/test_full_session_flow.py):
 start_session(label, rotation_id, subject_count, treated_count=3, lmsr_b_parameter=36.0, show_tournament_payout_screen=True)
 -> session_id;
 start_market(session_id, market_number, is_practice=False) -> Market;
 start_round(session_id, round_number) -> Round;
 record_trade(session_id, participant_id, TradeRequest) -> TradeResult;
 end_round(session_id) -> Round; resolve_market(session_id) -> MarketResolution;
 close_session(session_id) -> list[TournamentRanking].
 - start_session auto-creates participants P01..PNN + ParticipantSession rows. No join
 tokens needed for headless driving — pass "P01" etc. straight to record_trade.
 - start_market writes Market + one MarketRole per participant (role/endowment from
 roles.get_assignment). start_round draws + persists real Signal rows via
 bayesian.draw_for_round (delivered flag per stage/role). end_round writes closing_price
   - bayesian_benchmark. resolve_market draws outcome (sha256(f"{sid}:{mid}:resolve")),
 writes MarketResolution + final_balance per role. close_session writes
 TournamentRanking.
 - Orchestrator emits ZERO socket.io events — fully driveable headless.
 - TradeRequest (server/events.py): side: "buy"|"sell"="buy", direction: "yes"|"no",
 quantity: int Field(ge=1, le=20) → agents must split larger desired size into ≤20 chunks.
 - Agents read their own signal back from DB after start_round:
 select(Signal).where(Signal.round_id==rid, Signal.participant_id==pid); use
 signal_value/theta/posterior only when signal.delivered is True.
 - Practice market (market_number=0, PRACTICE_MARKET_NUMBER) optional; closed via
 close_practice_market. Include for fidelity (live sessions run it), but trades there are
 excluded from tournament.

 File Layout (all new)

 calibration/abm/
   __init__.py
   profiles.py        # BehavioralProfile dataclass + presets + mix parser
   agents.py          # Agent belief state + decide() -> list[TradeRequest] (pure given inputs)
   runner.py          # builds SQLite DB, drives Orchestrator end-to-end with agents
   export.py          # thin wrapper: run analysis/export_session_metrics for each session
   sim_metrics.py     # power_prediction-style cross-session metrics (wraps analysis/)
   config.py          # SimConfig dataclass + YAML/JSON load + profile assignment
   cli.py             # argparse entrypoint

 Import pattern: ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)).
 DB wiring: point server.db at an ephemeral SQLite URL (temp file, or :memory: with a
 single shared connection) before constructing the Orchestrator, then reuse
 server.db.SessionLocal so the existing exporter/analysis.load.load_session read the same DB.

 1. Behavioral profiles — profiles.py

 @dataclass(frozen=True)
 class BehavioralProfile:
     name: str
     risk_aversion: float      # [0,1] fraction of affordable size NOT used   (TUNABLE knob)
     bias: float               # [-0.3,0.3] additive nudge to initial belief
     stubbornness: float       # [0,1] damping of Bayesian updates
     expertise: float          # [0,1] signal-interpretation fidelity (1=perfect)
     market_imitation: float   # [0,1] pull of belief toward market price
     budget_variance: float    # [0,1] per-agent jitter on trade size
 Presets: rational, noise, herder, stubborn, overreact.
 parse_mix("rational:5,herder:2,noise:2") → per-participant profile assignment (deterministic).

 2. Agents — agents.py

 Agent holds belief (carried across rounds within a market) and reads live state each round
 (its delivered Signal, current MarketRole balance/holdings, market price). Per-(agent,round)
 RNG seeded sha256(f"{sid}:{mid}:{rid}:{pid}:{profile.name}")[:16] for order-independence.

 Belief init (per market): clamp(0.5 + bias, 0.01, 0.99).
 Belief update (per round) — only if a delivered signal exists:
 theta_eff = clamp(0.5 + (theta-0.5)*expertise, 0.51, 0.99)
 if rng.random() > expertise: s = flip(s)                       # misread
 raw_post = bayesian.update_posterior(prior=belief, signal=s, theta=theta_eff)
 post     = belief + (1-stubbornness)*(raw_post - belief)
 belief   = clamp(post + market_imitation*(p - post), 0.01, 0.99)   # p = lmsr.price
 No delivered signal → only the imitation pull toward p applies.

 Decision decide(...) -> list[TradeRequest] (respects engine constraints):
 p = lmsr.price(q_yes, q_no, b)
 direction = "yes" if belief > p else "no"
 edge = abs(belief - p)
 if edge < 0.02: return []                                       # no-trade band
 affordable = lmsr.max_purchasable(q_yes, q_no, balance, direction, b)
 size_frac  = (1 - risk_aversion) * min(1.0, edge/0.5)
 jitter     = 1.0 + budget_variance*(rng.random()*2 - 1)
 target_qty = clamp(int(floor(affordable*size_frac*jitter)), 0, affordable)
 # split into TradeRequest chunks of <=20 (engine cap); recompute price/affordability
 # between chunks is unnecessary since record_trade re-validates and we stay <= affordable
 return [TradeRequest(direction=direction, quantity=q) for q in chunks_of_20(target_qty)]
 v1 is buys-only (sufficient for all metrics; matches engine no-short-sell guard). Each chunk
 goes through record_trade, which re-validates funds/short-sell — agents stay within limits so
 no INSUFFICIENT_FUNDS/SHORT_SELL errors arise; defensive try/except logs+skips if they do.

 3. Runner — runner.py

 def run_session(orch, db_factory, config, profile_assignments) -> int   # returns session_id
 Drives the real Orchestrator, mirroring tests/test_full_session_flow.py:
 sid = orch.start_session(label, rotation_id, subject_count, treated_count, lmsr_b_parameter=b)
 # optional practice market:
 if config.include_practice:
     orch.start_market(sid, 0, is_practice=True); orch.start_round(sid, 1)
     <agents trade>; orch.end_round(sid); orch.close_practice_market(sid)
 for market_number in 1..4:
     orch.start_market(sid, market_number)
     init each agent.belief for this market
     for round_number in 1..5:
         round_row = orch.start_round(sid, round_number)     # signals persisted here
         with db_factory() as db:
             load each agent's delivered Signal + MarketRole(balance,yes_held,no_held) + Market(q_yes,q_no)
         for pid in sorted(participants):                     # deterministic order
             update agent belief; trades = agent.decide(...)
             for tr in trades: orch.record_trade(sid, pid, tr)
         orch.end_round(sid)
     orch.resolve_market(sid)
 orch.close_session(sid)
 Each call re-reads fresh state from DB so agents react to real prices/signals the engine
 produced. num_sessions>1 varies rotation_id/session label and reuses one DB (distinct
 session_ids), or one DB per session.

 4. Export — export.py

 Reuse the existing exporter directly: for each generated session_id, invoke
 analysis/export_session_metrics.py (its load_session(session_id) reads the same SQLite the
 orchestrator wrote). Produces the full existing CSV suite
 (session_<id>_price_accuracy.csv, _treatment_panel.csv, _benchmark_recompute.csv, etc.)
 plus the raw frames. No new export schema invented — comparability guaranteed.

 5. Cross-session sim metrics — sim_metrics.py

 simulation_report(session_ids) -> dict, wrapping analysis/outcomes.py + analysis/metrics.py:
 price MSE vs truth (price_accuracy), MSE vs benchmark (price_path_deviation), convergence
 lag (convergence_speed), price-path variance (groupby var of closing_price), volume
 (trading_volume), treatment effect (informed_returns by role_tier), info revelation
 (information_revelation_correlation). Aggregates across sessions for parameter sweeps
 (risk_aversion × b). CLI can write these to the output dir.

 6. CLI / config — config.py, cli.py

 SimConfig: rotation_id=1, subject_count=9, treated_count=3, b=18.0, risk_aversion=None (override profile), seed=42,
 profile_mix="rational:5,herder:2,noise:2", num_sessions=1, include_practice=True, outdir="calibration/abm/output",
 db_path=":memory:".
 Flags primary (repo argparse convention), optional --config YAML/JSON overridden by flags:
 --rotation-id --subject-count --treated-count --b --risk-aversion --seed --profile-mix --num-sessions --no-practice --outdir
 --db-path --emit-metrics.
 --b and --risk-aversion are the headline sweep knobs (can accept comma lists for sweeps in
 a follow-up). Validate 2 <= treated_count <= subject_count (matches roles.get_assignment).

 7. Tests (new under tests/)

 - tests/test_abm_agents.py — deterministic agent rules in isolation: bias+clamp on init;
 stubbornness=1→belief unchanged; market_imitation=1→belief==price; expertise=1 never
 misreads / expertise=0 flips deterministically; decide empty in no-trade band, correct
 side, never exceeds max_purchasable, splits >20 into ≤20 chunks; same seed→identical.
 - tests/test_abm_runner.py — run a full headless session via the real Orchestrator on SQLite;
 assert real rows written: 4 markets, 20 rounds, Signal rows present (delivered counts match
 stage rules), Trade rows respect quantity≤20 + funds, MarketResolution + final_balance set,
 TournamentRanking computed. (Mirrors test_full_session_flow shape but agent-driven.)
 - tests/test_abm_export_pipeline.py — after a session, run export_session_metrics /
 load_session + every outcomes.* without error; assert benchmark_recompute.abs_diff≈0
 and a comparable CSV suite is produced (proves dataset parity with live exports).
 - tests/test_abm_golden.py — fixed seed/rotation/subject/treated/b/profile-mix: assert exact
 per-market truths+outcomes (orchestrator seed formula), per-market final closing_price
 (~6dp), total trade count, per-tier mean return, total volume>0. Locks determinism.

 Risks

 - SQLite engine wiring: server.db must point at the ABM's SQLite before Orchestrator
 construction and the exporter must read the same DB. Handle via DATABASE_URL/server.db
 reuse; in-memory needs a single shared connection or use a temp file (simpler). Covered by
 export-pipeline test.
 - quantity≤20 cap: large positions need multiple trades; chunking handled in decide,
 asserted in agent test.
 - Empty-trade rounds (all agents in no-trade band) → flat price; golden test asserts volume>0.
 - stage-1 signals drawn with delivered=False → agents don't act on them; info-revelation
 metric yields no market-1 rows (matches real data).
 - Determinism vs engine RNG: orchestrator truth/resolve/signal seeds are fixed functions of
 ids; agent RNG seeded separately. Golden test pins the combined output.

 Verification

 source .venv/bin/activate
 # generate synthetic sessions through the real engine + export CSVs
 python3 calibration/abm/cli.py --seed 42 --subject-count 9 --treated-count 3 \
   --b 18.0 --num-sessions 1 --outdir calibration/abm/output --emit-metrics
 # ABM tests
 pytest tests/test_abm_agents.py tests/test_abm_runner.py \
        tests/test_abm_export_pipeline.py tests/test_abm_golden.py -v
 # no regression to existing suite
 pytest
 Expected: real DB rows generated through the Orchestrator; full existing CSV export suite in
 outdir; all ABM tests green; full suite still 35+ green; benchmark_recompute.abs_diff ≈ 0
 confirming synthetic datasets are structurally identical to live exports.