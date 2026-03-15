"""
Database initialization and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fx.config import DATABASE_URI


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URI, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db(app=None):
    """Create all tables. Optionally attach db to Flask app."""
    from fx.models import (  # noqa: F401
        Alert,
        AuditEntry,
        Contract,
        FXClause,
        FXRate,
        Prediction,
        Transaction,
    )

    Base.metadata.create_all(bind=engine)

    if app is not None:
        app.config["FX_DB_ENGINE"] = engine


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
