"""
FX Recovery System configuration.
"""

import os

# Database
DATABASE_PATH = os.environ.get("FX_DATABASE_PATH", "fx_recovery.db")
DATABASE_URI = f"sqlite:///{DATABASE_PATH}"

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("FX_CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUSE_EXTRACTION_MAX_TOKENS = 4096
NOTIFICATION_MAX_TOKENS = 2048

# FX Rate Feed
FX_FEED_SOURCE = os.environ.get("FX_FEED_SOURCE", "mock")  # 'mock' or 'oanda'
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
