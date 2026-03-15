"""
FX rate cache with SQLite persistence.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc

from fx.db import get_session
from fx.models import FXRate
from fx.monitoring.fx_feed import get_current_rates, generate_historical_rates


def refresh_rates() -> list[dict]:
    """Fetch current rates and persist to database."""
    rates_data = get_current_rates()
    session = get_session()
    saved = []
    try:
        for pair, data in rates_data.items():
            rate = FXRate(
                currency_pair=data["pair"],
                rate=Decimal(str(data["rate"])),
                source=data["source"],
            )
            session.add(rate)
            saved.append(data)
        session.commit()
    finally:
        session.close()
    return saved


def get_latest_rates() -> dict[str, dict]:
    """Get the most recent rate for each currency pair."""
    session = get_session()
    try:
        result = {}
        pairs = session.query(FXRate.currency_pair).distinct().all()
        for (pair,) in pairs:
            latest = (
                session.query(FXRate)
                .filter(FXRate.currency_pair == pair)
                .order_by(desc(FXRate.fetched_at))
                .first()
            )
            if latest:
                result[pair] = latest.to_dict()
        return result
    finally:
        session.close()


def get_rate_history(pair: str, days: int = 30) -> list[dict]:
    """Get rate history for a currency pair."""
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rates = (
            session.query(FXRate)
            .filter(FXRate.currency_pair == pair, FXRate.fetched_at >= cutoff)
            .order_by(FXRate.fetched_at.asc())
            .all()
        )
        return [r.to_dict() for r in rates]
    finally:
        session.close()


def seed_historical_rates():
    """Seed the database with historical mock rates."""
    from fx.config import CURRENCY_PAIRS

    session = get_session()
    try:
        for pair in CURRENCY_PAIRS:
            existing = session.query(FXRate).filter(FXRate.currency_pair == pair).count()
            if existing > 0:
                continue
            history = generate_historical_rates(pair, days=90)
            for data in history:
                rate = FXRate(
                    currency_pair=data["pair"],
                    rate=Decimal(str(data["rate"])),
                    source=data["source"],
                    fetched_at=datetime.fromisoformat(data["fetched_at"]),
                )
                session.add(rate)
        session.commit()
    finally:
        session.close()
