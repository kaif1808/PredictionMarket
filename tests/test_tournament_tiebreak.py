from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from server.db import SessionLocal
from server.db_models import AdminAction, MarketRole, TournamentRanking
from server.orchestrator import Orchestrator


def _seed_tie_session(tie_break_mode: str) -> int:
    orchestrator = Orchestrator(SessionLocal, tournament_tie_break_mode=tie_break_mode)
    session_id = orchestrator.start_session(label=f"tie-{tie_break_mode}", rotation_id=1, subject_count=8)
    market = orchestrator.start_market(session_id, 1)
    with SessionLocal() as db:
        roles = db.scalars(select(MarketRole).where(MarketRole.market_id == market.id)).all()
        for role in roles:
            if role.participant_id in {"P01", "P02"}:
                role.final_balance = Decimal("150.0")
            elif role.participant_id == "P03":
                role.final_balance = Decimal("120.0")
            else:
                role.final_balance = Decimal("100.0")
        db.commit()
    orchestrator.close_session(session_id)
    return session_id


def test_tournament_shared_prize_tie_default() -> None:
    session_id = _seed_tie_session("shared_prize")
    with SessionLocal() as db:
        rows = db.scalars(
            select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
        ).all()

    assert len(rows) == 8
    p1 = next(r for r in rows if r.participant_id == "P01")
    p2 = next(r for r in rows if r.participant_id == "P02")
    p3 = next(r for r in rows if r.participant_id == "P03")
    assert p1.rank == 1 and float(p1.prize_eur) == 5.0
    assert p2.rank == 1 and float(p2.prize_eur) == 5.0
    assert p3.rank == 3 and float(p3.prize_eur) == 2.0


def test_tournament_random_tiebreak_logs_seed_and_assigns_distinct_ranks() -> None:
    session_id = _seed_tie_session("random")
    with SessionLocal() as db:
        rows = db.scalars(
            select(TournamentRanking).where(TournamentRanking.session_id == session_id).order_by(TournamentRanking.rank)
        ).all()
        logs = db.scalars(
            select(AdminAction).where(
                AdminAction.session_id == session_id,
                AdminAction.action_type == "tournament_tiebreak_random",
            )
        ).all()

    assert len(rows) == 8
    assert len(logs) >= 1
    assert any(log.reason is not None and "seed=" in log.reason and "rank=1" in log.reason for log in logs)

    p1 = next(r for r in rows if r.participant_id == "P01")
    p2 = next(r for r in rows if r.participant_id == "P02")
    ranks = sorted([p1.rank, p2.rank])
    assert ranks == [1, 2]
    prizes = sorted([float(p1.prize_eur), float(p2.prize_eur)], reverse=True)
    assert prizes == [5.0, 3.0]
