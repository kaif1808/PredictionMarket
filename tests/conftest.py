from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_ABM_TESTS") == "1":
        return
    skip_abm = pytest.mark.skip(reason="ABM tests are opt-in; set RUN_ABM_TESTS=1 to run them")
    for item in items:
        if item.path.name.startswith("test_abm_"):
            item.add_marker(skip_abm)


@pytest.fixture(scope="session", autouse=True)
def reset_db() -> None:
    from server.db import engine
    from server.db_models import Base

    try:
        Base.metadata.drop_all(bind=engine)
    except OperationalError:
        # In occasional local SQLite states (e.g., interrupted prior runs),
        # metadata can include objects that are already absent. Continue with
        # a clean create to keep test bootstrap deterministic.
        pass
    Base.metadata.create_all(bind=engine)
