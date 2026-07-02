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


# ── Health ───────────────────────────────────────────────────────────────────

@api_bp.route("/api/health")
def health():
    """Operational health: database, rate freshness, extraction mode."""
    import os
    from datetime import datetime

    from sqlalchemy import text as sql_text

    from fx.config import RATE_FETCH_INTERVAL_MINUTES

    checks = {}
    status = "ok"
    http_code = 200

    session = get_session()
    try:
        session.execute(sql_text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        status = "error"
        http_code = 503
    finally:
        session.close()

    # Rate freshness: stale rates degrade the service but do not fail it —
    # with the scheduler off (manual mode) rates only move on demand.
    scheduler_enabled = os.environ.get("FX_SCHEDULER_ENABLED", "true").lower() == "true"
    rate_ages = {}
    stale = False
    try:
        for pair, data in get_latest_rates().items():
            fetched = data.get("fetched_at")
            if fetched:
                age_min = (datetime.utcnow() - datetime.fromisoformat(fetched)).total_seconds() / 60
                rate_ages[pair] = round(age_min, 1)
                if scheduler_enabled and age_min > 2 * RATE_FETCH_INTERVAL_MINUTES:
                    stale = True
    except Exception as e:
        checks["rates"] = f"error: {e}"
    checks.setdefault("rates", "stale" if stale else "ok")
    if stale and status == "ok":
        status = "degraded"

    # Extraction mode: Claude when credentials resolve, rule-based otherwise
    try:
        from fx.utils import get_anthropic_client
        get_anthropic_client()
        checks["extraction"] = "claude_api"
    except Exception:
        checks["extraction"] = "rule_based"

    return jsonify({
        "status": status,
        "checks": checks,
        "rate_age_minutes": rate_ages,
        "scheduler_enabled": scheduler_enabled,
    }), http_code


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
