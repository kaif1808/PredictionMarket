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


def test_signal_value_migration_expands_and_rewrites_legacy_values(tmp_path: Path) -> None:
    db_path = tmp_path / "signal_value_migration.db"
    db_url = f"sqlite:///{db_path}"

    _run_alembic(["upgrade", "c4a1d9e8b6f2"], db_url)

    with sqlite3.connect(str(db_path)) as con:
        con.execute(
            """
            INSERT INTO sessions
            (id, session_label, rotation_id, scenario_order, lmsr_b_parameter, treated_count)
            VALUES (1, 'signal-migration-test', 1, 'C,A,B,D', 36, 3)
            """
        )
        con.executemany(
            "INSERT INTO participants (id) VALUES (?)",
            [("P01",), ("P02",), ("P03",), ("P04",)],
        )
        con.execute(
            """
            INSERT INTO markets
            (id, session_id, market_number, scenario_id, true_probability, stage, b_parameter, q_yes, q_no)
            VALUES (1, 1, 1, 'C', 0.5000, 1, 36, 0, 0)
            """
        )
        con.execute(
            """
            INSERT INTO rounds
            (id, market_id, round_number, bayesian_benchmark)
            VALUES (1, 1, 1, 0.500000)
            """
        )
        con.executemany(
            """
            INSERT INTO signals
            (round_id, participant_id, signal_value, theta, posterior)
            VALUES (1, ?, ?, 0.850, 0.500000)
            """,
            [("P01", "H"), ("P02", "L")],
        )
        con.commit()

    _run_alembic(["upgrade", "head"], db_url)

    with sqlite3.connect(str(db_path)) as con:
        rows = con.execute(
            "SELECT participant_id, signal_value FROM signals ORDER BY participant_id"
        ).fetchall()
        con.execute(
            """
            INSERT INTO signals
            (round_id, participant_id, signal_value, theta, posterior)
            VALUES (1, 'P03', 'M+', 0.850, 0.500000)
            """
        )
        try:
            con.execute(
                """
                INSERT INTO signals
                (round_id, participant_id, signal_value, theta, posterior)
                VALUES (1, 'P04', 'H', 0.850, 0.500000)
                """
            )
        except sqlite3.IntegrityError:
            rejected_legacy_value = True
        else:
            rejected_legacy_value = False

    assert rows == [("P01", "S+"), ("P02", "S-")]
    assert rejected_legacy_value is True
