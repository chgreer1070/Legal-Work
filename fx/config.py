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
