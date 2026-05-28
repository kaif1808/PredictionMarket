from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run_alembic(args: list[str], database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_role_tier_migration_rewrites_legacy_values(tmp_path: Path) -> None:
    db_path = tmp_path / "role_tier_migration.db"
    db_url = f"sqlite:///{db_path}"

    _run_alembic(["upgrade", "12d8e8c3f7a1"], db_url)

    with sqlite3.connect(str(db_path)) as con:
        con.execute(
            """
            INSERT INTO sessions
            (id, session_label, rotation_id, scenario_order, lmsr_b_parameter)
            VALUES (1, 'migration-test', 1, 'C,A,B,D', 36)
            """
        )
        con.executemany(
            "INSERT INTO participants (id) VALUES (?)",
            [("P01",), ("P02",), ("P03",)],
        )
        con.execute(
            """
            INSERT INTO markets
            (id, session_id, market_number, scenario_id, true_probability, stage, b_parameter, q_yes, q_no)
            VALUES (1, 1, 1, 'C', 0.5000, 1, 36, 0, 0)
            """
        )
        con.executemany(
            """
            INSERT INTO market_roles
            (market_id, participant_id, role_tier, endowment_tokens, starting_balance, yes_held, no_held)
            VALUES (1, ?, ?, 100, 100, 0, 0)
            """,
            [("P01", "semi_informed"), ("P02", "insider"), ("P03", "uninformed")],
        )
        con.commit()

    _run_alembic(["upgrade", "head"], db_url)

    with sqlite3.connect(str(db_path)) as con:
        rows = con.execute("SELECT participant_id, role_tier FROM market_roles ORDER BY participant_id").fetchall()
    assert rows == [("P01", "informed"), ("P02", "informed"), ("P03", "uninformed")]
