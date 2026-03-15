"""
Human-in-the-loop approval workflow for notifications.
"""

from datetime import datetime

from fx.db import get_session
from fx.models import Alert
from fx.audit.logger import log_event


def approve_alert(alert_id: int, approved_by: str = "operator") -> dict:
    """Approve a notification for sending."""
    session = get_session()
    try:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status != "pending_approval":
            raise ValueError(f"Alert {alert_id} cannot be approved from status '{alert.status}'")

        alert.status = "approved"
        alert.approved_by = approved_by
        alert.approved_at = datetime.utcnow()

        log_event(
            event_type="notification_approved",
            entity_type="alert",
            entity_id=alert_id,
            action=f"Notification approved by {approved_by}",
            actor=approved_by,
            details={"previous_status": "pending_approval"},
            session=session,
        )

        session.commit()
        result = alert.to_dict()
    finally:
        session.close()
    return result


def dismiss_alert(alert_id: int, dismissed_by: str = "operator") -> dict:
    """Dismiss an alert without sending notification."""
    session = get_session()
    try:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status in ("sent", "dismissed", "approved"):
            raise ValueError(f"Alert {alert_id} cannot be dismissed from status '{alert.status}'")

        alert.status = "dismissed"

        log_event(
            event_type="alert_dismissed",
            entity_type="alert",
            entity_id=alert_id,
            action=f"Alert dismissed by {dismissed_by}",
            actor=dismissed_by,
            session=session,
        )

        session.commit()
        result = alert.to_dict()
    finally:
        session.close()
    return result


def mark_sent(alert_id: int) -> dict:
    """Mark an approved notification as sent."""
    session = get_session()
    try:
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        if alert.status != "approved":
            raise ValueError(f"Alert {alert_id} must be approved before marking as sent")

        alert.status = "sent"

        log_event(
            event_type="notification_sent",
            entity_type="alert",
            entity_id=alert_id,
            action="Notification marked as sent",
            actor="system",
            session=session,
        )

        session.commit()
        result = alert.to_dict()
    finally:
        session.close()
    return result
