"""
FX rate feed - mock implementation with interface for real API.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from fx.config import FX_FEED_SOURCE, FX_DEMO_MODE, CURRENCY_PAIRS

# Base rates aligned with seed clause base rates
BASE_RATES = {
    "USD/BRL": 5.05,
    "USD/MXN": 17.50,
    "USD/CNY": 7.25,
}

# Stateful drift tracking across calls
_cumulative_drift = {}
_call_count = 0
_demo_rng = None


def _get_demo_rng():
    """Get the seeded RNG for deterministic mode."""
    global _demo_rng
    if _demo_rng is None:
        _demo_rng = random.Random(42)
    return _demo_rng


def reset_mock_state():
    """Reset cumulative drift — useful for testing."""
    global _cumulative_drift, _call_count, _demo_rng
    _cumulative_drift = {}
    _call_count = 0
    _demo_rng = None


def get_current_rates() -> dict[str, dict]:
    """Get current FX rates for all monitored pairs."""
    if FX_FEED_SOURCE == "mock":
        return _get_mock_rates()
    else:
        return _get_mock_rates()  # Fallback to mock


def _get_mock_rates() -> dict[str, dict]:
    """Generate mock rates with stateful drift that triggers threshold breaches."""
    global _call_count
    _call_count += 1

    if FX_DEMO_MODE == "deterministic":
        return _get_deterministic_rates()
    else:
        return _get_random_rates()


def _get_deterministic_rates() -> dict[str, dict]:
    """Seeded random walk — guarantees threshold breaches within 3-5 refreshes."""
    rng = _get_demo_rng()
    rates = {}

    for pair in CURRENCY_PAIRS:
        base = BASE_RATES.get(pair, 1.0)

        if pair not in _cumulative_drift:
            _cumulative_drift[pair] = 0.0

        # Deterministic schedule: ~1.5% drift per call, guaranteed breach by call 3-4
        step = rng.gauss(0.015, 0.003)
        # Alternate direction by pair for variety
        if pair == "USD/CNY":
            step = -abs(step)
        else:
            step = abs(step)

        _cumulative_drift[pair] += step
        rate = round(base * (1.0 + _cumulative_drift[pair]), 6)
        rates[pair] = {
            "pair": pair,
            "rate": rate,
            "source": "mock",
            "fetched_at": datetime.utcnow().isoformat(),
        }
    return rates


def _get_random_rates() -> dict[str, dict]:
    """Larger random walk with bias toward threshold breaches."""
    rates = {}

    for pair in CURRENCY_PAIRS:
        base = BASE_RATES.get(pair, 1.0)

        if pair not in _cumulative_drift:
            _cumulative_drift[pair] = 0.0

        # Larger σ=0.015 with occasional regime shifts
        drift_step = random.gauss(0, 0.015)

        # 5% chance of a regime shift (3-8% jump)
        if random.random() < 0.05:
            drift_step += random.choice([-1, 1]) * random.uniform(0.03, 0.08)

        # Bias toward breaching: if drift is small, nudge it outward
        if abs(_cumulative_drift[pair]) < 0.02:
            drift_step += 0.005 * (1 if random.random() > 0.5 else -1)

        _cumulative_drift[pair] += drift_step
        rate = round(base * (1.0 + _cumulative_drift[pair]), 6)
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

    # Use a separate seeded RNG for reproducible historical data
    hist_rng = random.Random(hash(pair) & 0xFFFFFFFF)

    for i in range(days, 0, -1):
        # Random walk with mean reversion
        drift = hist_rng.gauss(0, 0.003) * current
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
