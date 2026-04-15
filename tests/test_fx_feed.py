"""
Unit tests for fx.monitoring.fx_feed.

Covers the live -> mock fallback path (sandbox note: real HTTPS is blocked, so
these tests always mock requests.get), deterministic mock drift, and historical
rate seeding.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from fx.config import CURRENCY_PAIRS
from fx.monitoring import fx_feed


pytestmark = pytest.mark.usefixtures("reset_feed_state")


def _ok_response(rates_by_quote):
    """Build a MagicMock response that mimics requests.Response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"success": True, "rates": rates_by_quote}
    return resp


def test_get_current_rates_returns_one_entry_per_pair():
    rates = fx_feed.get_current_rates()
    assert set(rates.keys()) == set(CURRENCY_PAIRS)
    for pair, data in rates.items():
        assert data["pair"] == pair
        assert isinstance(data["rate"], float)
        assert data["rate"] > 0
        assert "fetched_at" in data


def test_deterministic_mode_is_reproducible(monkeypatch):
    """Two fresh sequences from a reset state must match exactly."""
    monkeypatch.setattr(fx_feed, "FX_DEMO_MODE", "deterministic")
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "mock")

    first = [fx_feed.get_current_rates() for _ in range(3)]
    fx_feed.reset_mock_state()
    second = [fx_feed.get_current_rates() for _ in range(3)]

    for a, b in zip(first, second):
        for pair in CURRENCY_PAIRS:
            assert a[pair]["rate"] == b[pair]["rate"]


def test_live_feed_success_returns_exchangerate_host_source(monkeypatch):
    """When requests.get returns all expected pairs, we use the live values."""
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "exchangerate_host")

    # One response per base currency; all our pairs have base USD.
    response = _ok_response({"BRL": 5.10, "MXN": 17.60, "CNY": 7.30})
    with patch("fx.monitoring.fx_feed.requests.get", return_value=response) as mock_get:
        rates = fx_feed.get_current_rates()

    assert mock_get.called
    assert set(rates.keys()) == set(CURRENCY_PAIRS)
    for data in rates.values():
        assert data["source"] == "exchangerate.host"


def test_live_feed_partial_response_falls_back_to_mock(monkeypatch):
    """If the live feed returns fewer pairs than configured, fall back to mock."""
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "exchangerate_host")

    # Missing MXN and CNY — only 1 of 3 pairs returned.
    response = _ok_response({"BRL": 5.10})
    with patch("fx.monitoring.fx_feed.requests.get", return_value=response):
        rates = fx_feed.get_current_rates()

    assert set(rates.keys()) == set(CURRENCY_PAIRS)
    for data in rates.values():
        assert data["source"] == "mock"


def test_live_feed_http_error_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "exchangerate_host")

    err_resp = MagicMock()
    err_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    with patch("fx.monitoring.fx_feed.requests.get", return_value=err_resp):
        rates = fx_feed.get_current_rates()

    assert set(rates.keys()) == set(CURRENCY_PAIRS)
    for data in rates.values():
        assert data["source"] == "mock"


def test_live_feed_timeout_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "exchangerate_host")

    with patch(
        "fx.monitoring.fx_feed.requests.get",
        side_effect=requests.Timeout("timed out"),
    ):
        rates = fx_feed.get_current_rates()

    assert set(rates.keys()) == set(CURRENCY_PAIRS)
    for data in rates.values():
        assert data["source"] == "mock"


def test_exchangerate_host_raises_on_api_error_payload(monkeypatch):
    """When the API returns success=false with no rates, _get_exchangerate_host_rates raises."""
    monkeypatch.setattr(fx_feed, "FX_FEED_SOURCE", "exchangerate_host")

    err_resp = MagicMock()
    err_resp.raise_for_status = MagicMock()
    err_resp.json.return_value = {"success": False, "error": {"code": 101, "info": "bad key"}}

    with patch("fx.monitoring.fx_feed.requests.get", return_value=err_resp):
        with pytest.raises(RuntimeError, match="exchangerate.host error"):
            fx_feed._get_exchangerate_host_rates()


def test_generate_historical_rates_is_deterministic_per_pair():
    a = fx_feed.generate_historical_rates("USD/BRL", days=30)
    b = fx_feed.generate_historical_rates("USD/BRL", days=30)

    assert len(a) == 30
    assert len(b) == 30
    assert [r["rate"] for r in a] == [r["rate"] for r in b]
    # Different pair should give a different sequence.
    c = fx_feed.generate_historical_rates("USD/MXN", days=30)
    assert [r["rate"] for r in a] != [r["rate"] for r in c]
