from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import socketio
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from server.config import load_settings
from server.db import SessionLocal, get_db, init_db
from server.db_models import AdminAction, DebriefResponse, Market, MarketResolution, MarketRole, ParticipantSession, QuizAttempt, RiskElicitation, Round, SessionModel, Signal, TournamentRanking, Trade
from server.events import (
    ErrorEvent,
    LastTradePayload,
    MarketOutcomePublicEvent,
    MarketResolvedEvent,
    MarketStartedEvent,
    PrimingBulletinPayload,
    PriceUpdateEvent,
    RoundEndedEvent,
    RoundStartedEvent,
    TradeRequest,
)
from server import lmsr
from server.portfolio import compute_market_avg_costs
from server.orchestrator import Orchestrator, SessionPhase
from server.scenarios import get_bulletin, get_priming_bulletin


settings = load_settings()
ROUND_DURATION_SECONDS = 90
PRACTICE_ROUND_DURATION_SECONDS = 45
PRACTICE_MARKET_NUMBER = Orchestrator.PRACTICE_MARKET_NUMBER
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("valdoria")

fastapi_app = FastAPI(title="Valdoria Prediction Market")
# Keep FastAPI CORS strict, but disable Engine.IO origin enforcement because
# proxy/TLS termination (e.g. Heroku) can produce mismatched Origin/Host checks
# and reject valid same-site websocket upgrades with 403.
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=[])
combined_app = socketio.ASGIApp(socketio_server=sio, other_asgi_app=fastapi_app)
security = HTTPBasic()
orchestrator = Orchestrator(
    SessionLocal,
    tournament_tie_break_mode=settings.tournament_tie_break_mode,
    lmsr_b_parameter=settings.lmsr_b_parameter,
)
init_db()
try:
    orchestrator.restore_from_db()
except OperationalError:
    logger.warning("Skipping state restore due to schema mismatch; run migrations to sync local DB.")
practice_auto_close_tasks: dict[int, asyncio.Task[None]] = {}
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client_dist = Path(__file__).resolve().parents[1] / "client" / "dist"

SPA_ROOT_ROUTES = (
    "/",
    "/consent",
    "/instructions",
    "/quiz",
    "/risk",
    "/lobby",
    "/trade",
    "/debrief",
    "/admin",
    "/abm-watch",
)

@fastapi_app.get("/app/")
async def serve_app_root():
    return FileResponse(client_dist / "index.html")

@fastapi_app.get("/app/{path:path}")
async def serve_app(path: str):
    file_path = client_dist / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(client_dist / "index.html")

async def serve_spa_root_routes():
    return FileResponse(client_dist / "index.html")


for _route in SPA_ROOT_ROUTES:
    fastapi_app.add_api_route(_route, serve_spa_root_routes, methods=["GET"], include_in_schema=False)


class JoinRequest(BaseModel):
    join_token: str


class CreateSessionRequest(BaseModel):
    label: str
    rotation_id: int = 1
    subject_count: int = Field(default=9, ge=1, le=20)
    treated_count: int = Field(default=3, ge=2, le=20)
    lmsr_b_parameter: float = Field(default=36.0, gt=0)
    show_tournament_payout_screen: bool = True


class StartMarketRequest(BaseModel):
    market_number: int = Field(ge=1, le=4)


class StartRoundRequest(BaseModel):
    round_number: int = Field(ge=1, le=5)


class TournamentMarkPaidRequest(BaseModel):
    participant_id: str


class EmergencyActionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class QuizSubmitRequest(BaseModel):
    attempts: int = Field(ge=1, le=20)
    final_correct: bool
    raw_answers: dict[str, Any]


class RiskSubmitRequest(BaseModel):
    instrument: str
    switch_point: int | None = Field(default=None, ge=1, le=10)
    raw_choices: dict[str, Any] | None = None


class DebriefSubmitRequest(BaseModel):
    answers: dict[str, Any]


class FlowStepUpdateRequest(BaseModel):
    flow_step: str
    metadata: dict[str, Any] | None = None


SCENARIO_DESCRIPTIONS = {
    "A": "Will Valdoria enter armed conflict within 12 months?",
    "B": "Will diplomacy stabilize relations before military escalation?",
    "C": "Baseline uncertainty scenario for Valdoria conflict outlook.",
    "D": "Combined information and endowment treatment scenario.",
}


def _is_practice_market(market: Market | None) -> bool:
    return bool(market is not None and market.is_practice)


def _round_duration_seconds_for_market(market: Market | None) -> int:
    if _is_practice_market(market):
        return PRACTICE_ROUND_DURATION_SECONDS
    return ROUND_DURATION_SECONDS


def _cancel_practice_auto_close_task(session_id: int) -> None:
    task = practice_auto_close_tasks.pop(session_id, None)
    if task is not None and not task.done():
        task.cancel()


def _expire_practice_round_if_needed(session_id: int) -> None:
    try:
        state = orchestrator._require_state(session_id)
    except ValueError:
        return
    if state.phase != SessionPhase.ROUND_OPEN or state.current_market_number != PRACTICE_MARKET_NUMBER:
        return

    with SessionLocal() as db:
        market = db.scalars(
            select(Market).where(
                Market.session_id == session_id,
                Market.market_number == PRACTICE_MARKET_NUMBER,
            )
        ).first()
        if market is None or not _is_practice_market(market):
            return
        if state.current_round_number is None:
            return
        round_row = db.scalars(
            select(Round).where(
                Round.market_id == market.id,
                Round.round_number == state.current_round_number,
            )
        ).first()
        if round_row is None or round_row.opened_at is None:
            return
        opened_at = round_row.opened_at
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        deadline = opened_at + timedelta(seconds=_round_duration_seconds_for_market(market))
        if datetime.now(timezone.utc) < deadline:
            return

    _cancel_practice_auto_close_task(session_id=session_id)
    try:
        orchestrator.end_round(session_id=session_id)
    except ValueError:
        return
    try:
        orchestrator.close_practice_market(session_id=session_id)
    except ValueError:
        return
    with SessionLocal() as db:
        participants = db.scalars(select(ParticipantSession).where(ParticipantSession.session_id == session_id)).all()
        for participant in participants:
            participant.flow_step = "lobby"
        db.commit()


def _admin_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if credentials.username != settings.admin_user or credentials.password != settings.admin_pass:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")
    return credentials.username


def _parse_auth_cookie(auth_cookie: str | None) -> tuple[int, str]:
    if not auth_cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        sid_s, participant_id = auth_cookie.split(":", 1)
        return int(sid_s), participant_id
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Malformed session cookie") from exc


def _room_all(session_id: int) -> str:
    return f"session:{session_id}:all"


def _room_participant(session_id: int, participant_id: str) -> str:
    return f"session:{session_id}:participant:{participant_id}"


def _set_flow_step(db: Session, session_id: int, participant_id: str, flow_step: str) -> None:
    row = db.get(ParticipantSession, {"session_id": session_id, "participant_id": participant_id})
    if row is not None:
        row.flow_step = flow_step
        db.add(row)


def _log_admin_action(db: Session, session_id: int, action_type: str, reason: str) -> None:
    db.add(
        AdminAction(
            session_id=session_id,
            action_type=action_type,
            reason=reason.strip(),
        )
    )
    db.commit()


def _resolve_outcome_label(outcome: int | None) -> str | None:
    if outcome is None:
        return None
    return "YES — Conflict occurred" if outcome == 1 else "NO — Conflict did not occur"


async def _emit_market_resolution(session_id: int, market_id: int, outcome: int, db: Session) -> None:
    market = db.get(Market, market_id)
    public_event = MarketOutcomePublicEvent(
        outcome=outcome,
        outcome_label=_resolve_outcome_label(outcome) or "NO — Conflict did not occur",
        true_probability=float(market.true_probability) if market else 0.5,
    )
    await sio.emit(
        "market_outcome_public",
        public_event.model_dump(),
        room=_room_all(session_id),
    )
    if market is None:
        return
    role_rows = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
    for role in role_rows:
        payout = float(role.yes_held) if outcome == 1 else float(role.no_held)
        final_balance = float(role.final_balance or role.starting_balance)
        pnl = final_balance - float(role.endowment_tokens)
        private_event = MarketResolvedEvent(
            outcome=outcome,
            outcome_label=_resolve_outcome_label(outcome) or "NO — Conflict did not occur",
            true_probability=float(market.true_probability),
            payout=payout,
            final_balance=final_balance,
            pnl=pnl,
        )
        await sio.emit(
            "market_resolved",
            private_event.model_dump(),
            room=_room_participant(session_id, role.participant_id),
        )


def _build_participant_state(db: Session, session_id: int, participant_id: str) -> dict[str, Any]:
    session_row = db.get(SessionModel, session_id)
    try:
        state = orchestrator._require_state(session_id)
        phase = state.phase.value
        current_market_number = state.current_market_number
        current_round_number = state.current_round_number
    except ValueError:
        phase = "session_closed" if session_row and session_row.closed_at else "idle"
        current_market_number = None
        current_round_number = None

    market = None
    round_row = None
    if current_market_number is not None:
        market = db.scalars(
            select(Market).where(
                Market.session_id == session_id,
                Market.market_number == current_market_number,
            )
        ).first()
    if market is not None and current_round_number is not None:
        round_row = db.scalars(
            select(Round).where(
                Round.market_id == market.id,
                Round.round_number == current_round_number,
            )
        ).first()

    role = None
    signal_value = None
    signal_theta = None
    if market is not None:
        role = db.get(MarketRole, {"market_id": market.id, "participant_id": participant_id})
    if round_row is not None:
        signal = db.scalars(
            select(Signal).where(Signal.round_id == round_row.id, Signal.participant_id == participant_id)
        ).first()
        if signal is not None and signal.delivered:
            signal_value = signal.signal_value
            signal_theta = float(signal.theta)

    yes_avg_cost = None
    no_avg_cost = None
    if market is not None:
        market_trades = db.scalars(
            select(Trade)
            .join(Round, Trade.round_id == Round.id)
            .where(
                Round.market_id == market.id,
                Trade.participant_id == participant_id,
            )
            .order_by(Trade.id.asc())
        ).all()
        yes_trades = [t for t in market_trades if t.direction == "yes"]
        no_trades = [t for t in market_trades if t.direction == "no"]
        yes_avg_cost, no_avg_cost = compute_market_avg_costs(yes_trades=yes_trades, no_trades=no_trades)

    flow = db.get(ParticipantSession, {"session_id": session_id, "participant_id": participant_id})
    bulletin = None
    if market is not None and round_row is not None and role is not None:
        bulletin = get_bulletin(
            scenario_id=market.scenario_id,
            round_number=round_row.round_number,
            role_tier=role.role_tier,
            stage=market.stage,
        )
    priming = None
    if market is not None and role is not None and not market.is_practice:
        priming = get_priming_bulletin(
            scenario_id=market.scenario_id,
            role_tier=role.role_tier,
            stage=market.stage,
            seed=f"{session_id}:{market.id}:priming",
        )
    round_duration_seconds = None
    is_practice_round = _is_practice_market(market) and round_row is not None
    round_deadline_unix_ms = None
    if (
        phase == SessionPhase.ROUND_OPEN.value
        and round_row is not None
        and round_row.opened_at is not None
    ):
        round_duration_seconds = _round_duration_seconds_for_market(market)
        opened_at = round_row.opened_at
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=timezone.utc)
        round_deadline_unix_ms = int((opened_at + timedelta(seconds=round_duration_seconds)).timestamp() * 1000)
    elif round_row is not None:
        round_duration_seconds = _round_duration_seconds_for_market(market)

    return {
        "session_id": session_id,
        "participant_id": participant_id,
        "flow_step": flow.flow_step if flow else None,
        "phase": phase,
        "show_tournament_payout_screen": session_row.show_tournament_payout_screen if session_row else True,
        "current_market_number": current_market_number,
        "current_round_number": current_round_number,
        "market_id": market.id if market else None,
        "round_id": round_row.id if round_row else None,
        "role_tier": role.role_tier if role else None,
        "balance": float(role.starting_balance) if role else None,
        "yes_held": float(role.yes_held) if role else None,
        "no_held": float(role.no_held) if role else None,
        "yes_avg_cost": yes_avg_cost,
        "no_avg_cost": no_avg_cost,
        "current_price": (
            lmsr.price(float(market.q_yes), float(market.q_no), float(market.b_parameter)) if market else 0.5
        ),
        "bulletin": bulletin,
        "signal_value": signal_value,
        "signal_theta": signal_theta,
        "is_practice_round": is_practice_round,
        "round_duration_seconds": round_duration_seconds,
        "round_deadline_unix_ms": round_deadline_unix_ms,
        "priming": priming,
    }


@fastapi_app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@fastapi_app.post("/auth/join")
def auth_join(payload: JoinRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    ps = db.scalars(select(ParticipantSession).where(ParticipantSession.join_token == payload.join_token)).first()
    if ps is None:
        raise HTTPException(status_code=404, detail="Participant not attached to session")

    session_id = ps.session_id
    participant_id = ps.participant_id

    cookie_value = f"{session_id}:{participant_id}"
    response.set_cookie(
        key="valdoria_auth",
        value=cookie_value,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=int(timedelta(hours=12).total_seconds()),
    )
    # One-time token use: reconnects should rely on cookie session.
    ps.join_token = None
    db.add(ps)
    db.commit()
    return {"session_id": session_id, "participant_id": participant_id, "flow_step": ps.flow_step}


@fastapi_app.post("/admin/sessions")
def create_session(payload: CreateSessionRequest, _: str = Depends(_admin_auth)) -> dict[str, int]:
    if payload.treated_count > payload.subject_count:
        raise HTTPException(status_code=422, detail="treated_count must be less than or equal to subject_count")
    session_id = orchestrator.start_session(
        label=payload.label,
        rotation_id=payload.rotation_id,
        subject_count=payload.subject_count,
        treated_count=payload.treated_count,
        lmsr_b_parameter=payload.lmsr_b_parameter,
        show_tournament_payout_screen=payload.show_tournament_payout_screen,
    )
    return {"session_id": session_id}


@fastapi_app.get("/admin/sessions")
def list_sessions(_: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(select(SessionModel).order_by(SessionModel.id.desc())).all()
    return [
        {
            "session_id": s.id,
            "label": s.session_label,
            "rotation_id": s.rotation_id,
            "treated_count": s.treated_count,
            "lmsr_b_parameter": float(s.lmsr_b_parameter),
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        }
        for s in rows
    ]


async def _emit_round_started_events(session_id: int, market: Market, round_row: Round, db: Session) -> None:
    role_rows = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
    signals_by_pid = {
        s.participant_id: s
        for s in db.scalars(select(Signal).where(Signal.round_id == round_row.id)).all()
    }
    duration_seconds = _round_duration_seconds_for_market(market)
    opened_at = round_row.opened_at or datetime.now(timezone.utc)
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    deadline_ms = int((opened_at + timedelta(seconds=duration_seconds)).timestamp() * 1000)

    for role in role_rows:
        participant_id = role.participant_id
        signal = signals_by_pid.get(participant_id)
        bulletin = get_bulletin(
            scenario_id=market.scenario_id,
            round_number=round_row.round_number,
            role_tier=role.role_tier,
            stage=market.stage,
        )
        signal_value = None
        signal_theta = None
        if signal is not None and signal.delivered:
            signal_value = signal.signal_value
            signal_theta = float(signal.theta)

        participant_trades = db.scalars(
            select(Trade)
            .join(Round, Trade.round_id == Round.id)
            .where(
                Round.market_id == market.id,
                Trade.participant_id == participant_id,
            )
            .order_by(Trade.id.asc())
        ).all()
        yes_trades = [t for t in participant_trades if t.direction == "yes"]
        no_trades = [t for t in participant_trades if t.direction == "no"]
        yes_avg_cost, no_avg_cost = compute_market_avg_costs(yes_trades=yes_trades, no_trades=no_trades)

        event = RoundStartedEvent(
            round_number=round_row.round_number,
            is_practice_round=_is_practice_market(market),
            round_duration_seconds=duration_seconds,
            trading_open=True,
            current_price=float(round_row.opening_price or 0.5),
            balance=float(role.starting_balance),
            yes_held=float(role.yes_held),
            no_held=float(role.no_held),
            yes_avg_cost=yes_avg_cost,
            no_avg_cost=no_avg_cost,
            bulletin=bulletin,
            signal_value=signal_value,
            signal_theta=signal_theta,
            round_deadline_unix_ms=deadline_ms,
        )
        await sio.emit("round_started", event.model_dump(), room=_room_participant(session_id, participant_id))


@fastapi_app.post("/admin/sessions/{session_id}/markets")
async def start_market(session_id: int, payload: StartMarketRequest, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    market = orchestrator.start_market(session_id=session_id, market_number=payload.market_number)
    roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
    for role in roles:
        _set_flow_step(db, session_id, role.participant_id, f"market-{market.market_number}")
        event = MarketStartedEvent(
            market_number=market.market_number,
            is_practice=False,
            stage=market.stage,
            scenario_description=SCENARIO_DESCRIPTIONS.get(market.scenario_id, "Valdoria market scenario"),
            role_tier=role.role_tier,
            endowment_tokens=float(role.endowment_tokens),
            starting_balance=float(role.starting_balance),
            current_price=0.5,
            max_rounds=5,
            priming=None,
        )
        await sio.emit(
            "market_started",
            event.model_dump(),
            room=_room_participant(session_id, role.participant_id),
        )
    db.commit()
    return {"market_id": market.id, "market_number": market.market_number, "stage": market.stage}


@fastapi_app.post("/admin/sessions/{session_id}/markets/{market_number}/priming")
async def send_priming_bulletin(session_id: int, market_number: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    market = db.scalar(
        select(Market).where(Market.session_id == session_id, Market.market_number == market_number)
    )
    if market is None or market.is_practice:
        raise HTTPException(status_code=404, detail="Market not found")
    roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
    priming_seed = f"{session_id}:{market.id}:priming"
    sent = 0
    for role in roles:
        priming_dict = get_priming_bulletin(
            scenario_id=market.scenario_id,
            role_tier=role.role_tier,
            stage=market.stage,
            seed=priming_seed,
        )
        payload = PrimingBulletinPayload(**priming_dict)
        await sio.emit(
            "priming_bulletin",
            payload.model_dump(),
            room=_room_participant(session_id, role.participant_id),
        )
        sent += 1
    return {"sent": sent}


async def _finalize_practice_after_round_close(session_id: int) -> None:
    with SessionLocal() as db:
        state = orchestrator._require_state(session_id)
        market = None
        if state.current_market_number is not None:
            market = db.scalars(
                select(Market).where(
                    Market.session_id == session_id,
                    Market.market_number == state.current_market_number,
                )
            ).first()
        if market is None or not _is_practice_market(market):
            return
        orchestrator.close_practice_market(session_id=session_id)
        participants = db.scalars(select(ParticipantSession).where(ParticipantSession.session_id == session_id)).all()
        for participant in participants:
            participant.flow_step = "lobby"
        db.commit()


async def _auto_close_practice_round(session_id: int, round_number: int, delay_seconds: int) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        state = orchestrator._require_state(session_id)
        if state.phase != SessionPhase.ROUND_OPEN:
            return
        if state.current_round_number != round_number:
            return

        round_row = orchestrator.end_round(session_id=session_id)
        with SessionLocal() as db:
            market = db.get(Market, round_row.market_id)
            if market is None or not _is_practice_market(market):
                return
            round_volume = int(
                db.scalar(
                    select(func.coalesce(func.sum(Trade.quantity), 0)).where(Trade.round_id == round_row.id)
                )
                or 0
            )
        event = RoundEndedEvent(
            round_number=round_row.round_number,
            closing_price=float(round_row.closing_price or 0.5),
            round_volume=round_volume,
        )
        await sio.emit("round_ended", event.model_dump(), room=_room_all(session_id))
        await _finalize_practice_after_round_close(session_id=session_id)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("practice auto-close failed for session=%s", session_id)
    finally:
        practice_auto_close_tasks.pop(session_id, None)


@fastapi_app.post("/admin/sessions/{session_id}/practice_round")
async def start_practice_round(session_id: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        state = orchestrator._require_state(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if state.phase != SessionPhase.SESSION_OPEN:
        raise HTTPException(status_code=400, detail="Cannot start practice round outside session_open phase")

    try:
        market = orchestrator.start_market(session_id=session_id, market_number=PRACTICE_MARKET_NUMBER, is_practice=True)
        round_row = orchestrator.start_round(session_id=session_id, round_number=1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
    for role in roles:
        _set_flow_step(db, session_id, role.participant_id, "market-practice")
        event = MarketStartedEvent(
            market_number=market.market_number,
            is_practice=True,
            stage=market.stage,
            scenario_description="Practice round: familiarize with live trading mechanics.",
            role_tier=role.role_tier,
            endowment_tokens=float(role.endowment_tokens),
            starting_balance=float(role.starting_balance),
            current_price=0.5,
            max_rounds=1,
        )
        await sio.emit(
            "market_started",
            event.model_dump(),
            room=_room_participant(session_id, role.participant_id),
        )
    db.commit()
    await _emit_round_started_events(session_id=session_id, market=market, round_row=round_row, db=db)

    _cancel_practice_auto_close_task(session_id=session_id)
    practice_auto_close_tasks[session_id] = asyncio.create_task(
        _auto_close_practice_round(
            session_id=session_id,
            round_number=round_row.round_number,
            delay_seconds=PRACTICE_ROUND_DURATION_SECONDS,
        )
    )
    return {
        "market_id": market.id,
        "market_number": market.market_number,
        "round_id": round_row.id,
        "round_number": round_row.round_number,
        "is_practice": True,
        "duration_seconds": PRACTICE_ROUND_DURATION_SECONDS,
    }


@fastapi_app.post("/admin/sessions/{session_id}/rounds")
async def start_round(session_id: int, payload: StartRoundRequest, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        round_row = orchestrator.start_round(session_id=session_id, round_number=payload.round_number)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    market = db.get(Market, round_row.market_id)
    if market is None:
        raise HTTPException(status_code=500, detail="market missing")
    if _is_practice_market(market):
        raise HTTPException(status_code=400, detail="Use /practice_round to run the practice market")
    await _emit_round_started_events(session_id=session_id, market=market, round_row=round_row, db=db)
    return {"round_id": round_row.id, "round_number": round_row.round_number}


@fastapi_app.post("/admin/sessions/{session_id}/rounds/{round_number}/end")
async def end_round(session_id: int, round_number: int, _: str = Depends(_admin_auth)) -> dict[str, Any]:
    state = orchestrator._require_state(session_id)
    if state.current_round_number != round_number:
        raise HTTPException(status_code=400, detail="round mismatch")
    round_row = orchestrator.end_round(session_id=session_id)
    with SessionLocal() as db:
        market = db.get(Market, round_row.market_id)
        is_practice = _is_practice_market(market)
    with SessionLocal() as db:
        round_volume = int(
            db.scalar(
                select(func.coalesce(func.sum(Trade.quantity), 0)).where(Trade.round_id == round_row.id)
            )
            or 0
        )

    event = RoundEndedEvent(
        round_number=round_row.round_number,
        closing_price=float(round_row.closing_price or 0.5),
        round_volume=round_volume,
    )
    await sio.emit("round_ended", event.model_dump(), room=_room_all(session_id))
    if is_practice:
        _cancel_practice_auto_close_task(session_id=session_id)
        await _finalize_practice_after_round_close(session_id=session_id)
    return {
        "round_id": round_row.id,
        "closing_price": float(round_row.closing_price or 0.5),
        "benchmark": float(round_row.bayesian_benchmark or 0.5),
        "round_volume": round_volume,
    }


@fastapi_app.post("/admin/sessions/{session_id}/markets/{market_number}/resolve")
async def resolve_market(session_id: int, market_number: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    state = orchestrator._require_state(session_id)
    if state.current_market_number != market_number:
        raise HTTPException(status_code=400, detail="market mismatch")
    market = db.scalars(
        select(Market).where(
            Market.session_id == session_id,
            Market.market_number == market_number,
        )
    ).first()
    if market is not None and _is_practice_market(market):
        raise HTTPException(status_code=400, detail="Practice market cannot be resolved")
    resolution = orchestrator.resolve_market(session_id=session_id)
    await _emit_market_resolution(session_id=session_id, market_id=resolution.market_id, outcome=resolution.outcome, db=db)
    return {"outcome": resolution.outcome}


@fastapi_app.post("/admin/sessions/{session_id}/close")
async def close_session(session_id: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    _cancel_practice_auto_close_task(session_id=session_id)
    rankings = orchestrator.close_session(session_id=session_id)
    participants = db.scalars(select(ParticipantSession).where(ParticipantSession.session_id == session_id)).all()
    for p in participants:
        p.flow_step = "debrief"
    db.commit()
    await sio.emit("session_closed", {"session_id": session_id}, room=_room_all(session_id))
    return [
        {
            "participant_id": r.participant_id,
            "rank": r.rank,
            "total_tokens": float(r.total_tokens),
            "prize_eur": float(r.prize_eur),
        }
        for r in rankings
    ]


@fastapi_app.get("/admin/sessions/{session_id}/tournament")
def get_tournament(session_id: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
    ).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Tournament unavailable")
    return [
        {
            "participant_id": r.participant_id,
            "rank": r.rank,
            "total_tokens": float(r.total_tokens),
            "prize_eur": float(r.prize_eur),
            "paid_at": r.paid_at.isoformat() if r.paid_at else None,
        }
        for r in rows
    ]


@fastapi_app.get("/admin/sessions/{session_id}/tournament/provisional")
def get_tournament_provisional(session_id: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            MarketRole.participant_id,
            func.coalesce(func.sum(MarketRole.final_balance), 0),
            func.count(MarketRole.final_balance),
        )
        .join(Market, MarketRole.market_id == Market.id)
        .where(Market.session_id == session_id, Market.is_practice.is_(False))
        .group_by(MarketRole.participant_id)
    ).all()
    ranked = sorted(
        [
            {
                "participant_id": pid,
                "total_tokens": float(total or 0),
                "markets_completed": int(completed or 0),
            }
            for pid, total, completed in rows
        ],
        key=lambda x: x["total_tokens"],
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for i, row in enumerate(ranked, start=1):
        out.append(
            {
                "participant_id": row["participant_id"],
                "rank": i,
                "total_tokens": row["total_tokens"],
                "markets_completed": row["markets_completed"],
                "provisional": True,
            }
        )
    return out


@fastapi_app.post("/admin/sessions/{session_id}/tournament/mark_paid")
def mark_paid(session_id: int, payload: TournamentMarkPaidRequest, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.get(TournamentRanking, {"session_id": session_id, "participant_id": payload.participant_id})
    if row is None:
        raise HTTPException(status_code=404, detail="Ranking row not found")
    row.paid_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@fastapi_app.get("/admin/sessions/{session_id}/participants")
def list_session_participants(session_id: int, _: str = Depends(_admin_auth), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(ParticipantSession).where(ParticipantSession.session_id == session_id).order_by(ParticipantSession.participant_id)
    ).all()
    role_rows = db.execute(
        select(
            MarketRole.participant_id,
            Market.market_number,
            MarketRole.role_tier,
            MarketRole.endowment_tokens,
        )
        .join(Market, MarketRole.market_id == Market.id)
        .where(Market.session_id == session_id, Market.is_practice.is_(False))
    ).all()

    treatment_by_participant: dict[str, dict[int, dict[str, Any]]] = {}
    for participant_id, market_number, role_tier, endowment_tokens in role_rows:
        endowment_value = float(endowment_tokens)
        information_treated = role_tier != "uninformed"
        endowment_treated = endowment_value > 100
        treatment_by_participant.setdefault(participant_id, {})[int(market_number)] = {
            "role_tier": role_tier,
            "endowment_tokens": endowment_value,
            "information_treated": information_treated,
            "endowment_treated": endowment_treated,
            "treated": information_treated or endowment_treated,
        }

    return [
        {
            "participant_id": r.participant_id,
            "flow_step": r.flow_step,
            "joined_at": r.joined_at.isoformat(),
            "markets": treatment_by_participant.get(r.participant_id, {}),
        }
        for r in rows
    ]


@fastapi_app.get("/admin/sessions/{session_id}/dashboard")
def session_dashboard(
    session_id: int,
    include_practice: bool = False,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    session_row = db.get(SessionModel, session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")

    phase = "idle"
    current_market_number = None
    current_round_number = None
    if session_id in orchestrator.sessions:
        state = orchestrator.sessions[session_id]
        phase = state.phase.value
        current_market_number = state.current_market_number
        current_round_number = state.current_round_number
    elif session_row.closed_at is not None:
        phase = "session_closed"

    practice_round_active = current_market_number == PRACTICE_MARKET_NUMBER and phase in {
        SessionPhase.MARKET_OPEN.value,
        SessionPhase.ROUND_OPEN.value,
        SessionPhase.ROUND_CLOSED.value,
    }
    if practice_round_active and not include_practice:
        current_market_number = None
        current_round_number = None

    markets_query = select(Market).where(Market.session_id == session_id)
    if not include_practice:
        markets_query = markets_query.where(Market.is_practice.is_(False))
    markets = db.scalars(markets_query.order_by(Market.market_number)).all()

    rounds_query = select(Round).join(Market, Round.market_id == Market.id).where(Market.session_id == session_id)
    volume_query = (
        select(Round.id, func.coalesce(func.sum(Trade.quantity), 0))
        .join(Market, Round.market_id == Market.id)
        .outerjoin(Trade, Trade.round_id == Round.id)
        .where(Market.session_id == session_id)
    )
    if not include_practice:
        rounds_query = rounds_query.where(Market.is_practice.is_(False))
        volume_query = volume_query.where(Market.is_practice.is_(False))
    rounds = db.scalars(rounds_query.order_by(Round.id)).all()
    volume_rows = db.execute(volume_query.group_by(Round.id)).all()
    volume_by_round = {rid: int(vol) for rid, vol in volume_rows}

    rounds_by_market: dict[int, list[Round]] = {}
    for r in rounds:
        rounds_by_market.setdefault(r.market_id, []).append(r)

    market_cards: list[dict[str, Any]] = []
    for m in markets:
        market_rounds = rounds_by_market.get(m.id, [])
        latest_round = market_rounds[-1] if market_rounds else None
        resolution = db.get(MarketResolution, m.id)
        market_cards.append(
            {
                "market_id": m.id,
                "market_number": m.market_number,
                "is_practice": bool(m.is_practice),
                "stage": m.stage,
                "scenario_id": m.scenario_id,
                "current_price": lmsr.price(float(m.q_yes), float(m.q_no), float(m.b_parameter)),
                "total_volume": sum(volume_by_round.get(r.id, 0) for r in market_rounds),
                "rounds_opened": len(market_rounds),
                "latest_round_number": latest_round.round_number if latest_round else None,
                "latest_closing_price": (
                    float(latest_round.closing_price) if latest_round and latest_round.closing_price is not None else None
                ),
                "latest_benchmark": (
                    float(latest_round.bayesian_benchmark)
                    if latest_round and latest_round.bayesian_benchmark is not None
                    else None
                ),
                "outcome": resolution.outcome if resolution else None,
                "outcome_label": _resolve_outcome_label(resolution.outcome) if resolution else None,
            }
        )

    participants = db.scalars(
        select(ParticipantSession).where(ParticipantSession.session_id == session_id)
    ).all()
    return {
        "session_id": session_id,
        "label": session_row.session_label,
        "phase": phase,
        "current_market_number": current_market_number,
        "current_round_number": current_round_number,
        "practice_round_active": practice_round_active,
        "participant_count": len(participants),
        "markets": market_cards,
    }


@fastapi_app.post("/admin/sessions/{session_id}/participants/{participant_id}/flow")
def override_flow_step(
    session_id: int,
    participant_id: str,
    payload: dict[str, str],
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    flow_step = payload.get("flow_step")
    if not flow_step:
        raise HTTPException(status_code=400, detail="flow_step is required")
    row = db.get(ParticipantSession, {"session_id": session_id, "participant_id": participant_id})
    if row is None:
        raise HTTPException(status_code=404, detail="participant not found in session")
    row.flow_step = flow_step
    db.commit()
    return {"ok": True}


@fastapi_app.post("/admin/sessions/{session_id}/emergency/round_close")
async def emergency_round_close(
    session_id: int,
    payload: EmergencyActionRequest,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    state = orchestrator._require_state(session_id)
    if state.phase != SessionPhase.ROUND_OPEN:
        raise HTTPException(status_code=400, detail="No open round to force-close")
    round_row = orchestrator.end_round(session_id=session_id)
    market = db.get(Market, round_row.market_id)
    is_practice = _is_practice_market(market)
    round_volume = int(
        db.scalar(
            select(func.coalesce(func.sum(Trade.quantity), 0)).where(Trade.round_id == round_row.id)
        )
        or 0
    )
    event = RoundEndedEvent(
        round_number=round_row.round_number,
        closing_price=float(round_row.closing_price or 0.5),
        round_volume=round_volume,
    )
    await sio.emit("round_ended", event.model_dump(), room=_room_all(session_id))
    if is_practice:
        _cancel_practice_auto_close_task(session_id=session_id)
        await _finalize_practice_after_round_close(session_id=session_id)
    _log_admin_action(db, session_id, "emergency_round_close", payload.reason)
    return {
        "ok": True,
        "forced": True,
        "round_number": round_row.round_number,
        "round_volume": round_volume,
    }


@fastapi_app.post("/admin/sessions/{session_id}/emergency/market_resolve")
async def emergency_market_resolve(
    session_id: int,
    payload: EmergencyActionRequest,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    state = orchestrator._require_state(session_id)
    if state.current_market_number is None:
        raise HTTPException(status_code=400, detail="No active market to force-resolve")
    market = db.scalars(
        select(Market).where(
            Market.session_id == session_id,
            Market.market_number == state.current_market_number,
        )
    ).first()
    if market is not None and _is_practice_market(market):
        raise HTTPException(status_code=400, detail="Practice market cannot be resolved")
    resolution = orchestrator.resolve_market(session_id=session_id)
    await _emit_market_resolution(session_id=session_id, market_id=resolution.market_id, outcome=resolution.outcome, db=db)
    _log_admin_action(db, session_id, "emergency_market_resolve", payload.reason)
    return {"ok": True, "forced": True, "outcome": resolution.outcome}


@fastapi_app.post("/admin/sessions/{session_id}/emergency/session_close")
async def emergency_session_close(
    session_id: int,
    payload: EmergencyActionRequest,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _cancel_practice_auto_close_task(session_id=session_id)
    rankings = orchestrator.close_session(session_id=session_id)
    participants = db.scalars(select(ParticipantSession).where(ParticipantSession.session_id == session_id)).all()
    for p in participants:
        p.flow_step = "debrief"
    db.commit()
    _log_admin_action(db, session_id, "emergency_session_close", payload.reason)
    await sio.emit("session_closed", {"session_id": session_id}, room=_room_all(session_id))
    return {"ok": True, "forced": True, "rankings": len(rankings)}


@fastapi_app.get("/abm/watch/run")
async def abm_watch_run(
    seed: int = 42,
    subject_count: int = 9,
    profile_mix: str = "rational:5,herder:2,noise:2",
    b: float = 36.0,
    market_number: int = 1,
) -> JSONResponse:
    from calibration.abm.watch import run_single_market
    loop = asyncio.get_event_loop()
    payload = await loop.run_in_executor(None, lambda: run_single_market(
        seed=seed,
        market_number=market_number,
        subject_count=subject_count,
        profile_mix=profile_mix,
        b=b,
    ))
    return JSONResponse(content=payload)


@fastapi_app.get("/admin/sessions/{session_id}/export.csv")
def export_session_csv(
    session_id: int,
    include_practice: bool = False,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    trade_query = select(Trade).join(Round, Trade.round_id == Round.id).join(Market, Round.market_id == Market.id).where(Market.session_id == session_id)
    if not include_practice:
        trade_query = trade_query.where(Market.is_practice.is_(False))
    trades = db.scalars(
        trade_query
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "trade_id",
            "round_id",
            "participant_id",
            "direction",
            "quantity",
            "cost",
            "price_before",
            "price_after",
            "q_yes_after",
            "q_no_after",
            "executed_at",
        ]
    )
    for t in trades:
        writer.writerow(
            [
                t.id,
                t.round_id,
                t.participant_id,
                t.direction,
                t.quantity,
                float(t.cost),
                float(t.price_before),
                float(t.price_after),
                float(t.q_yes_after),
                float(t.q_no_after),
                t.executed_at.isoformat(),
            ]
        )
    return PlainTextResponse(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=session-{session_id}-trades.csv"},
    )


@fastapi_app.get("/admin/sessions/{session_id}/export.json")
def export_session_json(
    session_id: int,
    include_practice: bool = False,
    _: str = Depends(_admin_auth),
    db: Session = Depends(get_db),
) -> JSONResponse:
    session_row = db.get(SessionModel, session_id)
    if session_row is None:
        raise HTTPException(status_code=404, detail="session not found")

    markets_query = select(Market).where(Market.session_id == session_id)
    rounds_query = select(Round).join(Market, Round.market_id == Market.id).where(Market.session_id == session_id)
    trades_query = select(Trade).join(Round, Trade.round_id == Round.id).join(Market, Round.market_id == Market.id).where(Market.session_id == session_id)
    signals_query = select(Signal).join(Round, Signal.round_id == Round.id).join(Market, Round.market_id == Market.id).where(Market.session_id == session_id)
    if not include_practice:
        markets_query = markets_query.where(Market.is_practice.is_(False))
        rounds_query = rounds_query.where(Market.is_practice.is_(False))
        trades_query = trades_query.where(Market.is_practice.is_(False))
        signals_query = signals_query.where(Market.is_practice.is_(False))

    markets = db.scalars(markets_query.order_by(Market.market_number)).all()
    rounds = db.scalars(rounds_query.order_by(Round.id)).all()
    trades = db.scalars(trades_query.order_by(Trade.id)).all()
    signals = db.scalars(signals_query.order_by(Signal.id)).all()
    rankings = db.scalars(
        select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
    ).all()

    payload = {
        "session": {
            "id": session_row.id,
            "label": session_row.session_label,
            "rotation_id": session_row.rotation_id,
            "treated_count": session_row.treated_count,
            "lmsr_b_parameter": float(session_row.lmsr_b_parameter),
            "scenario_order": session_row.scenario_order,
            "created_at": session_row.created_at.isoformat(),
            "closed_at": session_row.closed_at.isoformat() if session_row.closed_at else None,
        },
        "markets": [
            {
                "id": m.id,
                "market_number": m.market_number,
                "is_practice": bool(m.is_practice),
                "scenario_id": m.scenario_id,
                "true_probability": float(m.true_probability),
                "stage": m.stage,
                "b_parameter": float(m.b_parameter),
                "q_yes": float(m.q_yes),
                "q_no": float(m.q_no),
                "opened_at": m.opened_at.isoformat() if m.opened_at else None,
                "closed_at": m.closed_at.isoformat() if m.closed_at else None,
            }
            for m in markets
        ],
        "rounds": [
            {
                "id": r.id,
                "market_id": r.market_id,
                "round_number": r.round_number,
                "opening_price": float(r.opening_price) if r.opening_price is not None else None,
                "closing_price": float(r.closing_price) if r.closing_price is not None else None,
                "bayesian_benchmark": float(r.bayesian_benchmark) if r.bayesian_benchmark is not None else None,
                "opened_at": r.opened_at.isoformat() if r.opened_at else None,
                "closed_at": r.closed_at.isoformat() if r.closed_at else None,
            }
            for r in rounds
        ],
        "trades": [
            {
                "id": t.id,
                "round_id": t.round_id,
                "participant_id": t.participant_id,
                "direction": t.direction,
                "quantity": t.quantity,
                "cost": float(t.cost),
                "price_before": float(t.price_before),
                "price_after": float(t.price_after),
                "q_yes_after": float(t.q_yes_after),
                "q_no_after": float(t.q_no_after),
                "executed_at": t.executed_at.isoformat(),
            }
            for t in trades
        ],
        "signals": [
            {
                "id": s.id,
                "round_id": s.round_id,
                "participant_id": s.participant_id,
                "signal_value": s.signal_value,
                "theta": float(s.theta),
                "posterior": float(s.posterior),
                "delivered": s.delivered,
                "delivered_at": s.delivered_at.isoformat(),
                "rng_seed": s.rng_seed,
            }
            for s in signals
        ],
        "tournament": [
            {
                "participant_id": r.participant_id,
                "rank": r.rank,
                "total_tokens": float(r.total_tokens),
                "prize_eur": float(r.prize_eur),
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
            }
            for r in rankings
        ],
    }
    return JSONResponse(content=payload)


@fastapi_app.post("/trade")
async def trade(payload: TradeRequest, valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    _expire_practice_round_if_needed(session_id=session_id)
    try:
        result = orchestrator.record_trade(session_id=session_id, participant_id=participant_id, trade=payload)
    except ValueError as exc:
        code = str(exc)
        message = "Trade rejected"
        if code == "INSUFFICIENT_FUNDS":
            message = "Insufficient balance for this trade."
        if code == "SHORT_SELL_NOT_ALLOWED":
            message = "Short selling is not allowed."
        if code == "ROUND_CLOSED":
            message = "Trading is currently closed."
        await sio.emit("error", ErrorEvent(code=code, message=message).model_dump(), room=_room_participant(session_id, participant_id))
        raise HTTPException(status_code=400, detail=code) from exc

    hashed_pid = hashlib.sha256(participant_id.encode("utf-8")).hexdigest()[:8]
    event = PriceUpdateEvent(
        current_price=result.price_after,
        q_yes=result.q_yes_after,
        q_no=result.q_no_after,
        last_trade=LastTradePayload(
            participant_id_hashed=hashed_pid,
            direction=payload.direction,
            quantity=payload.quantity,
            price_before=result.price_before,
            price_after=result.price_after,
        ),
    )
    await sio.emit("price_update", event.model_dump(), room=_room_all(session_id))
    return {
        "trade_id": result.trade_id,
        "cost": result.cost,
        "price_after": result.price_after,
        "balance_after": result.balance_after,
        "yes_held": result.yes_held,
        "no_held": result.no_held,
    }


@fastapi_app.get("/state")
def get_state(valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    _expire_practice_round_if_needed(session_id=session_id)
    return _build_participant_state(db=db, session_id=session_id, participant_id=participant_id)


@fastapi_app.post("/quiz/{quiz_name}/submit")
def submit_quiz(quiz_name: str, payload: QuizSubmitRequest, valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    row = db.get(
        QuizAttempt,
        {
            "session_id": session_id,
            "participant_id": participant_id,
            "quiz_name": quiz_name,
        },
    )
    if row is None:
        row = QuizAttempt(
            session_id=session_id,
            participant_id=participant_id,
            quiz_name=quiz_name,
            attempts=payload.attempts,
            final_correct=payload.final_correct,
            raw_answers=payload.raw_answers,
        )
    else:
        row.attempts = payload.attempts
        row.final_correct = payload.final_correct
        row.raw_answers = payload.raw_answers
    db.add(row)
    if payload.final_correct:
        _set_flow_step(db, session_id, participant_id, "risk")
    db.commit()
    return {"ok": True, "final_correct": payload.final_correct}


@fastapi_app.post("/risk_elicitation/submit")
def submit_risk(payload: RiskSubmitRequest, valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    row = db.get(RiskElicitation, {"session_id": session_id, "participant_id": participant_id})
    if row is None:
        row = RiskElicitation(
            session_id=session_id,
            participant_id=participant_id,
            instrument=payload.instrument,
            switch_point=payload.switch_point,
            raw_choices=payload.raw_choices,
        )
    else:
        row.instrument = payload.instrument
        row.switch_point = payload.switch_point
        row.raw_choices = payload.raw_choices
    db.add(row)
    _set_flow_step(db, session_id, participant_id, "lobby")
    db.commit()
    return {"ok": True}


@fastapi_app.post("/debrief/submit")
def submit_debrief(payload: DebriefSubmitRequest, valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    row = db.get(DebriefResponse, {"session_id": session_id, "participant_id": participant_id})
    if row is None:
        row = DebriefResponse(
            session_id=session_id,
            participant_id=participant_id,
            answers=payload.answers,
        )
    else:
        row.answers = payload.answers
    db.add(row)
    _set_flow_step(db, session_id, participant_id, "complete")
    db.commit()
    return {"ok": True}


@fastapi_app.post("/flow_step")
def update_flow_step(payload: FlowStepUpdateRequest, valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    row = db.get(ParticipantSession, {"session_id": session_id, "participant_id": participant_id})
    if row is None:
        raise HTTPException(status_code=404, detail="participant session not found")
    row.flow_step = payload.flow_step
    if payload.metadata:
        debrief = db.get(DebriefResponse, {"session_id": session_id, "participant_id": participant_id})
        answers: dict[str, Any] = {}
        if debrief is not None and isinstance(debrief.answers, dict):
            answers = dict(debrief.answers)
        if payload.metadata.get("consented") is not None:
            answers["consent"] = payload.metadata
        if answers:
            if debrief is None:
                debrief = DebriefResponse(session_id=session_id, participant_id=participant_id, answers=answers)
            else:
                debrief.answers = answers
            db.add(debrief)
    db.commit()
    return {"ok": True}


@fastapi_app.get("/tournament/final")
def tournament_final(valdoria_auth: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> dict[str, Any]:
    session_id, participant_id = _parse_auth_cookie(valdoria_auth)
    ranking = db.get(TournamentRanking, {"session_id": session_id, "participant_id": participant_id})
    if ranking is None:
        raise HTTPException(status_code=404, detail="Tournament results not available")
    return {
        "participant_id": ranking.participant_id,
        "rank": ranking.rank,
        "prize_eur": float(ranking.prize_eur),
        "total_tokens": float(ranking.total_tokens),
    }


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: Any) -> bool:
    origin = environ.get("HTTP_ORIGIN")
    host = environ.get("HTTP_HOST")
    forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO")
    query_string = environ.get("QUERY_STRING")
    cookie_header = environ.get("HTTP_COOKIE", "")
    cookie_map: dict[str, str] = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            key, value = part.strip().split("=", 1)
            cookie_map[key] = value
    cookie_value = cookie_map.get("valdoria_auth")
    logger.info(
        "Socket connect attempt sid=%s origin=%s host=%s x_forwarded_proto=%s has_auth_cookie=%s query=%s",
        sid,
        origin,
        host,
        forwarded_proto,
        bool(cookie_value),
        query_string,
    )
    try:
        session_id, participant_id = _parse_auth_cookie(cookie_value)
    except HTTPException:
        logger.warning(
            "Socket connect rejected sid=%s reason=invalid_or_missing_cookie origin=%s host=%s x_forwarded_proto=%s",
            sid,
            origin,
            host,
            forwarded_proto,
        )
        return False

    await sio.save_session(sid, {"session_id": session_id, "participant_id": participant_id})
    await sio.enter_room(sid, _room_all(session_id))
    await sio.enter_room(sid, _room_participant(session_id, participant_id))
    _expire_practice_round_if_needed(session_id=session_id)
    with SessionLocal() as db:
        state_payload = _build_participant_state(db=db, session_id=session_id, participant_id=participant_id)
    await sio.emit("state_sync", state_payload, room=sid)
    logger.info("Socket connect accepted sid=%s session_id=%s participant_id=%s", sid, session_id, participant_id)
    return True


@sio.event
async def disconnect(sid: str) -> None:
    logger.info("Socket disconnected: %s", sid)
