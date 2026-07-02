"""
Database initialization and session management.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fx.config import DATABASE_URI


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URI,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


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
    _ensure_clause_formula_columns()
    _ensure_alert_columns()
    _ensure_indexes()

    if app is not None:
        app.config["FX_DB_ENGINE"] = engine


def _ensure_clause_formula_columns():
    """Add formula columns to fx_clauses on databases created before they existed."""
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(fx_clauses)")}
        for name, ddl in (
            ("formula_type", "VARCHAR(50)"),
            ("formula_expression", "TEXT"),
            ("formula_description", "TEXT"),
        ):
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE fx_clauses ADD COLUMN {name} {ddl}")
        conn.commit()


def _ensure_alert_columns():
    """Add newer alert columns to databases created before they existed."""
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alerts)")}
        if "rate_direction" not in existing:
            conn.exec_driver_sql("ALTER TABLE alerts ADD COLUMN rate_direction VARCHAR(10)")
        conn.commit()


def _ensure_indexes():
    """Create hot-path indexes on databases created before they were declared."""
    with engine.connect() as conn:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_alerts_status ON alerts (status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_alerts_clause_status ON alerts (clause_id, status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_transactions_contract_pair_end"
            " ON transactions (contract_id, currency_pair, period_end)"
        )
        conn.commit()


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
