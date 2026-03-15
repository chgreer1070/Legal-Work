"""
Simplified FX threshold-crossing probability forecaster.
Uses moving average crossover + historical volatility.
"""

import math
from datetime import date, datetime, timedelta

import numpy as np

from fx.db import get_session
from fx.models import FXRate, Prediction
from fx.audit.logger import log_event

MODEL_VERSION = "mavg_vol_v1"


def forecast_threshold_crossing(
    currency_pair: str,
    threshold_pct: float,
    horizon_days: int = 30,
) -> dict:
    """
    Estimate probability of a currency pair crossing a threshold within horizon_days.

    Uses historical volatility and current trend to estimate crossing probability.
    Returns prediction data dict.
    """
    session = get_session()
    try:
        cutoff = datetime.utcnow() - timedelta(days=120)
        rates = (
            session.query(FXRate)
            .filter(FXRate.currency_pair == currency_pair, FXRate.fetched_at >= cutoff)
            .order_by(FXRate.fetched_at.asc())
            .all()
        )

        if len(rates) < 10:
            return _empty_prediction(currency_pair, horizon_days)

        values = np.array([float(r.rate) for r in rates])

        # Calculate daily returns
        returns = np.diff(values) / values[:-1]

        # Annualized volatility
        daily_vol = np.std(returns) if len(returns) > 1 else 0.01
        horizon_vol = daily_vol * math.sqrt(horizon_days)

        # Current trend: 20-day vs 50-day moving average
        short_ma = np.mean(values[-20:]) if len(values) >= 20 else np.mean(values)
        long_ma = np.mean(values[-50:]) if len(values) >= 50 else np.mean(values)
        trend = (short_ma - long_ma) / long_ma if long_ma != 0 else 0

        # Direction
        direction = "depreciation" if trend > 0 else "appreciation"

        # Probability of crossing threshold
        # Simplified: assume log-normal distribution of returns
        threshold_decimal = threshold_pct / 100.0
        if horizon_vol > 0:
            z_score = (threshold_decimal - abs(trend)) / horizon_vol
            # Approximate normal CDF using error function
            crossing_prob = 1.0 - 0.5 * (1.0 + math.erf(z_score / math.sqrt(2)))
        else:
            crossing_prob = 0.0

        crossing_prob = max(0.0, min(1.0, crossing_prob))

        # Confidence interval (1 sigma around current rate)
        current_rate = float(values[-1])
        confidence_lower = current_rate * (1.0 - horizon_vol)
        confidence_upper = current_rate * (1.0 + horizon_vol)

        prediction = Prediction(
            currency_pair=currency_pair,
            prediction_date=date.today(),
            horizon_days=horizon_days,
            crossing_probability=round(crossing_prob, 4),
            predicted_direction=direction,
            confidence_lower=round(confidence_lower, 6),
            confidence_upper=round(confidence_upper, 6),
            model_version=MODEL_VERSION,
        )
        session.add(prediction)
        session.commit()

        log_event(
            event_type="prediction_run",
            entity_type="prediction",
            entity_id=prediction.id,
            action=f"Forecast: {currency_pair} {crossing_prob:.1%} breach probability over {horizon_days}d",
            details={
                "pair": currency_pair,
                "crossing_probability": crossing_prob,
                "direction": direction,
                "horizon_vol": float(horizon_vol),
                "trend": float(trend),
            },
        )

        return prediction.to_dict()
    finally:
        session.close()


def _empty_prediction(currency_pair: str, horizon_days: int) -> dict:
    """Return an empty prediction when insufficient data."""
    return {
        "currency_pair": currency_pair,
        "prediction_date": date.today().isoformat(),
        "horizon_days": horizon_days,
        "crossing_probability": None,
        "predicted_direction": "unknown",
        "confidence_lower": None,
        "confidence_upper": None,
        "model_version": MODEL_VERSION,
        "error": "Insufficient historical data",
    }


def run_all_predictions(threshold_pct: float = 5.0, horizon_days: int = 30) -> list[dict]:
    """Run predictions for all monitored currency pairs."""
    from fx.config import CURRENCY_PAIRS

    results = []
    for pair in CURRENCY_PAIRS:
        result = forecast_threshold_crossing(pair, threshold_pct, horizon_days)
        results.append(result)
    return results
