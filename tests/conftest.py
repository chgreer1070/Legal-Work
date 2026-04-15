"""
Shared pytest fixtures for the FX Recovery core-logic test suite.

Tests never hit the real fx_recovery.db — every test that touches the DB gets a
fresh SQLite file under tmp_path with its own engine and SessionLocal, patched
onto fx.db so all callers (approval.py, calculator.py, forecaster.py, the
audit logger) use the isolated test DB.
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Swap fx.db.engine and fx.db.SessionLocal for a per-test SQLite file.

    Callers inside fx/* do `from fx.db import get_session`, and get_session()
    resolves SessionLocal at call time — so monkey-patching the module
    attribute is sufficient; the function object itself doesn't need replacing.
    """
    from fx import db as fx_db
    from fx.db import Base

    # Import models so Base.metadata knows about every table.
    import fx.models  # noqa: F401

    db_path = tmp_path / "test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)

    monkeypatch.setattr(fx_db, "engine", test_engine)
    monkeypatch.setattr(fx_db, "SessionLocal", TestSessionLocal)

    yield TestSessionLocal

    test_engine.dispose()


@pytest.fixture
def db_session(test_db):
    """A usable session for arranging test rows. Rolls back + closes on exit."""
    session = test_db()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def reset_feed_state():
    """Clear fx_feed module state before and after each test that uses it."""
    from fx.monitoring import fx_feed

    fx_feed.reset_mock_state()
    yield
    fx_feed.reset_mock_state()


@pytest.fixture
def mock_anthropic_client():
    """A MagicMock that mimics the anthropic client shape used by utils.py."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = MagicMock()
    return client
