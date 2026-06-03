from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from server.config import load_settings
from server.db_models import Base


settings = load_settings()

engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
ALEMBIC_BASELINE_REVISION = "2b7a9d4e6f01"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    sessions_columns = {column["name"] for column in inspector.get_columns("sessions")} if "sessions" in table_names else set()
    if "sessions" in table_names and "lmsr_b_parameter" not in sessions_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN lmsr_b_parameter NUMERIC(8,4) NOT NULL DEFAULT 36"))
    if "sessions" in table_names and "show_tournament_payout_screen" not in sessions_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN show_tournament_payout_screen BOOLEAN NOT NULL DEFAULT TRUE"))
    if "sessions" in table_names and "treated_count" not in sessions_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE sessions ADD COLUMN treated_count INTEGER NOT NULL DEFAULT 3"))

    if "alembic_version" not in table_names:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(
                text("INSERT INTO alembic_version(version_num) VALUES (:version_num)"),
                {"version_num": ALEMBIC_BASELINE_REVISION},
            )
