"""
Shared utility functions for the FX Recovery System.
"""

import logging
import time

logger = logging.getLogger(__name__)


def get_anthropic_client():
    """
    Build an Anthropic client. Uses the explicit ANTHROPIC_API_KEY when
    configured; otherwise lets the SDK resolve credentials from the
    environment (ANTHROPIC_AUTH_TOKEN, profile). When no credentials
    resolve, the SDK raises at construction — callers already catch and
    degrade gracefully.
    """
    import anthropic

    from fx.config import ANTHROPIC_API_KEY

    if ANTHROPIC_API_KEY:
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return anthropic.Anthropic()


def call_claude_with_retry(client, max_retries: int = 3, **kwargs):
    """
    Wrapper around client.messages.create() with exponential backoff.

    Retries on RateLimitError and APIConnectionError.
    """
    import anthropic

    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
            if attempt == max_retries:
                raise
            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
            logger.warning("Claude API error (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_retries, wait, e)
            time.sleep(wait)
