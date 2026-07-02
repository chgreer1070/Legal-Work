"""
FX Recovery System configuration.
"""

import os

# Database
DATABASE_PATH = os.environ.get("FX_DATABASE_PATH", "fx_recovery.db")
DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("FX_CLAUDE_MODEL", "claude-opus-4-8")
CLAUSE_EXTRACTION_MAX_TOKENS = 4096
NOTIFICATION_MAX_TOKENS = 2048

# FX Rate Feed
FX_FEED_SOURCE = os.environ.get("FX_FEED_SOURCE", "mock")  # 'mock', 'exchangerate_host', or 'oanda'
FX_DEMO_MODE = os.environ.get("FX_DEMO_MODE", "deterministic")  # 'deterministic' or 'random'
FX_FEED_TIMEOUT = float(os.environ.get("FX_FEED_TIMEOUT", "10"))
EXCHANGERATE_HOST_URL = os.environ.get(
    "FX_EXCHANGERATE_HOST_URL", "https://api.exchangerate.host/latest"
)
EXCHANGERATE_HOST_KEY = os.environ.get("FX_EXCHANGERATE_HOST_KEY", "")
OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")

# Monitoring
RATE_FETCH_INTERVAL_MINUTES = int(os.environ.get("FX_RATE_INTERVAL", "15"))
THRESHOLD_CHECK_INTERVAL_MINUTES = int(os.environ.get("FX_THRESHOLD_INTERVAL", "60"))

# Monitored currency pairs
CURRENCY_PAIRS = [
    "USD/BRL",
    "USD/MXN",
    "USD/CNY",
]

# Upload directory for contracts
CONTRACT_UPLOAD_DIR = os.environ.get("FX_UPLOAD_DIR", "fx_uploads")

# Maximum contract upload size in megabytes (enforced per-request on the
# FX upload route; the converter app manages its own app-wide limit)
MAX_UPLOAD_MB = int(os.environ.get("FX_MAX_UPLOAD_MB", "20"))

_KNOWN_FEED_SOURCES = {"mock", "exchangerate_host", "oanda"}


def validate_config():
    """Fail fast on configuration that would break monitoring at runtime.

    Raises ValueError for values that are outright wrong; unknown feed
    sources only warn because the feed layer falls back to mock by design.
    """
    import logging

    problems = []
    if RATE_FETCH_INTERVAL_MINUTES <= 0:
        problems.append(f"FX_RATE_INTERVAL must be positive, got {RATE_FETCH_INTERVAL_MINUTES}")
    if THRESHOLD_CHECK_INTERVAL_MINUTES <= 0:
        problems.append(f"FX_THRESHOLD_INTERVAL must be positive, got {THRESHOLD_CHECK_INTERVAL_MINUTES}")
    if FX_FEED_TIMEOUT <= 0:
        problems.append(f"FX_FEED_TIMEOUT must be positive, got {FX_FEED_TIMEOUT}")
    if MAX_UPLOAD_MB <= 0:
        problems.append(f"FX_MAX_UPLOAD_MB must be positive, got {MAX_UPLOAD_MB}")
    if not CURRENCY_PAIRS:
        problems.append("CURRENCY_PAIRS must not be empty")
    if problems:
        raise ValueError("Invalid FX configuration: " + "; ".join(problems))

    if FX_FEED_SOURCE not in _KNOWN_FEED_SOURCES:
        logging.getLogger(__name__).warning(
            "Unknown FX_FEED_SOURCE %r — the feed layer will fall back to mock",
            FX_FEED_SOURCE,
        )
