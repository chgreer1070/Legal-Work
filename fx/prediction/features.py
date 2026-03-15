"""
Feature engineering from FX rate history.
"""

import numpy as np


def compute_features(rates: list[float]) -> dict:
    """Compute statistical features from a rate time series."""
    if len(rates) < 2:
        return {}

    values = np.array(rates)
    returns = np.diff(values) / values[:-1]

    return {
        "mean_rate": float(np.mean(values)),
        "std_rate": float(np.std(values)),
        "min_rate": float(np.min(values)),
        "max_rate": float(np.max(values)),
        "current_rate": float(values[-1]),
        "mean_return": float(np.mean(returns)),
        "volatility": float(np.std(returns)),
        "skewness": float(_skewness(returns)),
        "max_drawdown": float(_max_drawdown(values)),
        "trend_slope": float(_trend_slope(values)),
    }


def _skewness(arr: np.ndarray) -> float:
    """Compute skewness of a distribution."""
    n = len(arr)
    if n < 3:
        return 0.0
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return 0.0
    return float(np.mean(((arr - mean) / std) ** 3))


def _max_drawdown(prices: np.ndarray) -> float:
    """Compute maximum drawdown from peak."""
    peak = prices[0]
    max_dd = 0.0
    for price in prices:
        if price > peak:
            peak = price
        dd = (peak - price) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return max_dd


def _trend_slope(values: np.ndarray) -> float:
    """Compute linear trend slope."""
    x = np.arange(len(values))
    if len(values) < 2:
        return 0.0
    coeffs = np.polyfit(x, values, 1)
    return coeffs[0]
