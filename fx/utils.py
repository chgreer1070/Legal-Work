"""
Shared utility functions for the FX Recovery System.
"""

import logging
import time

logger = logging.getLogger(__name__)


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
