"""
Alert and notification management routes.
"""

from flask import Blueprint, jsonify, render_template, request

from fx.db import get_session
from fx.models import Alert, Contract, FXClause, Transaction
from fx.notifications.generator import generate_notification
from fx.notifications.approval import approve_alert, dismiss_alert, mark_sent

alerts_bp = Blueprint("fx_alerts", __name__)


@alerts_bp.route("/alerts")
def list_alerts():
    """Alert queue page."""
    return render_template("alerts.html")


@alerts_bp.route("/alerts/<int:alert_id>")
def alert_detail(alert_id: int):
    """Alert detail page."""
    return render_template("alert_detail.html", alert_id=alert_id)


@alerts_bp.route("/api/alerts", methods=["GET"])
def api_list_alerts():
    """JSON alert list with optional status filter."""
    status = request.args.get("status")
    session = get_session()
    try:
        query = session.query(Alert).order_by(Alert.created_at.desc())
        if status:
            query = query.filter(Alert.status == status)
        alerts = query.all()
        return jsonify([a.to_dict() for a in alerts])
    finally:
        session.close()


@alerts_bp.route("/api/alerts/<int:alert_id>", methods=["GET"])
def api_alert_detail(alert_id: int):
    """JSON alert detail with clause and contract info."""
    session = get_session()
    try:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return jsonify({"error": "Alert not found"}), 404

        data = alert.to_dict()
        if alert.clause:
            data["clause"] = alert.clause.to_dict()
        return jsonify(data)
    finally:
        session.close()


@alerts_bp.route("/api/alerts/<int:alert_id>/generate-notification", methods=["POST"])
def api_generate_notification(alert_id: int):
    """Generate notification text via Claude API."""
    session = get_session()
    try:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return jsonify({"error": "Alert not found"}), 404

        if alert.status != "triggered":
            return jsonify({"error": f"Cannot generate notification for status '{alert.status}'"}), 400

        clause = session.query(FXClause).filter(FXClause.id == alert.clause_id).first()
        contract = session.query(Contract).filter(Contract.id == alert.contract_id).first()

        # Get transaction volume
        transactions = (
            session.query(Transaction)
            .filter(
                Transaction.contract_id == alert.contract_id,
                Transaction.currency_pair == alert.currency_pair,
            )
            .all()
        )
        total_volume = sum(float(t.volume) for t in transactions) if transactions else 1000000.0

        try:
            notification_text = generate_notification(
                customer_name=contract.customer_name,
                contract_reference=contract.contract_reference,
                currency_pair=alert.currency_pair,
                base_rate=float(alert.base_rate),
                current_rate=float(alert.current_rate),
                deviation_pct=float(alert.deviation_pct),
                threshold_pct=float(clause.threshold_pct),
                adjustment_method=clause.adjustment_method,
                clause_text=clause.clause_text or "",
                volume=total_volume,
                exposure_amount=float(alert.exposure_amount),
                notification_period_days=clause.notification_period_days,
                alert_id=alert_id,
            )

            alert.notification_text = notification_text
            alert.status = "pending_approval"
            session.commit()

            return jsonify({
                "alert_id": alert_id,
                "status": "pending_approval",
                "notification_text": notification_text,
            })
        except Exception as e:
            return jsonify({"error": f"Notification generation failed: {str(e)}"}), 500
    finally:
        session.close()


@alerts_bp.route("/api/alerts/<int:alert_id>/approve", methods=["POST"])
def api_approve_alert(alert_id: int):
    """Approve a notification for sending."""
    approved_by = request.json.get("approved_by", "operator") if request.is_json else "operator"
    try:
        result = approve_alert(alert_id, approved_by)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@alerts_bp.route("/api/alerts/<int:alert_id>/dismiss", methods=["POST"])
def api_dismiss_alert(alert_id: int):
    """Dismiss an alert."""
    dismissed_by = request.json.get("dismissed_by", "operator") if request.is_json else "operator"
    try:
        result = dismiss_alert(alert_id, dismissed_by)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@alerts_bp.route("/api/alerts/<int:alert_id>/send", methods=["POST"])
def api_send_alert(alert_id: int):
    """Mark an approved notification as sent."""
    try:
        result = mark_sent(alert_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
