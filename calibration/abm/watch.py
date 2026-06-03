"""watch.py — Run a single ABM market to completion and return a structured replay payload.

The return value is JSON-serializable and contains full trade tape, round summaries,
bot rosters, and market metadata suitable for client-side replay.
"""
from __future__ import annotations

import os
import random
from decimal import Decimal

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


WATCH_SCENARIOS: dict[str, float] = {
    "very_no": 0.10,
    "no_lean": 0.30,
    "coinflip": 0.50,
    "yes_lean": 0.70,
    "very_yes": 0.90,
}


def _role_sets_for_market(
    *,
    participants: list[str],
    seed: int,
    informed_only_count: int,
    informed_whale_count: int,
    whale_only_count: int,
) -> tuple[set[str], set[str], set[str]]:
    ordered = sorted(participants)
    rng = random.Random(f"{seed}:watch-role-mix")
    shuffled = ordered[:]
    rng.shuffle(shuffled)
    overlap = set(shuffled[:informed_whale_count])
    informed_only = set(shuffled[informed_whale_count:informed_whale_count + informed_only_count])
    whale_only = set(
        shuffled[
            informed_whale_count + informed_only_count:
            informed_whale_count + informed_only_count + whale_only_count
        ]
    )
    return informed_only, overlap, whale_only


def _resolve_watch_scenario(*, seed: int, scenario: str) -> tuple[str, float | None]:
    normalized = scenario.strip().lower()
    if normalized == "market_default":
        return "market_default", None
    if normalized == "seeded":
        names = list(WATCH_SCENARIOS.keys())
        picked = names[seed % len(names)]
        return picked, WATCH_SCENARIOS[picked]
    if normalized not in WATCH_SCENARIOS:
        valid = ", ".join(["seeded", "market_default", *WATCH_SCENARIOS.keys()])
        raise ValueError(f"unknown scenario '{scenario}'. valid: {valid}")
    return normalized, WATCH_SCENARIOS[normalized]


def run_single_market(
    *,
    seed: int = 42,
    market_number: int = 1,
    subject_count: int = 9,
    profile_mix: str = "rational:5,herder:2,noise:2",
    b: float = 36.0,
    order_size_dist: str = "geometric:p=0.68,tail=0.35",
    reaction_delay_s: float = 0.65,
    reaction_delay_jitter_s: float = 0.35,
    informed_only_count: int = 3,
    informed_whale_count: int = 0,
    whale_only_count: int = 0,
    scenario: str = "seeded",
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
    order_size_dist:
        Order-size sampler spec (e.g. ``"geometric:p=0.45,tail=0.75"``).
    reaction_delay_s:
        Base hesitation (seconds) applied before each decision opportunity.
    reaction_delay_jitter_s:
        Extra uniform jitter added to hesitation on each decision opportunity.
    informed_only_count:
        Number of informed-only participants.
    informed_whale_count:
        Number of participants in the overlap between informed and whale.
    whale_only_count:
        Number of whale-only participants.
    scenario:
        One of ``seeded``, ``market_default``, or a named watch scenario such
        as ``very_no``/``coinflip``/``very_yes``.

    Returns
    -------
    dict
        Keys: ``market``, ``bots``, ``rounds``, ``trades``.
    """
    for name, value in (
        ("informed_only_count", informed_only_count),
        ("informed_whale_count", informed_whale_count),
        ("whale_only_count", whale_only_count),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
    bucket_total = informed_only_count + informed_whale_count + whale_only_count
    if bucket_total > subject_count:
        raise ValueError(
            "bucket counts must sum to less than or equal to subject_count, "
            f"got {bucket_total} > {subject_count}"
        )
    informed_count = informed_only_count + informed_whale_count
    whale_count = whale_only_count + informed_whale_count
    uninformed_count = subject_count - bucket_total
    config = SimConfig(
        seed=seed,
        subject_count=subject_count,
        treated_count=max(2, informed_count),
        profile_mix=profile_mix,
        b=b,
        order_size_dist=order_size_dist,
        reaction_delay_s=reaction_delay_s,
        reaction_delay_jitter_s=reaction_delay_jitter_s,
        db_path=":memory:",
        include_practice=False,
        num_sessions=1,
    ).validated()

    if not (1 <= market_number <= 4):
        raise ValueError(f"market_number must be between 1 and 4, got {market_number}")

    database_url, db_path = _to_database_url(config.db_path)
    db_factory = _build_session_factory(database_url)
    try:
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
            pid: Agent(
                participant_id=pid,
                profile=assignments.get(pid, PROFILE_PRESETS["rational"]),
                sim_seed=config.seed,
            )
            for pid in participants
        }
        informed_only_ids, overlap_ids, whale_only_ids = _role_sets_for_market(
            participants=participants,
            seed=seed,
            informed_only_count=informed_only_count,
            informed_whale_count=informed_whale_count,
            whale_only_count=whale_only_count,
        )
        # Split scenarios across seeds so market 2/3 true probabilities vary in watch mode.
        rotation_id = 1 if (seed % 2 == 0) else 2

        session_id = orch.start_session(
            label=f"abm-watch-{seed}",
            rotation_id=rotation_id,
            subject_count=config.subject_count,
            treated_count=config.treated_count,
            lmsr_b_parameter=config.b,
            show_tournament_payout_screen=False,
        )

        # Run markets 1..market_number; only collect trades for the target market
        trades_collected: list[dict] = []
        selected_scenario_name = "market_default"

        def _collect(event: dict) -> None:
            trades_collected.append(event)

        for mn in range(1, market_number + 1):
            orch.start_market(session_id, mn)
            if mn == market_number:
                selected_scenario_name, scenario_prob = _resolve_watch_scenario(seed=seed, scenario=scenario)
                with db_factory() as db:
                    market_row = db.scalar(
                        select(Market).where(
                            Market.session_id == session_id,
                            Market.market_number == mn,
                        )
                    )
                    if market_row is None:
                        raise RuntimeError(f"market {mn} not found while applying watch overrides")
                    if scenario_prob is not None:
                        market_row.true_probability = Decimal(str(scenario_prob))
                    role_rows = db.scalars(select(MarketRole).where(MarketRole.market_id == market_row.id)).all()
                    for role_row in role_rows:
                        is_informed_only = role_row.participant_id in informed_only_ids
                        is_overlap = role_row.participant_id in overlap_ids
                        is_whale_only = role_row.participant_id in whale_only_ids
                        is_informed = is_informed_only or is_overlap
                        is_whale = is_whale_only or is_overlap
                        if is_informed and is_whale:
                            role_row.role_tier = "informed"
                            role_row.endowment_tokens = Decimal("400")
                            role_row.starting_balance = Decimal("400")
                        elif is_informed:
                            role_row.role_tier = "informed"
                            role_row.endowment_tokens = Decimal("100")
                            role_row.starting_balance = Decimal("100")
                        elif is_whale:
                            role_row.role_tier = "uninformed"
                            role_row.endowment_tokens = Decimal("400")
                            role_row.starting_balance = Decimal("400")
                        else:
                            role_row.role_tier = "uninformed"
                            role_row.endowment_tokens = Decimal("100")
                            role_row.starting_balance = Decimal("100")
                    db.commit()
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
        role_group_by_pid: dict[str, str] = {}
        for role in roles:
            is_informed = role.role_tier == "informed"
            is_whale = float(role.endowment_tokens) > 100.0
            if is_informed and is_whale:
                role_group_by_pid[role.participant_id] = "informed_whale"
            elif is_informed:
                role_group_by_pid[role.participant_id] = "informed"
            elif is_whale:
                role_group_by_pid[role.participant_id] = "whale"
            else:
                role_group_by_pid[role.participant_id] = "uninformed"
        informed_realized = sum(1 for g in role_group_by_pid.values() if g in {"informed", "informed_whale"})
        whale_realized = sum(1 for g in role_group_by_pid.values() if g in {"whale", "informed_whale"})
        overlap_realized = sum(1 for g in role_group_by_pid.values() if g == "informed_whale")
        uninformed_realized = sum(1 for g in role_group_by_pid.values() if g == "uninformed")

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
                "role_group": role_group_by_pid.get(pid, "uninformed"),
                "is_informed": role_group_by_pid.get(pid, "uninformed") in {"informed", "informed_whale"},
                "is_whale": role_group_by_pid.get(pid, "uninformed") in {"whale", "informed_whale"},
                "risk_aversion": float(agents[pid].profile.risk_aversion),
                "starting_balance": 100.0,
            }
            for pid in participants
        ]
        start_balance_by_pid: dict[str, float] = {r.participant_id: float(r.endowment_tokens) for r in roles}
        for bot in bots_payload:
            bot["starting_balance"] = start_balance_by_pid.get(bot["id"], 100.0)

        return {
            "market": {
                "true_probability": float(market_row.true_probability),
                "outcome": int(res_row.outcome),
                "rotation_id": rotation_id,
                "scenario": selected_scenario_name,
                "treated_count": informed_realized,
                "treated_share": informed_realized / config.subject_count,
                "informed_count": informed_realized,
                "informed_share": informed_realized / config.subject_count,
                "informed_only_count": sum(1 for g in role_group_by_pid.values() if g == "informed"),
                "informed_whale_count": overlap_realized,
                "whale_count": whale_realized,
                "whale_share": whale_realized / config.subject_count,
                "whale_only_count": sum(1 for g in role_group_by_pid.values() if g == "whale"),
                "overlap_count": overlap_realized,
                "overlap_share": overlap_realized / config.subject_count,
                "uninformed_count": uninformed_realized,
                "uninformed_share": uninformed_realized / config.subject_count,
                "b": float(market_row.b_parameter),
                "round_duration_s": round_duration_s,
                "subject_count": config.subject_count,
            },
            "bots": bots_payload,
            "rounds": rounds_payload,
            "trades": trades_collected,
        }
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass
