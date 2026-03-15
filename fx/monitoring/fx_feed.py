"""
FX rate feed - mock implementation with interface for real API.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from fx.config import FX_FEED_SOURCE, CURRENCY_PAIRS

# Realistic base rates as of early 2026
BASE_RATES = {
    "USD/BRL": 5.15,
    "USD/MXN": 17.85,
    "USD/CNY": 7.28,
}


def get_current_rates() -> dict[str, dict]:
    """Get current FX rates for all monitored pairs."""
    if FX_FEED_SOURCE == "mock":
        return _get_mock_rates()
    else:
        return _get_mock_rates()  # Fallback to mock


def _get_mock_rates() -> dict[str, dict]:
    """Generate realistic mock rates with random walk drift."""
    rates = {}
    for pair in CURRENCY_PAIRS:
        base = BASE_RATES.get(pair, 1.0)
        # Random walk: +/- up to 2% drift
        drift = random.gauss(0, 0.005) * base
        rate = round(base + drift, 6)
        rates[pair] = {
            "pair": pair,
            "rate": rate,
            "source": "mock",
            "fetched_at": datetime.utcnow().isoformat(),
        }
    return rates


def generate_historical_rates(pair: str, days: int = 90) -> list[dict]:
    """Generate mock historical daily rates for a currency pair."""
    base = BASE_RATES.get(pair, 1.0)
    rates = []
    current = base
    now = datetime.utcnow()

    for i in range(days, 0, -1):
        # Random walk with mean reversion
        drift = random.gauss(0, 0.003) * current
        mean_reversion = (base - current) * 0.02
        current = max(current + drift + mean_reversion, base * 0.8)
        current = min(current, base * 1.2)

        rates.append({
            "pair": pair,
            "rate": round(current, 6),
            "source": "mock",
            "date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
            "fetched_at": (now - timedelta(days=i)).isoformat(),
        })

    return rates
