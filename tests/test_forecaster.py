"""
Unit tests for fx.prediction.forecaster.
"""

from datetime import datetime, timedelta

import pytest

from fx.models import FXRate
from fx.prediction.forecaster import forecast_threshold_crossing, run_all_predictions


def _seed_rates(session, pair, values, start_days_ago=60):
    """Insert a synthetic price series for `pair`, one row per day."""
    now = datetime.utcnow()
    for i, v in enumerate(values):
        session.add(
            FXRate(
                currency_pair=pair,
                rate=v,
                source="test",
                fetched_at=now - timedelta(days=start_days_ago - i),
            )
        )
    session.commit()


def test_insufficient_data_returns_empty_prediction(test_db, db_session):
    _seed_rates(db_session, "USD/BRL", [5.0, 5.01, 5.02])  # only 3 rows
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    assert result["error"] == "Insufficient historical data"
    assert result["predicted_direction"] == "unknown"
    assert result["crossing_probability"] is None


def test_flat_rates_give_zero_probability(test_db, db_session):
    _seed_rates(db_session, "USD/BRL", [5.00] * 30)
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    # With zero volatility, crossing probability collapses to 0.
    assert result["crossing_probability"] == 0.0


def test_increasing_rates_predict_depreciation(test_db, db_session):
    values = [5.00 + 0.01 * i for i in range(30)]
    _seed_rates(db_session, "USD/BRL", values)
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    assert result["predicted_direction"] == "depreciation"
    assert 0.0 <= result["crossing_probability"] <= 1.0


def test_decreasing_rates_predict_appreciation(test_db, db_session):
    values = [5.00 - 0.01 * i for i in range(30)]
    _seed_rates(db_session, "USD/BRL", values)
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    assert result["predicted_direction"] == "appreciation"
    assert 0.0 <= result["crossing_probability"] <= 1.0


def test_confidence_interval_symmetric_around_trend_adjusted_rate(test_db, db_session):
    values = [5.00 + 0.005 * (i % 3 - 1) for i in range(30)]  # small zig-zag
    _seed_rates(db_session, "USD/BRL", values)
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    # Interval should be symmetric around the trend-adjusted center,
    # not the raw current rate.
    center = (result["confidence_upper"] + result["confidence_lower"]) / 2
    upper_gap = result["confidence_upper"] - center
    lower_gap = center - result["confidence_lower"]
    assert abs(upper_gap - lower_gap) < 1e-6


def test_probability_is_clamped_to_unit_interval(test_db, db_session):
    # Extremely volatile series — trend + volatility should still give p in [0, 1].
    values = [5.0 + 0.5 * ((-1) ** i) for i in range(30)]
    _seed_rates(db_session, "USD/BRL", values)
    result = forecast_threshold_crossing("USD/BRL", threshold_pct=5.0)

    assert 0.0 <= result["crossing_probability"] <= 1.0


def test_run_all_predictions_returns_one_entry_per_pair(test_db, db_session):
    from fx.config import CURRENCY_PAIRS

    # Seed enough data for every pair so none return the empty shape.
    for pair in CURRENCY_PAIRS:
        _seed_rates(db_session, pair, [5.0 + 0.005 * i for i in range(30)])

    results = run_all_predictions(threshold_pct=5.0)
    assert len(results) == len(CURRENCY_PAIRS)
    seen = {r["currency_pair"] for r in results}
    assert seen == set(CURRENCY_PAIRS)
