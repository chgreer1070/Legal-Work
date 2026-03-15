"""
Historical rate data for demo seeding.
"""

from fx.monitoring.rate_cache import seed_historical_rates


def seed_rates():
    """Seed 90 days of historical rates for all monitored pairs."""
    seed_historical_rates()
