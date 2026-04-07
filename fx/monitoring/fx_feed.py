"""
FX rate feed - mock implementation with interface for real API.
"""

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal

import requests

from fx.config import (
    CURRENCY_PAIRS,
    EXCHANGERATE_HOST_KEY,
    EXCHANGERATE_HOST_URL,
    FX_DEMO_MODE,
    FX_FEED_SOURCE,
    FX_FEED_TIMEOUT,
)

logger = logging.getLogger(__name__)

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
    """Get current FX rates for all monitored pairs.

    Tries the configured live source; on any failure, falls back to mock so
    the monitoring loop never crashes.
    """
    if FX_FEED_SOURCE == "exchangerate_host":
        try:
            rates = _get_exchangerate_host_rates()
            if rates:
                return rates
            logger.warning("exchangerate.host returned no rates; falling back to mock")
        except Exception as e:
            logger.warning("exchangerate.host fetch failed (%s); falling back to mock", e)
    return _get_mock_rates()


def _get_exchangerate_host_rates() -> dict[str, dict]:
    """Fetch live rates from exchangerate.host.

    Each pair is parsed as BASE/QUOTE. We group pairs by base currency and
    issue one HTTP call per base. Returns {} on partial/empty response so the
    caller can decide to fall back.
    """
    by_base: dict[str, list[str]] = {}
    for pair in CURRENCY_PAIRS:
        if "/" not in pair:
            continue
        base, quote = pair.split("/", 1)
        by_base.setdefault(base, []).append(quote)

    fetched_at = datetime.utcnow().isoformat()
    result: dict[str, dict] = {}

    for base, quotes in by_base.items():
        params = {"base": base, "symbols": ",".join(quotes)}
        if EXCHANGERATE_HOST_KEY:
            params["access_key"] = EXCHANGERATE_HOST_KEY

        resp = requests.get(EXCHANGERATE_HOST_URL, params=params, timeout=FX_FEED_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        if not payload.get("success", True) and "rates" not in payload:
            err = payload.get("error", {})
            raise RuntimeError(f"exchangerate.host error: {err}")

        rates_map = payload.get("rates") or {}
        for quote in quotes:
            if quote not in rates_map:
                logger.warning("exchangerate.host missing quote %s for base %s", quote, base)
                continue
            pair_key = f"{base}/{quote}"
            try:
                rate_value = float(rates_map[quote])
            except (TypeError, ValueError):
                logger.warning("exchangerate.host returned non-numeric rate for %s", pair_key)
                continue
            result[pair_key] = {
                "pair": pair_key,
                "rate": round(rate_value, 6),
                "source": "exchangerate.host",
                "fetched_at": fetched_at,
            }

    # Require all configured pairs to be present, otherwise treat as failure
    if len(result) != len(CURRENCY_PAIRS):
        logger.warning(
            "exchangerate.host returned %d/%d pairs; treating as failure",
            len(result),
            len(CURRENCY_PAIRS),
        )
        return {}

    return result


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
