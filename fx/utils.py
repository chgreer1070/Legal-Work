"""
Shared utility functions for the FX Recovery System.
"""

import logging
import time

logger = logging.getLogger(__name__)


def call_claude_with_retry(client, max_retries: int = 3, timeout_seconds: float | None = None, **kwargs):
    """
    Wrapper around client.messages.create() with exponential backoff.

    Retries on RateLimitError and APIConnectionError. When ``timeout_seconds``
    is set, stop retrying and re-raise once the next backoff sleep would push
    total elapsed time past the deadline — prevents hanging indefinitely when
    the remote API is stuck.
    """
    import anthropic

    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None

    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
            if attempt == max_retries:
                raise
            wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
            if deadline is not None and time.monotonic() + wait >= deadline:
                logger.warning(
                    "Claude API error (attempt %d/%d), retry budget exhausted by timeout_seconds=%s: %s",
                    attempt + 1, max_retries, timeout_seconds, e,
                )
                raise
            logger.warning("Claude API error (attempt %d/%d), retrying in %ds: %s", attempt + 1, max_retries, wait, e)
            time.sleep(wait)
