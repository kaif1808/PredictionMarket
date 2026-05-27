from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import create_engine, text

from server.config import load_settings


@dataclass
class SessionFrames:
    sessions: pd.DataFrame
    markets: pd.DataFrame
    rounds: pd.DataFrame
    trades: pd.DataFrame
    signals: pd.DataFrame
    market_roles: pd.DataFrame
    tournament: pd.DataFrame


def _engine():
    settings = load_settings()
    return create_engine(settings.database_url)


def load_session(session_id: int) -> SessionFrames:
    engine = _engine()
    with engine.connect() as conn:
        sessions = pd.read_sql(text("SELECT * FROM sessions WHERE id = :sid"), conn, params={"sid": session_id})
        markets = pd.read_sql(
            text("SELECT * FROM markets WHERE session_id = :sid ORDER BY market_number"),
            conn,
            params={"sid": session_id},
        )
        rounds = pd.read_sql(
            text(
                """
                SELECT r.* FROM rounds r
                JOIN markets m ON m.id = r.market_id
                WHERE m.session_id = :sid
                ORDER BY m.market_number, r.round_number
                """
            ),
            conn,
            params={"sid": session_id},
        )
        trades = pd.read_sql(
            text(
                """
                SELECT t.*, r.market_id FROM trades t
                JOIN rounds r ON r.id = t.round_id
                JOIN markets m ON m.id = r.market_id
                WHERE m.session_id = :sid
                ORDER BY t.executed_at
                """
            ),
            conn,
            params={"sid": session_id},
        )
        signals = pd.read_sql(
            text(
                """
                SELECT s.*, r.market_id FROM signals s
                JOIN rounds r ON r.id = s.round_id
                JOIN markets m ON m.id = r.market_id
                WHERE m.session_id = :sid
                ORDER BY s.id
                """
            ),
            conn,
            params={"sid": session_id},
        )
        market_roles = pd.read_sql(
            text(
                """
                SELECT mr.*, m.market_number, m.stage
                FROM market_roles mr
                JOIN markets m ON m.id = mr.market_id
                WHERE m.session_id = :sid
                ORDER BY m.market_number, mr.participant_id
                """
            ),
            conn,
            params={"sid": session_id},
        )
        tournament = pd.read_sql(
            text("SELECT * FROM tournament_rankings WHERE session_id = :sid ORDER BY rank"),
            conn,
            params={"sid": session_id},
        )

    return SessionFrames(
        sessions=sessions,
        markets=markets,
        rounds=rounds,
        trades=trades,
        signals=signals,
        market_roles=market_roles,
        tournament=tournament,
    )
