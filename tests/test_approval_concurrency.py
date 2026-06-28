"""
Regression test for the approval-state-machine race fix.

Before the conditional-UPDATE fix, two threads racing to approve (or mix
approve/dismiss) the same alert could both commit their transitions,
violating the state-machine invariant. This test asserts exactly one
transition succeeds and the rest raise ValueError.
"""

import threading
from decimal import Decimal

import pytest

from fx.models import Alert, AuditEntry, Contract, FXClause
from fx.notifications.approval import approve_alert, dismiss_alert


def _seed_alert(session, status="pending_approval") -> int:
    contract = Contract(customer_name="Race Test", contract_reference="R-1")
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
        exposure_amount=Decimal("0"),
        status=status,
    )
    session.add(alert)
    session.commit()
    return alert.id


def test_concurrent_approvals_one_wins(test_db, db_session):
    alert_id = _seed_alert(db_session)

    successes: list[int] = []
    rejections: list[str] = []
    lock = threading.Lock()

    def worker(i: int):
        try:
            approve_alert(alert_id, approved_by=f"thread_{i}")
            with lock:
                successes.append(i)
        except ValueError as e:
            with lock:
                rejections.append(str(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 1, f"exactly one approval should win, got {len(successes)}"
    assert len(rejections) == 9
    assert all("cannot be approved" in msg for msg in rejections)

    db_session.expire_all()
    row = db_session.query(Alert).filter(Alert.id == alert_id).one()
    assert row.status == "approved"

    # Exactly one audit entry for the single successful transition.
    audit_count = (
        db_session.query(AuditEntry)
        .filter(
            AuditEntry.entity_type == "alert",
            AuditEntry.entity_id == alert_id,
            AuditEntry.event_type == "notification_approved",
        )
        .count()
    )
    assert audit_count == 1


def test_concurrent_approve_vs_dismiss_one_wins(test_db, db_session):
    """Mixing approve and dismiss on the same pending_approval alert must
    still produce exactly one terminal transition."""
    alert_id = _seed_alert(db_session)

    outcomes: list[str] = []
    lock = threading.Lock()

    def approver(i: int):
        try:
            approve_alert(alert_id, approved_by=f"a{i}")
            with lock:
                outcomes.append("approved")
        except ValueError:
            with lock:
                outcomes.append("approve_rejected")

    def dismisser(i: int):
        try:
            dismiss_alert(alert_id, dismissed_by=f"d{i}")
            with lock:
                outcomes.append("dismissed")
        except ValueError:
            with lock:
                outcomes.append("dismiss_rejected")

    threads = []
    for i in range(5):
        threads.append(threading.Thread(target=approver, args=(i,)))
        threads.append(threading.Thread(target=dismisser, args=(i,)))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [o for o in outcomes if o in ("approved", "dismissed")]
    assert len(successes) == 1, f"expected 1 winning transition, got {successes}"

    db_session.expire_all()
    row = db_session.query(Alert).filter(Alert.id == alert_id).one()
    assert row.status in ("approved", "dismissed")
    assert row.status == successes[0]


@pytest.mark.parametrize("parallel", [1, 5, 20])
def test_approve_is_idempotent_under_any_fan_out(test_db, db_session, parallel):
    """Regardless of how many threads pile on, the invariant holds."""
    alert_id = _seed_alert(db_session)

    wins = []
    lock = threading.Lock()

    def worker(i: int):
        try:
            approve_alert(alert_id, approved_by=f"t{i}")
            with lock:
                wins.append(i)
        except ValueError:
            pass

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(parallel)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(wins) == 1
