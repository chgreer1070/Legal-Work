"""
Unit tests for fx.notifications.approval — full state-machine coverage.

States:  triggered -> pending_approval -> approved -> sent
                 \-> dismissed              /
                  \-> dismissed  (from pending_approval)

approve_alert: pending_approval -> approved
dismiss_alert: triggered | pending_approval -> dismissed
mark_sent:     approved -> sent
"""

from decimal import Decimal

import pytest

from fx.models import Alert, AuditEntry, Contract, FXClause
from fx.notifications.approval import approve_alert, dismiss_alert, mark_sent


def _make_alert(session, status="triggered"):
    contract = Contract(customer_name="Acme", contract_reference="C-A")
    session.add(contract)
    session.flush()
    clause = FXClause(
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        threshold_pct=Decimal("5.00"),
    )
    session.add(clause)
    session.flush()
    alert = Alert(
        clause_id=clause.id,
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.25"),
        deviation_pct=Decimal("5.00"),
        exposure_amount=Decimal("250.00"),
        status=status,
    )
    session.add(alert)
    session.commit()
    return alert.id


# ---------- approve_alert ------------------------------------------------

def test_approve_alert_from_pending_approval(test_db, db_session):
    alert_id = _make_alert(db_session, status="pending_approval")

    result = approve_alert(alert_id, approved_by="alice")

    assert result["status"] == "approved"
    assert result["approved_by"] == "alice"
    assert result["approved_at"] is not None

    # And the DB actually reflects the transition.
    db_session.expire_all()
    row = db_session.query(Alert).filter(Alert.id == alert_id).one()
    assert row.status == "approved"


def test_approve_alert_not_found_raises(test_db, db_session):
    with pytest.raises(ValueError, match="not found"):
        approve_alert(99999)


@pytest.mark.parametrize("bad_status", ["triggered", "approved", "sent", "dismissed"])
def test_approve_alert_rejects_invalid_from_state(test_db, db_session, bad_status):
    alert_id = _make_alert(db_session, status=bad_status)

    with pytest.raises(ValueError, match="cannot be approved"):
        approve_alert(alert_id)


def test_approve_alert_writes_audit_entry(test_db, db_session):
    alert_id = _make_alert(db_session, status="pending_approval")
    approve_alert(alert_id, approved_by="bob")

    db_session.expire_all()
    entries = (
        db_session.query(AuditEntry)
        .filter(
            AuditEntry.entity_type == "alert",
            AuditEntry.entity_id == alert_id,
            AuditEntry.event_type == "notification_approved",
        )
        .all()
    )
    assert len(entries) == 1
    assert entries[0].actor == "bob"


# ---------- dismiss_alert -----------------------------------------------

@pytest.mark.parametrize("from_status", ["triggered", "pending_approval"])
def test_dismiss_alert_valid_transitions(test_db, db_session, from_status):
    alert_id = _make_alert(db_session, status=from_status)
    result = dismiss_alert(alert_id)
    assert result["status"] == "dismissed"


def test_dismiss_alert_not_found_raises(test_db, db_session):
    with pytest.raises(ValueError, match="not found"):
        dismiss_alert(99999)


@pytest.mark.parametrize("bad_status", ["sent", "dismissed", "approved"])
def test_dismiss_alert_rejects_invalid_from_state(test_db, db_session, bad_status):
    alert_id = _make_alert(db_session, status=bad_status)
    with pytest.raises(ValueError, match="cannot be dismissed"):
        dismiss_alert(alert_id)


# ---------- mark_sent ---------------------------------------------------

def test_mark_sent_from_approved(test_db, db_session):
    alert_id = _make_alert(db_session, status="approved")
    result = mark_sent(alert_id)
    assert result["status"] == "sent"


def test_mark_sent_not_found_raises(test_db, db_session):
    with pytest.raises(ValueError, match="not found"):
        mark_sent(99999)


@pytest.mark.parametrize(
    "bad_status", ["triggered", "pending_approval", "sent", "dismissed"]
)
def test_mark_sent_rejects_invalid_from_state(test_db, db_session, bad_status):
    alert_id = _make_alert(db_session, status=bad_status)
    with pytest.raises(ValueError, match="must be approved"):
        mark_sent(alert_id)


def test_mark_sent_writes_audit_entry(test_db, db_session):
    alert_id = _make_alert(db_session, status="approved")
    mark_sent(alert_id)

    db_session.expire_all()
    entry = (
        db_session.query(AuditEntry)
        .filter(
            AuditEntry.entity_type == "alert",
            AuditEntry.entity_id == alert_id,
            AuditEntry.event_type == "notification_sent",
        )
        .one()
    )
    assert entry.actor == "system"
