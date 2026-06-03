from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from server import bayesian, lmsr
from server.db_models import AdminAction, Market, MarketResolution, MarketRole, Participant, ParticipantSession, Round, SessionModel, Signal, TournamentRanking, Trade
from server.events import TradeRequest
from server.roles import MarketAssignment, get_assignment, get_market_config


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
    current_market_number: int | None = None
    current_round_number: int | None = None
    market_cache: dict[str, Any] = field(default_factory=dict)
    participants_cache: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeResult:
    trade_id: int
    cost: float
    price_before: float
    price_after: float
    q_yes_after: float
    q_no_after: float
    balance_after: float
    yes_held: float
    no_held: float


class Orchestrator:
    PRACTICE_MARKET_NUMBER = 0

    def __init__(
        self,
        db_session_factory: sessionmaker[Session],
        tournament_tie_break_mode: str = "shared_prize",
        lmsr_b_parameter: float = 18.0,
    ):
        self.db_session_factory = db_session_factory
        self.sessions: dict[int, SessionState] = {}
        if tournament_tie_break_mode not in {"shared_prize", "random"}:
            raise ValueError("tournament_tie_break_mode must be 'shared_prize' or 'random'")
        self.tournament_tie_break_mode = tournament_tie_break_mode
        if lmsr_b_parameter <= 0:
            raise ValueError("lmsr_b_parameter must be > 0")
        self.lmsr_b_parameter = lmsr_b_parameter

    def _require_state(self, session_id: int) -> SessionState:
        if session_id not in self.sessions:
            raise ValueError(f"Unknown session_id={session_id}")
        return self.sessions[session_id]

    def start_session(
        self,
        label: str,
        rotation_id: int,
        subject_count: int,
        treated_count: int = 3,
        lmsr_b_parameter: float = 36.0,
        show_tournament_payout_screen: bool = True,
    ) -> int:
        if lmsr_b_parameter <= 0:
            raise ValueError("lmsr_b_parameter must be > 0")
        if treated_count < 2:
            raise ValueError("treated_count must be >= 2")
        if treated_count > subject_count:
            raise ValueError("treated_count must be <= subject_count")
        with self.db_session_factory() as db:
            session = SessionModel(
                session_label=label,
                rotation_id=rotation_id,
                scenario_order="C,A,B,D",
                treated_count=treated_count,
                lmsr_b_parameter=Decimal(str(lmsr_b_parameter)),
                show_tournament_payout_screen=show_tournament_payout_screen,
            )
            db.add(session)
            db.flush()

            for n in range(1, subject_count + 1):
                pid = f"P{n:02d}"
                participant = db.get(Participant, pid)
                if participant is None:
                    participant = Participant(id=pid)
                    db.add(participant)
                    db.flush()
                token = f"{session.id}:{pid}"
                db.add(
                    ParticipantSession(
                        session_id=session.id,
                        participant_id=pid,
                        join_token=token,
                    )
                )

            db.commit()

        self.sessions[session.id] = SessionState(session_id=session.id, phase=SessionPhase.SESSION_OPEN)
        return session.id

    def start_market(self, session_id: int, market_number: int, is_practice: bool = False) -> Market:
        state = self._require_state(session_id)
        if state.phase not in {SessionPhase.SESSION_OPEN, SessionPhase.MARKET_RESOLVED}:
            raise ValueError("Cannot start market from current phase")
        if is_practice and state.phase != SessionPhase.SESSION_OPEN:
            raise ValueError("Cannot start practice round from current phase")

        with self.db_session_factory() as db:
            session_row = db.get(SessionModel, session_id)
            if session_row is None:
                raise ValueError("Session not found")

            if is_practice:
                market_number = self.PRACTICE_MARKET_NUMBER
                existing_practice_market = db.scalars(
                    select(Market).where(
                        Market.session_id == session_id,
                        Market.market_number == self.PRACTICE_MARKET_NUMBER,
                    )
                ).first()
                if existing_practice_market is not None:
                    raise ValueError("Practice round already completed for this session")
                market_cfg = get_market_config(
                    session_row.rotation_id,
                    1,
                    lmsr_b_parameter=float(session_row.lmsr_b_parameter),
                )
            else:
                market_cfg = get_market_config(
                    session_row.rotation_id,
                    market_number,
                    lmsr_b_parameter=float(session_row.lmsr_b_parameter),
                )
            market = Market(
                session_id=session_id,
                market_number=market_number,
                is_practice=is_practice,
                scenario_id=market_cfg.scenario_id,
                true_probability=Decimal(str(market_cfg.true_probability)),
                stage=market_cfg.stage,
                b_parameter=Decimal(str(market_cfg.b_parameter)),
                q_yes=Decimal("0"),
                q_no=Decimal("0"),
                opened_at=datetime.now(timezone.utc),
            )
            db.add(market)
            db.flush()

            participants = db.scalars(
                select(ParticipantSession.participant_id).where(ParticipantSession.session_id == session_id)
            ).all()
            for pid in participants:
                if is_practice:
                    assign = MarketAssignment(role_tier="uninformed", endowment_tokens=100.0)
                else:
                    assign = get_assignment(
                        session_id=session_id,
                        session_rotation_id=session_row.rotation_id,
                        participant_id=pid,
                        market_number=market_number,
                        subject_count=len(participants),
                        treated_count=session_row.treated_count,
                    )
                db.add(
                    MarketRole(
                        market_id=market.id,
                        participant_id=pid,
                        role_tier=assign.role_tier,
                        endowment_tokens=Decimal(str(assign.endowment_tokens)),
                        starting_balance=Decimal(str(assign.endowment_tokens)),
                    )
                )

            db.commit()
            db.refresh(market)

        state.phase = SessionPhase.MARKET_OPEN
        state.current_market_number = market_number
        state.current_round_number = None
        state.market_cache = {
            "market_id": market.id,
            "q_yes": 0.0,
            "q_no": 0.0,
            "b": float(market.b_parameter),
            "stage": market.stage,
            "is_practice": bool(market.is_practice),
        }
        return market

    def _prior_by_participant_before_round(self, db: Session, market_id: int, round_number: int) -> dict[str, float]:
        signal_rows = db.scalars(
            select(Signal)
            .join(Round, Signal.round_id == Round.id)
            .where(
                Round.market_id == market_id,
                Round.round_number < round_number,
                Signal.delivered.is_(True),
            )
            .order_by(Round.round_number, Signal.id)
        ).all()
        priors: dict[str, float] = {}
        for signal_row in signal_rows:
            pid = signal_row.participant_id
            prior = priors.get(pid, 0.5)
            priors[pid] = bayesian.update_posterior(
                prior=prior,
                signal=signal_row.signal_value,
                theta=float(signal_row.theta),
            )
        return priors

    def start_round(self, session_id: int, round_number: int) -> Round:
        state = self._require_state(session_id)
        if state.phase not in {SessionPhase.MARKET_OPEN, SessionPhase.ROUND_CLOSED}:
            raise ValueError("Cannot start round from current phase")

        with self.db_session_factory() as db:
            market = self._current_market_row(db, session_id, state.current_market_number)
            if market is None:
                raise ValueError("No open market")

            opening_price = lmsr.price(float(market.q_yes), float(market.q_no), float(market.b_parameter))
            round_row = Round(
                market_id=market.id,
                round_number=round_number,
                opened_at=datetime.now(timezone.utc),
                opening_price=Decimal(str(opening_price)),
            )
            db.add(round_row)
            db.flush()

            role_rows = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
            market_roles: list[tuple[str, MarketAssignment]] = []
            for role in role_rows:
                market_roles.append(
                    (
                        role.participant_id,
                        MarketAssignment(role_tier=role.role_tier, endowment_tokens=float(role.endowment_tokens)),
                    )
                )

            true_outcome = self._draw_market_truth(session_id, market.id, float(market.true_probability))
            prior_by_participant = self._prior_by_participant_before_round(db, market.id, round_number)
            draws = bayesian.draw_for_round(
                session_id=session_id,
                market_id=market.id,
                round_id=round_row.id,
                market_roles=market_roles,
                true_outcome=true_outcome,
                true_probability=float(market.true_probability),
                stage=market.stage,
                prior_by_participant=prior_by_participant,
            )
            for draw in draws:
                db.add(
                    Signal(
                        round_id=round_row.id,
                        participant_id=draw.participant_id,
                        signal_value=draw.value,
                        theta=Decimal(str(draw.theta)),
                        posterior=Decimal(str(draw.posterior)),
                        delivered=draw.delivered,
                        rng_seed=draw.seed,
                    )
                )
            db.commit()
            db.refresh(round_row)

        state.phase = SessionPhase.ROUND_OPEN
        state.current_round_number = round_number
        return round_row

    def record_trade(self, session_id: int, participant_id: str, trade: TradeRequest) -> TradeResult:
        state = self._require_state(session_id)
        if state.phase != SessionPhase.ROUND_OPEN:
            raise ValueError("ROUND_CLOSED")

        with self.db_session_factory() as db:
            market = None
            if state.current_market_number is not None:
                market = db.scalars(
                    select(Market)
                    .where(
                        Market.session_id == session_id,
                        Market.market_number == state.current_market_number,
                    )
                    .with_for_update()
                ).first()
            round_row = self._current_round_row(db, market.id, state.current_round_number) if market else None
            if market is None or round_row is None:
                raise ValueError("No active market/round")
            if round_row.closed_at is not None:
                raise ValueError("ROUND_CLOSED")

            role_row = db.scalars(
                select(MarketRole)
                .where(
                    MarketRole.market_id == market.id,
                    MarketRole.participant_id == participant_id,
                )
                .with_for_update()
            ).first()
            if role_row is None:
                raise ValueError("unknown participant")

            side_sign = 1.0 if trade.side == "buy" else -1.0
            d_yes = float(trade.quantity * side_sign if trade.direction == "yes" else 0)
            d_no = float(trade.quantity * side_sign if trade.direction == "no" else 0)
            if trade.side == "sell":
                held = float(role_row.yes_held) if trade.direction == "yes" else float(role_row.no_held)
                if float(trade.quantity) > held:
                    raise ValueError("SHORT_SELL_NOT_ALLOWED")
            price_before = lmsr.price(float(market.q_yes), float(market.q_no), float(market.b_parameter))
            delta_cost = lmsr.cost(float(market.q_yes), float(market.q_no), d_yes, d_no, float(market.b_parameter))
            if delta_cost > float(role_row.starting_balance):
                raise ValueError("INSUFFICIENT_FUNDS")

            new_q_yes = float(market.q_yes) + d_yes
            new_q_no = float(market.q_no) + d_no
            price_after = lmsr.price(new_q_yes, new_q_no, float(market.b_parameter))

            role_row.starting_balance = Decimal(str(float(role_row.starting_balance) - delta_cost))
            role_row.yes_held = Decimal(str(float(role_row.yes_held) + d_yes))
            role_row.no_held = Decimal(str(float(role_row.no_held) + d_no))
            market.q_yes = Decimal(str(new_q_yes))
            market.q_no = Decimal(str(new_q_no))

            trade_row = Trade(
                round_id=round_row.id,
                participant_id=participant_id,
                direction=trade.direction,
                quantity=trade.quantity,
                cost=Decimal(str(delta_cost)),
                price_before=Decimal(str(price_before)),
                price_after=Decimal(str(price_after)),
                q_yes_after=Decimal(str(new_q_yes)),
                q_no_after=Decimal(str(new_q_no)),
            )
            db.add(trade_row)
            db.commit()
            db.refresh(trade_row)

            return TradeResult(
                trade_id=trade_row.id,
                cost=float(trade_row.cost),
                price_before=float(trade_row.price_before),
                price_after=float(trade_row.price_after),
                q_yes_after=float(trade_row.q_yes_after),
                q_no_after=float(trade_row.q_no_after),
                balance_after=float(role_row.starting_balance),
                yes_held=float(role_row.yes_held),
                no_held=float(role_row.no_held),
            )

    def end_round(self, session_id: int) -> Round:
        state = self._require_state(session_id)
        if state.phase != SessionPhase.ROUND_OPEN:
            raise ValueError("No open round to close")

        with self.db_session_factory() as db:
            market = self._current_market_row(db, session_id, state.current_market_number)
            round_row = self._current_round_row(db, market.id, state.current_round_number) if market else None
            if market is None or round_row is None:
                raise ValueError("No active market/round")
            closing_price = lmsr.price(float(market.q_yes), float(market.q_no), float(market.b_parameter))
            signal_rows = db.scalars(
                select(Signal)
                .join(Round, Signal.round_id == Round.id)
                .where(
                    Round.market_id == market.id,
                    Round.round_number <= round_row.round_number,
                    Signal.delivered.is_(True),
                )
                .order_by(Round.round_number, Signal.id)
            ).all()
            benchmark = bayesian.benchmark_price(
                prior=0.5,
                all_signals=[(s.signal_value, float(s.theta)) for s in signal_rows],
            )
            round_row.closing_price = Decimal(str(closing_price))
            round_row.bayesian_benchmark = Decimal(str(benchmark))
            round_row.closed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(round_row)

        state.phase = SessionPhase.ROUND_CLOSED
        return round_row

    def resolve_market(self, session_id: int) -> MarketResolution:
        state = self._require_state(session_id)
        if state.phase not in {SessionPhase.ROUND_CLOSED, SessionPhase.MARKET_OPEN}:
            raise ValueError("Cannot resolve market from current phase")

        with self.db_session_factory() as db:
            market = self._current_market_row(db, session_id, state.current_market_number)
            if market is None:
                raise ValueError("No open market")

            # Use the same latent market truth that signal draws use so information quality
            # is about the resolved payout outcome rather than an independent variable.
            seed = hashlib.sha256(f"{session_id}:{market.id}:truth".encode("utf-8")).hexdigest()[:16]
            outcome = self._draw_market_truth(session_id, market.id, float(market.true_probability))
            resolution = MarketResolution(market_id=market.id, outcome=outcome, rng_seed=seed)
            db.add(resolution)

            role_rows = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
            for role in role_rows:
                payout = float(role.yes_held) if outcome == 1 else float(role.no_held)
                role.final_balance = Decimal(str(float(role.starting_balance) + payout))

            market.closed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(resolution)

        state.phase = SessionPhase.MARKET_RESOLVED
        state.current_round_number = None
        return resolution

    def close_session(self, session_id: int) -> list[TournamentRanking]:
        state = self._require_state(session_id)
        rankings = self.compute_tournament(session_id)
        with self.db_session_factory() as db:
            session_row = db.get(SessionModel, session_id)
            if session_row is None:
                raise ValueError("session not found")
            session_row.closed_at = datetime.now(timezone.utc)
            db.commit()
        state.phase = SessionPhase.SESSION_CLOSED
        return rankings

    def compute_tournament(self, session_id: int) -> list[TournamentRanking]:
        with self.db_session_factory() as db:
            existing = db.scalars(
                select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
            ).all()
            if existing:
                return existing

            stmt: Select[tuple[str, Decimal, int]] = (
                select(
                    MarketRole.participant_id,
                    func.sum(MarketRole.final_balance).label("total_tokens"),
                    func.count(MarketRole.market_id).label("markets_count"),
                )
                .join(Market, MarketRole.market_id == Market.id)
                .where(
                    Market.session_id == session_id,
                    MarketRole.final_balance.is_not(None),
                    Market.is_practice.is_(False),
                )
                .group_by(MarketRole.participant_id)
            )
            rows = db.execute(stmt).all()
            scored = [(pid, float(total), int(markets)) for pid, total, markets in rows if markets > 0]
            scored.sort(key=lambda x: x[1], reverse=True)

            rank = 1
            i = 0
            while i < len(scored):
                tied = [scored[i]]
                j = i + 1
                while j < len(scored) and abs(scored[j][1] - scored[i][1]) < 1e-9:
                    tied.append(scored[j])
                    j += 1

                if len(tied) > 1 and self.tournament_tie_break_mode == "random":
                    seed = hashlib.sha256(f"{session_id}:tiebreak:{rank}:{i}".encode("utf-8")).hexdigest()[:16]
                    rng = random.Random(seed)
                    rng.shuffle(tied)
                    db.add(
                        AdminAction(
                            session_id=session_id,
                            action_type="tournament_tiebreak_random",
                            reason=f"seed={seed};rank={rank};participants={','.join(pid for pid, _, _ in tied)}",
                        )
                    )
                    for offset, (pid, total, _) in enumerate(tied):
                        rank_for_participant = rank + offset
                        db.add(
                            TournamentRanking(
                                session_id=session_id,
                                participant_id=pid,
                                total_tokens=Decimal(str(total)),
                                rank=rank_for_participant,
                                prize_eur=Decimal(str(self._prize_for_rank(rank_for_participant))),
                            )
                        )
                    rank += len(tied)
                else:
                    # Default bible behavior: shared-prize at tied rank and skip subsequent ranks.
                    prize = self._prize_for_rank(rank)
                    for pid, total, _ in tied:
                        db.add(
                            TournamentRanking(
                                session_id=session_id,
                                participant_id=pid,
                                total_tokens=Decimal(str(total)),
                                rank=rank,
                                prize_eur=Decimal(str(prize)),
                            )
                        )
                    rank += len(tied)
                i = j

            db.commit()
            return db.scalars(
                select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
            ).all()

    @staticmethod
    def _prize_for_rank(rank: int) -> float:
        if rank == 1:
            return 5.0
        if rank == 2:
            return 3.0
        if rank == 3:
            return 2.0
        return 0.0

    def restore_from_db(self) -> None:
        with self.db_session_factory() as db:
            open_sessions = db.scalars(select(SessionModel).where(SessionModel.closed_at.is_(None))).all()
            for sess in open_sessions:
                state = SessionState(session_id=sess.id, phase=SessionPhase.SESSION_OPEN)
                current_market = db.scalars(
                    select(Market)
                    .where(Market.session_id == sess.id, Market.closed_at.is_(None))
                    .order_by(Market.market_number.desc())
                ).first()
                if current_market:
                    state.current_market_number = current_market.market_number
                    state.phase = SessionPhase.MARKET_OPEN
                    current_round = db.scalars(
                        select(Round)
                        .where(Round.market_id == current_market.id, Round.closed_at.is_(None))
                        .order_by(Round.round_number.desc())
                    ).first()
                    if current_round:
                        state.current_round_number = current_round.round_number
                        state.phase = SessionPhase.ROUND_OPEN
                self.sessions[sess.id] = state

    def close_practice_market(self, session_id: int) -> None:
        state = self._require_state(session_id)
        if state.current_market_number != self.PRACTICE_MARKET_NUMBER:
            raise ValueError("No active practice market")
        if state.phase not in {SessionPhase.MARKET_OPEN, SessionPhase.ROUND_CLOSED}:
            raise ValueError("Cannot close practice market from current phase")

        with self.db_session_factory() as db:
            market = self._current_market_row(db, session_id, state.current_market_number)
            if market is None or not bool(market.is_practice):
                raise ValueError("No active practice market")
            market.closed_at = datetime.now(timezone.utc)
            db.commit()

        state.phase = SessionPhase.SESSION_OPEN
        state.current_market_number = None
        state.current_round_number = None
        state.market_cache = {}

    @staticmethod
    def _draw_market_truth(session_id: int, market_id: int, true_probability: float) -> int:
        seed = hashlib.sha256(f"{session_id}:{market_id}:truth".encode("utf-8")).hexdigest()[:16]
        rng = random.Random(seed)
        return 1 if rng.random() < true_probability else 0

    @staticmethod
    def _current_market_row(db: Session, session_id: int, market_number: int | None) -> Market | None:
        if market_number is None:
            return None
        return db.scalars(
            select(Market).where(
                Market.session_id == session_id,
                Market.market_number == market_number,
            )
        ).first()

    @staticmethod
    def _current_round_row(db: Session, market_id: int, round_number: int | None) -> Round | None:
        if round_number is None:
            return None
        return db.scalars(
            select(Round).where(
                Round.market_id == market_id,
                Round.round_number == round_number,
            )
        ).first()
