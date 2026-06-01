"""watch.py — Run a single ABM market to completion and return a structured replay payload.

The return value is JSON-serializable and contains full trade tape, round summaries,
bot rosters, and market metadata suitable for client-side replay.
"""
from __future__ import annotations

from sqlalchemy import select

from calibration.abm.agents import Agent
from calibration.abm.config import SimConfig
from calibration.abm.profiles import PROFILE_PRESETS, apply_risk_aversion, assign_profiles, assign_risk_aversion
from calibration.abm.runner import (
    _apply_risk_override,
    _build_session_factory,
    _canonical_participants,
    _run_market_round,
    _to_database_url,
)
from server.db_models import Market, MarketResolution, MarketRole, Round
from server.orchestrator import Orchestrator


def run_single_market(
    *,
    seed: int = 42,
    market_number: int = 1,
    subject_count: int = 9,
    profile_mix: str = "rational:5,herder:2,noise:2",
    b: float = 36.0,
) -> dict:
    """Run one market to completion and return a JSON-serializable replay payload.

    Parameters
    ----------
    seed:
        RNG seed for full determinism.
    market_number:
        Which market to collect trades for (1-indexed). Markets 1..market_number-1 are
        run silently to advance the orchestrator to the correct stage.
    subject_count:
        Number of simulated participants.
    profile_mix:
        Comma-separated ``profile:count`` pairs (e.g. ``"rational:5,herder:2,noise:2"``).
    b:
        LMSR liquidity parameter.

    Returns
    -------
    dict
        Keys: ``market``, ``bots``, ``rounds``, ``trades``.
    """
    config = SimConfig(
        seed=seed,
        subject_count=subject_count,
        profile_mix=profile_mix,
        b=b,
        db_path=":memory:",
        include_practice=False,
        num_sessions=1,
    ).validated()

    database_url, _ = _to_database_url(config.db_path)
    db_factory = _build_session_factory(database_url)
    orch = Orchestrator(
        db_session_factory=db_factory,
        tournament_tie_break_mode="shared_prize",
        lmsr_b_parameter=config.b,
    )

    # Build agents the same way run_session does
    participants = _canonical_participants(config.subject_count)
    assigned = assign_profiles(participants, config.profile_mix)
    risk_draws = assign_risk_aversion(
        participants,
        mean=config.ra_mean,
        sd=config.ra_sd,
        lo=config.ra_lo,
        hi=config.ra_hi,
        seed=config.seed,
    )
    assignments = apply_risk_aversion(assigned, risk_draws)
    assignments = _apply_risk_override(assignments, config.risk_aversion)
    agents = {
        pid: Agent(participant_id=pid, profile=assignments.get(pid, PROFILE_PRESETS["rational"]))
        for pid in participants
    }

    session_id = orch.start_session(
        label=f"abm-watch-{seed}",
        rotation_id=1,
        subject_count=config.subject_count,
        treated_count=config.treated_count,
        lmsr_b_parameter=config.b,
        show_tournament_payout_screen=False,
    )

    # Run markets 1..market_number; only collect trades for the target market
    trades_collected: list[dict] = []

    def _collect(event: dict) -> None:
        trades_collected.append(event)

    for mn in range(1, market_number + 1):
        orch.start_market(session_id, mn)
        for agent in agents.values():
            agent.init_market()
        on_trade_fn = _collect if mn == market_number else None
        for rn in range(1, 6):
            _run_market_round(
                orch=orch,
                db_factory=db_factory,
                session_id=session_id,
                market_number=mn,
                round_number=rn,
                agents=agents,
                config=config,
                on_trade=on_trade_fn,
            )
        orch.resolve_market(session_id)

    # Read back market data from DB
    with db_factory() as db:
        market_row = db.scalar(
            select(Market).where(
                Market.session_id == session_id,
                Market.market_number == market_number,
            )
        )
        if market_row is None:
            raise RuntimeError(f"market {market_number} not found in DB after simulation")

        res_row = db.scalar(
            select(MarketResolution).where(MarketResolution.market_id == market_row.id)
        )
        if res_row is None:
            raise RuntimeError(f"no resolution row found for market {market_number}")

        rounds = list(
            db.scalars(
                select(Round)
                .where(Round.market_id == market_row.id)
                .order_by(Round.round_number)
            ).all()
        )

        roles = list(
            db.scalars(
                select(MarketRole).where(MarketRole.market_id == market_row.id)
            ).all()
        )

    # Build role lookup: participant_id -> role_tier
    role_by_pid: dict[str, str] = {r.participant_id: r.role_tier for r in roles}

    # Compute t_ms and sort trades
    round_duration_ms = config.round_duration_s * 1000
    for t in trades_collected:
        t["t_ms"] = (t["round_number"] - 1) * round_duration_ms + t["event_time_s"] * 1000
    trades_collected.sort(key=lambda t: t["t_ms"])

    # Build round summaries
    round_duration_s = config.round_duration_s
    rounds_payload = [
        {
            "round_number": r.round_number,
            "opening_price": float(r.opening_price) if r.opening_price is not None else None,
            "closing_price": float(r.closing_price) if r.closing_price is not None else None,
            "benchmark": float(r.bayesian_benchmark) if r.bayesian_benchmark is not None else None,
            "duration_s": round_duration_s,
        }
        for r in rounds
    ]

    # Build bots roster; risk_aversion comes from the final BehavioralProfile
    bots_payload = [
        {
            "id": pid,
            "profile": agents[pid].profile.name,
            "role_tier": role_by_pid.get(pid, "uninformed"),
            "risk_aversion": float(agents[pid].profile.risk_aversion),
        }
        for pid in participants
    ]

    return {
        "market": {
            "true_probability": float(market_row.true_probability),
            "outcome": int(res_row.outcome),
            "b": float(market_row.b_parameter),
            "round_duration_s": round_duration_s,
            "subject_count": config.subject_count,
        },
        "bots": bots_payload,
        "rounds": rounds_payload,
        "trades": trades_collected,
    }
