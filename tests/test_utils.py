"""
Unit tests for fx.utils.call_claude_with_retry.
"""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from fx.utils import call_claude_with_retry


def _make_rate_limit_error():
    """Build a RateLimitError without needing a real httpx Response."""
    return anthropic.RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )


def _make_connection_error():
    return anthropic.APIConnectionError(request=MagicMock())


def test_success_on_first_attempt_does_not_sleep(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = "ok"

    with patch("fx.utils.time.sleep") as mock_sleep:
        result = call_claude_with_retry(mock_anthropic_client, max_retries=3, model="m")

    assert result == "ok"
    assert mock_anthropic_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()


def test_rate_limit_then_success_retries(mock_anthropic_client):
    mock_anthropic_client.messages.create.side_effect = [
        _make_rate_limit_error(),
        "ok",
    ]

    with patch("fx.utils.time.sleep") as mock_sleep:
        result = call_claude_with_retry(mock_anthropic_client, max_retries=3)

    assert result == "ok"
    assert mock_anthropic_client.messages.create.call_count == 2
    mock_sleep.assert_called_once_with(2)


def test_connection_error_exhausts_retries_then_raises(mock_anthropic_client):
    mock_anthropic_client.messages.create.side_effect = _make_connection_error()

    with patch("fx.utils.time.sleep") as mock_sleep:
        with pytest.raises(anthropic.APIConnectionError):
            call_claude_with_retry(mock_anthropic_client, max_retries=3)

    # max_retries=3 means up to 4 total attempts (0..3).
    assert mock_anthropic_client.messages.create.call_count == 4
    # Sleeps happen before each of the first 3 retries: 2s, 4s, 8s.
    assert [c.args[0] for c in mock_sleep.call_args_list] == [2, 4, 8]


def test_exponential_backoff_schedule(mock_anthropic_client):
    """Backoff doubles: 2s, 4s, 8s, 16s for max_retries=4."""
    mock_anthropic_client.messages.create.side_effect = [
        _make_rate_limit_error(),
        _make_rate_limit_error(),
        _make_rate_limit_error(),
        _make_rate_limit_error(),
        "ok",
    ]

    with patch("fx.utils.time.sleep") as mock_sleep:
        result = call_claude_with_retry(mock_anthropic_client, max_retries=4)

    assert result == "ok"
    assert [c.args[0] for c in mock_sleep.call_args_list] == [2, 4, 8, 16]


def test_non_retryable_exception_propagates_without_retry(mock_anthropic_client):
    """ValueError (or any non-anthropic exception) must not be swallowed."""
    mock_anthropic_client.messages.create.side_effect = ValueError("bad arg")

    with patch("fx.utils.time.sleep") as mock_sleep:
        with pytest.raises(ValueError):
            call_claude_with_retry(mock_anthropic_client, max_retries=3)

    assert mock_anthropic_client.messages.create.call_count == 1
    mock_sleep.assert_not_called()
