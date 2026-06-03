ABM Continuous-Time Recalibration (experiment_1 / export_1 anchored)

 Context

 The ABM (calibration/abm/) headlessly replays the real server/ orchestrator with
 synthetic agents standing in for humans. Today it trades single-pass per round
 (one deterministic sweep, agents sorted by id) and is buys-only — agents never sell,
 so no negative-cost trades ever appear. Defaults (b=18, 9 agents, treated=3) were guesses,
 not anchored to data.

 We now have real reference data:
 - experiment_1/ — full DB dump of 2 human sessions: 9 agents, b=36, treated_count=3,
 4 real markets/session (scenarios C/A/B/D, true_prob 0.5/0.75/0.25/0.65), 3,459 trades.
 Empirical order flow: median order size 1, mean 6.47, max 20; buy/sell ≈ 58/42;
 28.7% of trades have cost < 0 (sells returning cash).
 - export_1/ — derived real-markets-only subset (practice excluded), used as the
 cross-check that target extraction matches the live export schema.

 Goal: make the ABM produce human-like order flow (small-order-heavy, two-sided, continuous
 intra-round activity) and calibrate it against these references, with a reproducible
 scoring + acceptance-gate harness. Validation runs at 9 agents (1:1 with reference,
 no normalization), and a separate 24-agent production config is exposed for scale-up.

 Decisions locked (from user)

 1. Cohort: keep a 9-agent validation config (direct 1:1 comparison to reference) AND
 a 24-agent production config (treated=8 ≈ 33%, b=36). Calibration fits on 9-agent;
 24-agent is a scaled deployment whose per-agent metrics are sanity-checked against the
 same per-agent bands.
 2. Risk aversion: per-agent truncated normal clamped to [min,max]; calibration sweeps
 the truncnorm params (mean/sd) and/or bounds.
 3. Golden tests: replace single-pass with continuous-time as the only code path;
 regenerate golden snapshots. No back-compat flag.
 4. Returns: total/leaderboard "return" is net of initial endowment
 (final_balance - endowment), consistent with sim_metrics ratio already being
 (final-endowment)/endowment.

 Key facts that shape the implementation (verified)

 - Sells need NO engine change. TradeRequest.side already accepts "sell"
 (server/events.py:104); record_trade applies side_sign=-1 and guards short-sells
 (server/orchestrator.py:304-310). Selling held inventory yields cost<0 automatically.
 - Order size is hard-capped 1–20 by TradeRequest.quantity (events.py:106). Matches the
 reference max of 20. Large trades must be split into ≤20 chunks (already done in agents.py:112-118).
 - State is already re-read per trade. record_trade reloads market q_yes/q_no with
 with_for_update() each call, so "continually exposed to current price" is satisfied by simply
 calling decide() repeatedly within a round and feeding back the returned state.
 - ABM reuses real lmsr/bayesian/roles/orchestrator — do not reimplement market math.

 ---
 Implementation

 1. Continuous-time round runner — calibration/abm/runner.py

 Replace the single deterministic sweep in _run_market_round() (lines 97-148) with a
 virtual-clock event loop over t ∈ [0, round_duration_s] (default 90s simulated):

 - Build a merged event stream: each agent draws inter-arrival gaps from an exponential process
 (rate = event_intensity per agent), producing (t, participant_id, event_index) events.
 Process events in ascending t.
 - At each event: reload that agent's live snapshot (market q_yes/q_no via the orchestrator's
 current DB state, the agent's balance/holdings from its MarketRole row, signal/posterior),
 call agent.update_belief(...) then agent.decide(...), and submit any returned
 TradeRequests through orch.record_trade() (unchanged). Cache nothing stale — read fresh.
 - Persist the virtual timestamp on each trade. Trade.executed_at is the natural column;
 set it from a base time + t so exported rows carry monotonic simulated time. No wall-clock
 sleeping — the loop runs as fast as the CPU allows.
 - Determinism: the per-agent arrival process is seeded from
 _seed(session, market, round, participant, step="arrivals"); each decision uses
 step=f"decide:{event_index}" and belief uses step=f"belief:{event_index}". Event ordering
 is fully determined by seeds, so the whole session stays reproducible.
 - Keep the existing market/round structure in run_session() (4 real markets × 5 rounds,
 optional practice). Only the intra-round body changes.

 2. Two-sided agent policy — calibration/abm/agents.py

 Extend decide() (lines 74-118) to emit buy, sell, or hold:

 - Edge & direction: keep p = lmsr.price(...), edge = belief - p. Buy the side the agent
 believes underpriced; sell held inventory of a side when belief has moved against it
 (reversal/unwind) or to take profit. Selling requires yes_held/no_held > 0 (engine enforces
 it too).
 - Small-order-heavy sizing: replace the single target_qty with a draw from a config
 order-size distribution skewed toward 1 (reference median=1, mean≈6.5). E.g. geometric /
 truncated-power-law on [1,20] with an occasional larger draw; scale the probability of
 acting and size by (1-risk_aversion), edge, and remaining affordable/held quantity.
 - Sell propensity: a sell_propensity knob governs how readily an agent unwinds; this is
 the lever that pushes the cost<0 share toward the reference 28.7%.
 - Preserve the no-trade band (|edge| < edge_threshold), affordability clamp
 (lmsr.max_purchasable), and ≤20 chunk splitting.
 - Seeds now include event_index (see §1) so repeated intra-round events differ.

 3. Heterogeneous risk aversion — calibration/abm/profiles.py + config.py

 - Add assign_risk_aversion(participant_ids, *, mean, sd, lo, hi, seed) sampling a
 truncated normal per agent (deterministic, seeded). Apply over the existing profile
 presets, overriding each profile's risk_aversion per-agent.
 - This supersedes the current single scalar override in runner.py:151-168.

 4. Config / defaults — calibration/abm/config.py

 Extend SimConfig (lines 9-21). New continuous-time + heterogeneity knobs (with defaults that
 reproduce the reference order flow once calibrated):

 round_duration_s: float = 90.0        # simulated, not wall-clock
 event_intensity: float = ...          # per-agent arrival rate (Hz of virtual events)
 order_size_dist: str = ...            # name + params for 1-skewed sizing
 sell_propensity: float = ...          # drives cost<0 share
 edge_threshold: float = 0.02          # no-trade band (existing 0.02)
 ra_mean / ra_sd / ra_lo / ra_hi       # truncnorm risk-aversion params

 Provide two named presets (helper constructors or JSON configs under calibration/abm/):
 - validation: subject_count=9, treated_count=3, b=36.0 (matches experiment_1).
 - production: subject_count=24, treated_count=8, b=36.0.

 Update validation in __post_init__ for the new fields.

 5. Calibration scoring + acceptance gate — new calibration/abm/calibrate.py (+ CLI)

 Reuse existing infra; do not rebuild metrics from scratch:
 - Target extractor extract_reference_targets(): load experiment_1/*.csv (real markets only,
 matching export_1's practice-excluded subset) and compute per-agent-round targets:
   - trades per agent-round, quantity per agent-round (primary, volume-first),
   - order-size distribution (median + quantiles),
   - sell-share / cost<0 share,
   - per-market activity (all 4 non-practice markets non-empty).
 Cross-check the extracted trade set against export_1/market_*_trades.csv for consistency
 (row-count / id alignment) and fail loudly on mismatch.
 - Scorer: run the ABM (9-agent validation config) via runner.run_abm, export via
 export.export_session_outputs, derive the same per-agent metrics, and score each metric as a
 band ratio (modeled / reference). Reuse sim_metrics.simulation_report for the
 price/return/convergence side metrics.
 - Sweep: grid/random over event_intensity, sell_propensity, order-size params, and
 risk-aversion truncnorm params (mirror b_sweep.py's structure, but multi-knob).
 - Acceptance gate: for each session profile, every primary per-agent volume metric within
 0.5×–1.5× of reference, non-zero activity in all 4 non-practice markets, and report
 residual mismatch (no perfect-fit requirement).

 6. CLI / outputs

 Add a calibration command (extend calibration/abm/cli.py or a sibling entry) that writes:
 - leaderboard.csv — candidate params + scores, sorted.
 - chosen_params.json — winning config.
 - abm_vs_reference.json — chosen-config modeled metrics vs reference, per-metric band ratios,
 gate pass/fail. "Total return" rows reported net of endowment.

 ---
 Tests

 Mirror existing conventions (tests/conftest.py autouse reset_db, SQLite tmp_path,
 SQLAlchemy ORM assertions).

 - Agents (tests/test_abm_agents.py, extend): continuous-time event decisions deterministic
 given seed+event_index; sell path valid (never short-sells beyond holdings, respects
 balance); small-order-heavy sizing (median draw ≈ 1); hold when |edge|<threshold.
 - Runner (tests/test_abm_runner.py, update): 9-agent and 24-agent runs both populate all
 4 real markets; both buy and sell (cost<0) trades appear; all trades 1≤qty≤20; no invalid
 trades; virtual executed_at monotonic within a round.
 - Calibration (new tests/test_abm_calibrate.py): extract_reference_targets matches known
 experiment_1 counts and agrees with export_1; scorer band-ratio math correct; acceptance
 gate passes on a calibrated config and fails on a deliberately off-target one.
 - Golden (tests/test_abm_golden.py, regenerate): new pinned snapshot for continuous-time
 defaults (new trade_count, closing prices, return ratios). Document that values changed because
 single-pass→continuous + sells is a deliberate behavior change.
 - Export pipeline (tests/test_abm_export_pipeline.py): keep the abs_diff ≤ 1e-9 benchmark
 parity check; confirm raw trade export now contains negative-cost rows.

 Verification (end-to-end)

 # 1. Unit + integration suite green
 pytest tests/test_abm_agents.py tests/test_abm_runner.py \
        tests/test_abm_golden.py tests/test_abm_export_pipeline.py \
        tests/test_abm_calibrate.py -v

 # 2. Extract reference targets and confirm experiment_1/export_1 agree
 python3 -m calibration.abm.calibrate --extract-only   # prints per-agent targets

 # 3. Run a calibration sweep; inspect leaderboard + gate
 python3 -m calibration.abm.calibrate --config validation --sweep ...
 #   -> writes leaderboard.csv, chosen_params.json, abm_vs_reference.json

 # 4. Sanity: chosen config, all 4 markets active, buy+sell present, bands within 0.5x-1.5x
 #   (read abm_vs_reference.json: every primary metric gate == pass)

 # 5. Production scale-up runs clean
 python3 -m calibration.abm.cli --config production --emit-metrics

 Manual sanity check on the chosen run: median order size ≈ 1, cost<0 share ≈ 0.29,
 buy/sell ≈ 58/42, all 4 non-practice markets non-empty.

 Out of scope / assumptions

 - Server/orchestrator/lmsr/bayesian untouched (sells already supported).
 - "Continually exposed to current price" = repeated intra-round events with fresh state re-read,
 not a continuous-derivative model.
 - 90s round is simulated time only; execution is as-fast-as-CPU.
 - 24-agent production is a deployment, not a fit target; the 9-agent config is the calibration
 anchor (avoids the per-agent normalization assumption breaking under fixed b=36).