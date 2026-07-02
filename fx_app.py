"""
Unified entry point: serves both the Outlook-to-PDF converter
and the FX Recovery System.

- /           -> Outlook-to-PDF converter (existing app.py)
- /fx/        -> FX Recovery dashboard and API
"""

import os
from pathlib import Path

from flask import Flask

from fx import create_fx_blueprint
from fx.db import init_db
from fx.monitoring.scheduler import start_scheduler


def create_app():
    """Configure and return the unified Flask application."""
    from fx.config import validate_config
    validate_config()

    # Try to import the existing converter app; fall back to a standalone Flask app
    try:
        from app import app as base_app
    except (ImportError, ModuleNotFoundError):
        base_app = Flask(__name__)
        base_app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

    # Initialize FX database
    init_db(base_app)

    # Register FX blueprint
    fx_bp = create_fx_blueprint()
    base_app.register_blueprint(fx_bp, url_prefix="/fx")

    # Create upload directory
    from fx.config import CONTRACT_UPLOAD_DIR
    Path(CONTRACT_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Start background scheduler for rate monitoring
    if os.environ.get("FX_SCHEDULER_ENABLED", "true").lower() == "true":
        start_scheduler(base_app)

    return base_app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
