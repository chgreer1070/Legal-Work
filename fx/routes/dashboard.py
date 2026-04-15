"""
Dashboard page routes.
"""

from flask import Blueprint, render_template

dashboard_bp = Blueprint("fx_dashboard", __name__)


@dashboard_bp.route("/")
def index():
    """Main FX Recovery dashboard."""
    return render_template("dashboard.html")


@dashboard_bp.route("/predictions")
def predictions():
    """Predictions page."""
    return render_template("predictions.html")


@dashboard_bp.route("/audit")
def audit_log():
    """Audit log viewer."""
    return render_template("audit_log.html")
