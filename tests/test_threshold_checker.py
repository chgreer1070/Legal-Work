"""
Unit tests for fx.monitoring.threshold_checker.check_all_thresholds.

Covers the latent invariants the auditor flagged:
  * zero base_rate must NOT divide by zero (the clause is skipped)
  * an already-open alert must suppress a new duplicate on the next check
  * inactive contracts must not produce alerts even if their rate has moved
"""

from decimal import Decimal

import pytest

from fx.models import Alert, Contract, FXClause, FXRate
from fx.monitoring.threshold_checker import check_all_thresholds


def _make_contract_with_clause(session, *, base_rate="5.00", threshold_pct="5.00",
                               currency_pair="USD/BRL", contract_status="active"):
    contract = Contract(
        customer_name="Acme Test",
        contract_reference=f"TC-{currency_pair.replace('/', '')}-{base_rate}-{contract_status}",
        status=contract_status,
    )
    session.add(contract)
    session.flush()
    clause = FXClause(
        contract_id=contract.id,
        currency_pair=currency_pair,
        base_rate=Decimal(base_rate),
        threshold_pct=Decimal(threshold_pct),
    )
    session.add(clause)
    session.flush()
    return contract, clause


def _seed_rate(session, pair: str, rate: str):
    session.add(FXRate(currency_pair=pair, rate=Decimal(rate), source="test"))


def test_zero_base_rate_is_skipped_without_divide_by_zero(test_db, db_session):
    """base_rate=0 must short-circuit — the old code would divide by zero."""
    _make_contract_with_clause(db_session, base_rate="0.00", currency_pair="USD/ZWL")
    _seed_rate(db_session, "USD/ZWL", "1.2345")
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert new_alerts == []
    db_session.expire_all()
    assert db_session.query(Alert).count() == 0


def test_breach_creates_an_alert(test_db, db_session):
    """Sanity check that the happy path still triggers an alert."""
    _make_contract_with_clause(db_session, base_rate="5.00", threshold_pct="1.00")
    _seed_rate(db_session, "USD/BRL", "5.25")  # 5% deviation, threshold is 1%
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert len(new_alerts) == 1
    db_session.expire_all()
    assert db_session.query(Alert).count() == 1


@pytest.mark.parametrize("existing_status", ["triggered", "pending_approval"])
def test_existing_open_alert_suppresses_duplicate(test_db, db_session, existing_status):
    """An open alert for the same clause should prevent a second alert."""
    contract, clause = _make_contract_with_clause(
        db_session, base_rate="5.00", threshold_pct="1.00"
    )
    _seed_rate(db_session, "USD/BRL", "5.25")
    db_session.add(Alert(
        clause_id=clause.id,
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.25"),
        deviation_pct=Decimal("5.00"),
        exposure_amount=Decimal("0"),
        status=existing_status,
    ))
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert new_alerts == []
    db_session.expire_all()
    assert db_session.query(Alert).count() == 1  # still just the pre-existing one


@pytest.mark.parametrize("terminal_status", ["approved", "sent", "dismissed"])
def test_terminal_alert_does_not_suppress_new_alert(test_db, db_session, terminal_status):
    """Alerts in terminal states don't block the next breach from firing."""
    contract, clause = _make_contract_with_clause(
        db_session, base_rate="5.00", threshold_pct="1.00"
    )
    _seed_rate(db_session, "USD/BRL", "5.25")
    db_session.add(Alert(
        clause_id=clause.id,
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.25"),
        deviation_pct=Decimal("5.00"),
        exposure_amount=Decimal("0"),
        status=terminal_status,
    ))
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert len(new_alerts) == 1  # a new alert, on top of the closed one
    db_session.expire_all()
    assert db_session.query(Alert).count() == 2


def test_inactive_contracts_do_not_trigger_alerts(test_db, db_session):
    """Only contracts with status='active' should be considered."""
    _make_contract_with_clause(
        db_session,
        base_rate="5.00",
        threshold_pct="1.00",
        contract_status="expired",
    )
    _seed_rate(db_session, "USD/BRL", "5.25")
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert new_alerts == []
    db_session.expire_all()
    assert db_session.query(Alert).count() == 0


def test_no_matching_rate_means_no_alert(test_db, db_session):
    """Clause for USD/BRL + rate for EUR/USD only → no alert, no crash."""
    _make_contract_with_clause(db_session, currency_pair="USD/BRL")
    _seed_rate(db_session, "EUR/USD", "1.10")
    db_session.commit()

    new_alerts = check_all_thresholds()

    assert new_alerts == []


def test_no_rates_at_all_returns_empty(test_db, db_session):
    """Empty rate cache → no-op, no exception."""
    _make_contract_with_clause(db_session)
    db_session.commit()

    assert check_all_thresholds() == []
