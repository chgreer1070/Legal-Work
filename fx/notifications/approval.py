"""
Human-in-the-loop approval workflow for notifications.

Transitions are applied atomically via a conditional UPDATE
(`UPDATE ... WHERE id=? AND status=<expected>`) so that two concurrent
callers racing on the same alert cannot both succeed.
"""

from datetime import datetime

from fx.db import get_session
from fx.models import Alert
from fx.audit.logger import log_event


def _transition(alert_id: int, from_statuses, to_status: str, extra_columns=None,
                rejection_msg: str = "cannot be transitioned"):
    """
    Atomically move an alert from one of ``from_statuses`` to ``to_status``.

    Raises ValueError if the alert is missing or not in an allowed from-state.
    Returns the refreshed ORM row so the caller can write an audit entry and
    serialize the result within the same session/transaction.
    """
    if isinstance(from_statuses, str):
        from_statuses = [from_statuses]

    session = get_session()
    try:
        values = {"status": to_status}
        if extra_columns:
            values.update(extra_columns)

        rowcount = (
            session.query(Alert)
            .filter(Alert.id == alert_id, Alert.status.in_(from_statuses))
            .update(values, synchronize_session=False)
        )

        if rowcount == 0:
            alert = session.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                raise ValueError(f"Alert {alert_id} not found")
            raise ValueError(
                f"Alert {alert_id} {rejection_msg} from status '{alert.status}'"
            )

        alert = session.query(Alert).filter(Alert.id == alert_id).one()
        return session, alert
    except Exception:
        session.close()
        raise


def approve_alert(alert_id: int, approved_by: str = "operator") -> dict:
    """Approve a notification for sending."""
    session, alert = _transition(
        alert_id,
        from_statuses="pending_approval",
        to_status="approved",
        extra_columns={"approved_by": approved_by, "approved_at": datetime.utcnow()},
        rejection_msg="cannot be approved",
    )
    try:
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
        return alert.to_dict()
    finally:
        session.close()


def dismiss_alert(alert_id: int, dismissed_by: str = "operator") -> dict:
    """Dismiss an alert without sending notification."""
    session, alert = _transition(
        alert_id,
        from_statuses=["triggered", "pending_approval"],
        to_status="dismissed",
        rejection_msg="cannot be dismissed",
    )
    try:
        log_event(
            event_type="alert_dismissed",
            entity_type="alert",
            entity_id=alert_id,
            action=f"Alert dismissed by {dismissed_by}",
            actor=dismissed_by,
            session=session,
        )
        session.commit()
        return alert.to_dict()
    finally:
        session.close()


def mark_sent(alert_id: int) -> dict:
    """Mark an approved notification as sent."""
    try:
        session, alert = _transition(
            alert_id,
            from_statuses="approved",
            to_status="sent",
            rejection_msg="internal",
        )
    except ValueError as e:
        # Preserve the historical "must be approved before marking as sent" message
        # for the not-in-'approved' case.
        msg = str(e)
        if "not found" in msg:
            raise
        raise ValueError(f"Alert {alert_id} must be approved before marking as sent") from None

    try:
        log_event(
            event_type="notification_sent",
            entity_type="alert",
            entity_id=alert_id,
            action="Notification marked as sent",
            actor="system",
            session=session,
        )
        session.commit()
        return alert.to_dict()
    finally:
        session.close()
