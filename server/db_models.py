from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, PrimaryKeyConstraint, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_label: Mapped[str] = mapped_column(Text, nullable=False)
    rotation_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_order: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    lmsr_b_parameter: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("36"), server_default="36")
    treated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    show_tournament_payout_screen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    join_token: Mapped[str | None] = mapped_column(Text, unique=True)
    external_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ParticipantSession(Base):
    __tablename__ = "participant_sessions"

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), primary_key=True)
    join_token: Mapped[str | None] = mapped_column(Text, unique=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    flow_step: Mapped[str] = mapped_column(Text, nullable=False, default="consent", server_default="consent")


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (
        CheckConstraint(
            "(is_practice AND market_number = 0) OR ((NOT is_practice) AND market_number BETWEEN 1 AND 4)",
            name="ck_market_number",
        ),
        UniqueConstraint("session_id", "market_number", name="uq_session_market_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    market_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_practice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    scenario_id: Mapped[str] = mapped_column(String(1), nullable=False)
    true_probability: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    stage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    b_parameter: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    q_yes: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0")
    q_no: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketRole(Base):
    __tablename__ = "market_roles"
    __table_args__ = (
        PrimaryKeyConstraint("market_id", "participant_id", name="pk_market_role"),
        CheckConstraint("role_tier IN ('uninformed','informed')", name="ck_role_tier"),
    )

    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    role_tier: Mapped[str] = mapped_column(Text, nullable=False)
    endowment_tokens: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    starting_balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    final_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    yes_held: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0")
    no_held: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0"), server_default="0")


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (
        CheckConstraint("round_number BETWEEN 1 AND 5", name="ck_round_number"),
        UniqueConstraint("market_id", "round_number", name="uq_market_round"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), nullable=False)
    round_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_price: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    closing_price: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))
    bayesian_benchmark: Mapped[Decimal | None] = mapped_column(Numeric(7, 6))


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("signal_value IN ('S+','M+','N','M-','S-')", name="ck_signal_value"),
        UniqueConstraint("round_id", "participant_id", name="uq_signal_round_participant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), nullable=False)
    signal_value: Mapped[str] = mapped_column(String(1), nullable=False)
    theta: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    posterior: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rng_seed: Mapped[str | None] = mapped_column(Text)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (
        CheckConstraint("direction IN ('yes','no')", name="ck_trade_direction"),
        CheckConstraint("quantity > 0", name="ck_trade_quantity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    price_before: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    price_after: Mapped[Decimal] = mapped_column(Numeric(7, 6), nullable=False)
    q_yes_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    q_no_after: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


Index("trades_round_idx", Trade.round_id)
Index("trades_participant_idx", Trade.participant_id)


class MarketResolution(Base):
    __tablename__ = "market_resolutions"
    __table_args__ = (CheckConstraint("outcome IN (0,1)", name="ck_market_outcome"),)

    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="CASCADE"), primary_key=True)
    outcome: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rng_seed: Mapped[str | None] = mapped_column(Text)


class RiskElicitation(Base):
    __tablename__ = "risk_elicitations"
    __table_args__ = (PrimaryKeyConstraint("session_id", "participant_id", name="pk_risk_elicitation"),)

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    instrument: Mapped[str] = mapped_column(Text, nullable=False)
    switch_point: Mapped[int | None] = mapped_column(SmallInteger)
    raw_choices: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "participant_id", "quiz_name", name="pk_quiz_attempt"),
    )

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    quiz_name: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    final_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    raw_answers: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class DebriefResponse(Base):
    __tablename__ = "debrief_responses"
    __table_args__ = (PrimaryKeyConstraint("session_id", "participant_id", name="pk_debrief"),)

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    answers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TournamentRanking(Base):
    __tablename__ = "tournament_rankings"
    __table_args__ = (PrimaryKeyConstraint("session_id", "participant_id", name="pk_tournament"),)

    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    total_tokens: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    prize_eur: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"), server_default="0")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("tournament_rank_idx", TournamentRanking.session_id, TournamentRanking.rank)


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
