from __future__ import annotations

import hashlib
import heapq
import random
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from calibration.abm.agents import Agent
from calibration.abm.config import SimConfig
from calibration.abm.profiles import PROFILE_PRESETS, BehavioralProfile, apply_risk_aversion, assign_profiles, assign_risk_aversion
from server.db_models import Base, Market, MarketRole, Round, Signal, Trade
from server.orchestrator import Orchestrator


@dataclass(frozen=True)
class ABMRunResult:
    session_ids: list[int]
    database_url: str
    db_path: str


def _canonical_participants(subject_count: int) -> list[str]:
    return [f"P{i:02d}" for i in range(1, subject_count + 1)]


def _to_database_url(db_path: str) -> tuple[str, str]:
    if db_path == ":memory:":
        handle = tempfile.NamedTemporaryFile(prefix="abm_mem_", suffix=".db", delete=False)
        handle.close()
        resolved = Path(handle.name).resolve()
        return f"sqlite:///{resolved}", str(resolved)
    if db_path.startswith("sqlite"):
        return db_path, db_path
    if db_path == "tempfile":
        handle = tempfile.NamedTemporaryFile(prefix="abm_", suffix=".db", delete=False)
        handle.close()
        resolved = Path(handle.name).resolve()
        return f"sqlite:///{resolved}", str(resolved)
    resolved = Path(db_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved}", str(resolved)


def _build_session_factory(database_url: str) -> sessionmaker[Session]:
    kwargs: dict[str, object] = {"future": True}
    if database_url.endswith(":memory:"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    elif database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **kwargs)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def _seed(
    *,
    sim_seed: int,
    session_id: int,
    market_id: int,
    round_id: int,
    participant_id: str,
    step: str,
) -> str:
    material = f"{sim_seed}:{session_id}:{market_id}:{round_id}:{participant_id}:{step}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _load_event_snapshot(
    db_factory: sessionmaker[Session],
    *,
    session_id: int,
    market_number: int,
    round_number: int,
    participant_id: str,
) -> tuple[int, int, float, float, float, MarketRole, Signal | None]:
    with db_factory() as db:
        market = db.scalar(
            select(Market).where(
                Market.session_id == session_id,
                Market.market_number == market_number,
            )
        )
        if market is None:
            raise ValueError("market not found")
        round_row = db.scalar(
            select(Round).where(
                Round.market_id == market.id,
                Round.round_number == round_number,
            )
        )
        if round_row is None:
            raise ValueError("round not found")
        role = db.scalar(
            select(MarketRole).where(
                MarketRole.market_id == market.id,
                MarketRole.participant_id == participant_id,
            )
        )
        if role is None:
            raise ValueError("market role not found")
        signal = db.scalar(
            select(Signal).where(
                Signal.round_id == round_row.id,
                Signal.participant_id == participant_id,
            )
        )

        return (
            market.id,
            round_row.id,
            float(market.q_yes),
            float(market.q_no),
            float(market.b_parameter),
            role,
            signal,
        )


def _set_trade_timestamp(
    db_factory: sessionmaker[Session],
    *,
    trade_id: int,
    executed_at: datetime,
) -> None:
    with db_factory() as db:
        trade_row = db.scalar(select(Trade).where(Trade.id == trade_id))
        if trade_row is None:
            return
        trade_row.executed_at = executed_at
        db.commit()


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _state_intensity(
    *,
    config: SimConfig,
    belief: float,
    current_price: float,
    ema_abs_return: float,
) -> float:
    edge_i = _clip(abs(belief - current_price) / 0.5, 0.0, 1.0)
    vol_t = _clip(ema_abs_return / config.vol_ref, 0.0, 1.0)
    raw = config.lambda_base * (1.0 + config.edge_gain * (edge_i**config.edge_exp)) * (
        1.0 + config.vol_gain * (vol_t**config.vol_exp)
    )
    return _clip(raw, config.lambda_min, config.lambda_max)


def _proposal_rate(config: SimConfig) -> float:
    if config.intensity_mode == "legacy_homogeneous":
        return config.event_intensity
    return config.lambda_max


def _update_ema_abs_return(*, current: float, abs_return: float, alpha: float) -> float:
    return alpha * abs_return + (1.0 - alpha) * current


def _next_decision_time(
    *,
    now_s: float,
    gap_rng: random.Random,
    proposal_rate: float,
    reaction_delay_s: float,
    reaction_delay_jitter_s: float,
) -> float:
    jitter = gap_rng.random() * reaction_delay_jitter_s
    hesitation = reaction_delay_s + jitter
    return now_s + hesitation + gap_rng.expovariate(proposal_rate)


def _run_market_round(
    *,
    orch: Orchestrator,
    db_factory: sessionmaker[Session],
    session_id: int,
    market_number: int,
    round_number: int,
    agents: dict[str, Agent],
    config: SimConfig,
    on_trade: Callable | None = None,
) -> None:
    round_row = orch.start_round(session_id, round_number)
    proposal_rate = _proposal_rate(config)
    if proposal_rate <= 0:
        orch.end_round(session_id)
        return

    gap_rngs: dict[str, random.Random] = {}
    accept_rngs: dict[str, random.Random] = {}
    accepted_event_index: dict[str, int] = {}
    event_heap: list[tuple[float, str, int]] = []
    for participant_id in sorted(agents):
        gap_rng = random.Random(
            _seed(
                session_id=session_id,
                market_id=round_row.market_id,
                round_id=round_row.id,
                participant_id=participant_id,
                sim_seed=config.seed,
                step="arrivals_gap" if config.intensity_mode == "state_hybrid" else "arrivals",
            )
        )
        gap_rngs[participant_id] = gap_rng
        accept_rngs[participant_id] = random.Random(
            _seed(
                session_id=session_id,
                market_id=round_row.market_id,
                round_id=round_row.id,
                participant_id=participant_id,
                sim_seed=config.seed,
                step="arrivals_accept",
            )
        )
        accepted_event_index[participant_id] = 0
        first_t = _next_decision_time(
            now_s=0.0,
            gap_rng=gap_rng,
            proposal_rate=proposal_rate,
            reaction_delay_s=config.reaction_delay_s,
            reaction_delay_jitter_s=config.reaction_delay_jitter_s,
        )
        if first_t <= config.round_duration_s:
            heapq.heappush(event_heap, (first_t, participant_id, 0))

    round_base = datetime.now(timezone.utc)
    trade_seq = 0
    ema_abs_return = 0.0

    while event_heap:
        event_time_s, participant_id, candidate_index = heapq.heappop(event_heap)
        try:
            market_id, db_round_id, q_yes, q_no, b, role, signal = _load_event_snapshot(
                db_factory,
                session_id=session_id,
                market_number=market_number,
                round_number=round_number,
                participant_id=participant_id,
            )
        except ValueError:
            continue

        agent = agents[participant_id]

        from server import lmsr

        current_price = lmsr.price(q_yes, q_no, b) if b > 0 else 0.5
        event_index = accepted_event_index[participant_id]
        if config.intensity_mode == "state_hybrid":
            intensity = _state_intensity(
                config=config,
                belief=float(agent.belief),
                current_price=current_price,
                ema_abs_return=ema_abs_return,
            )
            if accept_rngs[participant_id].random() > (intensity / config.lambda_max):
                next_t = _next_decision_time(
                    now_s=event_time_s,
                    gap_rng=gap_rngs[participant_id],
                    proposal_rate=proposal_rate,
                    reaction_delay_s=config.reaction_delay_s,
                    reaction_delay_jitter_s=config.reaction_delay_jitter_s,
                )
                if next_t <= config.round_duration_s:
                    heapq.heappush(event_heap, (next_t, participant_id, candidate_index + 1))
                continue

        agent.update_belief(
            session_id=session_id,
            market_id=market_id,
            round_id=db_round_id,
            current_price=current_price,
            signal_value=signal.signal_value if signal is not None else None,
            signal_theta=float(signal.theta) if signal is not None else None,
            signal_delivered=bool(signal.delivered) if signal is not None else False,
            event_index=event_index,
        )
        accepted_event_index[participant_id] = event_index + 1

        trades = agent.decide(
            session_id=session_id,
            market_id=market_id,
            round_id=db_round_id,
            q_yes=q_yes,
            q_no=q_no,
            b=b,
            balance=float(role.starting_balance),
            yes_held=float(role.yes_held),
            no_held=float(role.no_held),
            event_index=event_index,
            edge_threshold=config.edge_threshold,
            sell_propensity=config.sell_propensity,
            order_size_dist=config.order_size_dist,
        )

        for trade in trades:
            try:
                result = orch.record_trade(session_id, participant_id, trade)
            except ValueError:
                continue

            if config.intensity_mode == "state_hybrid":
                price_move = abs(float(result.price_after) - float(result.price_before))
                ema_abs_return = _update_ema_abs_return(
                    current=ema_abs_return,
                    abs_return=price_move,
                    alpha=config.vol_ema_alpha,
                )

            executed_at = round_base + timedelta(seconds=event_time_s, microseconds=trade_seq)
            trade_seq += 1
            _set_trade_timestamp(
                db_factory,
                trade_id=result.trade_id,
                executed_at=executed_at,
            )

            if on_trade is not None:
                on_trade(
                    {
                        "round_number": round_number,
                        "event_time_s": event_time_s,
                        "participant_id": participant_id,
                        "profile": agent.profile.name,
                        "side": trade.side,
                        "direction": trade.direction,
                        "quantity": trade.quantity,
                        "price_before": result.price_before,
                        "price_after": result.price_after,
                        "q_yes_after": result.q_yes_after,
                        "q_no_after": result.q_no_after,
                        "balance_after": result.balance_after,
                        "yes_held": result.yes_held,
                        "no_held": result.no_held,
                        "belief": float(agent.belief),
                    }
                )

        next_t = _next_decision_time(
            now_s=event_time_s,
            gap_rng=gap_rngs[participant_id],
            proposal_rate=proposal_rate,
            reaction_delay_s=config.reaction_delay_s,
            reaction_delay_jitter_s=config.reaction_delay_jitter_s,
        )
        if next_t <= config.round_duration_s:
            heapq.heappush(event_heap, (next_t, participant_id, candidate_index + 1))

    orch.end_round(session_id)


def _apply_risk_override(
    assigned: dict[str, BehavioralProfile],
    risk_aversion: float | None,
) -> dict[str, BehavioralProfile]:
    if risk_aversion is None:
        return assigned
    overridden: dict[str, BehavioralProfile] = {}
    for pid, profile in assigned.items():
        overridden[pid] = BehavioralProfile(
            name=profile.name,
            risk_aversion=risk_aversion,
            bias=profile.bias,
            stubbornness=profile.stubbornness,
            expertise=profile.expertise,
            market_imitation=profile.market_imitation,
            budget_variance=profile.budget_variance,
        )
    return overridden


def run_session(
    *,
    orch: Orchestrator,
    db_factory: sessionmaker[Session],
    config: SimConfig,
    session_index: int,
) -> int:
    participants = _canonical_participants(config.subject_count)
    assigned = assign_profiles(participants, config.profile_mix)
    risk_draws = assign_risk_aversion(
        participants,
        mean=config.ra_mean,
        sd=config.ra_sd,
        lo=config.ra_lo,
        hi=config.ra_hi,
        seed=config.seed + session_index,
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

    session_id = orch.start_session(
        label=f"abm-{config.seed}-{session_index + 1}",
        rotation_id=config.rotation_id + session_index,
        subject_count=config.subject_count,
        treated_count=config.treated_count,
        lmsr_b_parameter=config.b,
        show_tournament_payout_screen=True,
    )

    if config.include_practice:
        orch.start_market(session_id, Orchestrator.PRACTICE_MARKET_NUMBER, is_practice=True)
        for agent in agents.values():
            agent.init_market()
        _run_market_round(
            orch=orch,
            db_factory=db_factory,
            session_id=session_id,
            market_number=Orchestrator.PRACTICE_MARKET_NUMBER,
            round_number=1,
            agents=agents,
            config=config,
        )
        orch.close_practice_market(session_id)

    for market_number in range(1, 5):
        orch.start_market(session_id, market_number)
        for agent in agents.values():
            agent.init_market()
        for round_number in range(1, 6):
            _run_market_round(
                orch=orch,
                db_factory=db_factory,
                session_id=session_id,
                market_number=market_number,
                round_number=round_number,
                agents=agents,
                config=config,
            )
        orch.resolve_market(session_id)
    orch.close_session(session_id)
    return session_id


def run_abm(config: SimConfig) -> ABMRunResult:
    cfg = config.validated()
    database_url, resolved_path = _to_database_url(cfg.db_path)
    db_factory = _build_session_factory(database_url)
    orch = Orchestrator(
        db_session_factory=db_factory,
        tournament_tie_break_mode="shared_prize",
        lmsr_b_parameter=cfg.b,
    )
    session_ids: list[int] = []
    for idx in range(cfg.num_sessions):
        session_ids.append(
            run_session(
                orch=orch,
                db_factory=db_factory,
                config=cfg,
                session_index=idx,
            )
        )
    return ABMRunResult(session_ids=session_ids, database_url=database_url, db_path=resolved_path)
