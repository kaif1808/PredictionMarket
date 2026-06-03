from __future__ import annotations

from sqlalchemy import create_engine, text


def test_init_db_preserves_existing_alembic_revision(monkeypatch, tmp_path) -> None:
    import server.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'init_db_revision.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        conn.execute(text("INSERT INTO alembic_version(version_num) VALUES ('legacy_revision')"))

    monkeypatch.setattr(db_module, "engine", engine)

    db_module.init_db()

    with engine.begin() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "legacy_revision"
