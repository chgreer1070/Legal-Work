"""
JSON API endpoints for dashboard, rates, and predictions.
"""

from flask import Blueprint, jsonify, request

from fx.db import get_session
from fx.models import Alert, Contract, FXClause
from fx.monitoring.rate_cache import get_latest_rates, get_rate_history, refresh_rates
from fx.monitoring.threshold_checker import check_all_thresholds
from fx.exposure.calculator import get_total_exposure_by_pair
from fx.prediction.forecaster import run_all_predictions
from fx.audit.logger import get_audit_log

api_bp = Blueprint("fx_api", __name__)


# ── Dashboard ────────────────────────────────────────────────────────────────

@api_bp.route("/api/dashboard/summary")
def dashboard_summary():
    """Aggregate stats for the dashboard."""
    session = get_session()
    try:
        active_contracts = session.query(Contract).filter(Contract.status == "active").count()
        total_clauses = session.query(FXClause).count()
        open_alerts = (
            session.query(Alert)
            .filter(Alert.status.in_(["triggered", "pending_approval"]))
            .count()
        )
        approved_alerts = session.query(Alert).filter(Alert.status == "approved").count()
        sent_alerts = session.query(Alert).filter(Alert.status == "sent").count()

        # Total exposure from open alerts
        alerts = (
            session.query(Alert)
            .filter(Alert.status.in_(["triggered", "pending_approval"]))
            .all()
        )
        total_exposure = sum(float(a.exposure_amount or 0) for a in alerts)

        return jsonify({
            "active_contracts": active_contracts,
            "total_clauses": total_clauses,
            "open_alerts": open_alerts,
            "approved_alerts": approved_alerts,
            "sent_alerts": sent_alerts,
            "total_exposure": round(total_exposure, 2),
        })
    finally:
        session.close()


@api_bp.route("/api/dashboard/exposure-by-pair")
def exposure_by_pair():
    """Exposure breakdown by currency pair."""
    return jsonify(get_total_exposure_by_pair())


# ── Rates ────────────────────────────────────────────────────────────────────

@api_bp.route("/api/rates")
def current_rates():
    """Current rates for all monitored pairs."""
    return jsonify(get_latest_rates())


@api_bp.route("/api/rates/<path:pair>/history")
def rate_history(pair: str):
    """Rate history for a currency pair."""
    days = request.args.get("days", 30, type=int)
    days = max(1, min(days, 365))  # Bound to 1-365 days
    history = get_rate_history(pair, days=days)
    return jsonify(history)


@api_bp.route("/api/rates/refresh", methods=["POST"])
def force_refresh_rates():
    """Force a rate refresh."""
    saved = refresh_rates()
    # Also check thresholds after refresh
    new_alerts = check_all_thresholds()
    return jsonify({
        "rates_updated": len(saved),
        "new_alerts": len(new_alerts),
    })


# ── Predictions ──────────────────────────────────────────────────────────────

@api_bp.route("/api/predictions")
def list_predictions():
    """Get latest predictions."""
    from fx.models import Prediction
    session = get_session()
    try:
        predictions = (
            session.query(Prediction)
            .order_by(Prediction.created_at.desc())
            .limit(20)
            .all()
        )
        return jsonify([p.to_dict() for p in predictions])
    finally:
        session.close()


@api_bp.route("/api/predictions/run", methods=["POST"])
def trigger_predictions():
    """Run predictions for all pairs."""
    threshold = request.json.get("threshold_pct", 5.0) if request.is_json else 5.0
    horizon = request.json.get("horizon_days", 30) if request.is_json else 30
    results = run_all_predictions(threshold_pct=threshold, horizon_days=horizon)
    return jsonify(results)


# ── Audit ────────────────────────────────────────────────────────────────────

@api_bp.route("/api/audit")
def audit_entries():
    """Query audit log."""
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id", type=int)
    limit = request.args.get("limit", 100, type=int)
    limit = max(1, min(limit, 500))  # Bound to 1-500 entries
    entries = get_audit_log(entity_type=entity_type, entity_id=entity_id, limit=limit)
    return jsonify(entries)
