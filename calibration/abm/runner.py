from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from calibration.abm.agents import Agent
from calibration.abm.config import SimConfig
from calibration.abm.profiles import PROFILE_PRESETS, BehavioralProfile, assign_profiles
from server.db_models import Base, Market, MarketRole, Round, Signal
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


def _load_round_snapshot(
    db_factory: sessionmaker[Session],
    *,
    session_id: int,
    market_number: int,
    round_number: int,
) -> tuple[int, float, float, float, dict[str, MarketRole], dict[str, Signal]]:
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
        roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
        signals = db.scalars(select(Signal).where(Signal.round_id == round_row.id)).all()
        role_map = {r.participant_id: r for r in roles}
        signal_map = {s.participant_id: s for s in signals}
        return (
            market.id,
            float(market.q_yes),
            float(market.q_no),
            float(market.b_parameter),
            role_map,
            signal_map,
        )


def _run_market_round(
    *,
    orch: Orchestrator,
    db_factory: sessionmaker[Session],
    session_id: int,
    market_number: int,
    round_number: int,
    agents: dict[str, Agent],
) -> None:
    round_row = orch.start_round(session_id, round_number)
    market_id, q_yes, q_no, b, role_map, signal_map = _load_round_snapshot(
        db_factory,
        session_id=session_id,
        market_number=market_number,
        round_number=round_number,
    )
    for participant_id in sorted(agents):
        role = role_map[participant_id]
        signal = signal_map.get(participant_id)
        agent = agents[participant_id]
        current_price = 0.5
        if b > 0:
            from server import lmsr

            current_price = lmsr.price(q_yes, q_no, b)
        agent.update_belief(
            session_id=session_id,
            market_id=market_id,
            round_id=round_row.id,
            current_price=current_price,
            signal_value=signal.signal_value if signal is not None else None,
            signal_theta=float(signal.theta) if signal is not None else None,
            signal_delivered=bool(signal.delivered) if signal is not None else False,
        )
        trades = agent.decide(
            session_id=session_id,
            market_id=market_id,
            round_id=round_row.id,
            q_yes=q_yes,
            q_no=q_no,
            b=b,
            balance=float(role.starting_balance),
        )
        for trade in trades:
            try:
                result = orch.record_trade(session_id, participant_id, trade)
            except ValueError:
                continue
            q_yes = result.q_yes_after
            q_no = result.q_no_after
            role.starting_balance = result.balance_after
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
    assignments = _apply_risk_override(assign_profiles(participants, config.profile_mix), config.risk_aversion)
    agents = {pid: Agent(participant_id=pid, profile=assignments.get(pid, PROFILE_PRESETS["rational"])) for pid in participants}
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
