"""
Unit tests for fx.monitoring.threshold_checker.check_all_thresholds.

Covers the core monitoring loop: breach detection, exposure recording, the
no-breach / exact-threshold boundary, the skip paths (zero base rate, missing
rate, inactive contract), open-alert dedup, and the audit write.
"""

from datetime import date
from decimal import Decimal

import pytest

from fx.models import Alert, AuditEntry, Contract, FXClause, FXRate, Transaction
from fx.monitoring.threshold_checker import check_all_thresholds


def _make_active_contract_with_clause(
    session, ref="C-001", pair="USD/BRL", base="5.00", threshold="5.00"
):
    contract = Contract(customer_name="Acme", contract_reference=ref, status="active")
    session.add(contract)
    session.flush()
    clause = FXClause(
        contract_id=contract.id,
        currency_pair=pair,
        base_rate=Decimal(base),
        threshold_pct=Decimal(threshold),
    )
    session.add(clause)
    session.flush()
    return contract, clause


def _seed_rate(session, pair, rate):
    session.add(FXRate(currency_pair=pair, rate=Decimal(str(rate)), source="test"))


def test_breach_creates_single_alert(test_db, db_session):
    _, clause = _make_active_contract_with_clause(db_session)
    _seed_rate(db_session, "USD/BRL", "5.50")  # 10% > 5% threshold
    db_session.commit()

    result = check_all_thresholds()

    assert len(result) == 1
    assert result[0]["currency_pair"] == "USD/BRL"
    assert result[0]["status"] == "triggered"
    assert result[0]["deviation_pct"] == pytest.approx(10.0)

    alerts = db_session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].clause_id == clause.id


def test_breach_records_exposure_from_transactions(test_db, db_session):
    contract, _ = _make_active_contract_with_clause(db_session)
    db_session.add(
        Transaction(
            contract_id=contract.id,
            currency_pair="USD/BRL",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            volume=Decimal("1000"),
            transaction_count=1,
        )
    )
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert len(result) == 1
    # 1000 * |5.50 - 5.00| = 500.00
    assert result[0]["exposure_amount"] == pytest.approx(500.0)


def test_no_alert_below_threshold(test_db, db_session):
    _make_active_contract_with_clause(db_session)
    _seed_rate(db_session, "USD/BRL", "5.10")  # 2% < 5%
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0


def test_no_alert_at_exact_threshold(test_db, db_session):
    # Breach requires deviation strictly greater than the threshold (uses `>`).
    _make_active_contract_with_clause(db_session)
    _seed_rate(db_session, "USD/BRL", "5.25")  # exactly 5%
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0


def test_favorable_move_also_triggers(test_db, db_session):
    """Documents the current direction-agnostic behavior.

    check_all_thresholds compares abs(deviation), so a *favorable* move breaches
    the threshold exactly like an adverse one. The audit flagged this as a
    limitation (FXClause has no direction field); this test pins the behavior so
    that a future directional fix updates it deliberately rather than silently.
    """
    _make_active_contract_with_clause(db_session)
    _seed_rate(db_session, "USD/BRL", "4.50")  # -10% move
    db_session.commit()

    result = check_all_thresholds()

    assert len(result) == 1
    assert result[0]["deviation_pct"] == pytest.approx(10.0)


def test_zero_base_rate_skipped(test_db, db_session):
    # A zero base rate would divide by zero; the clause must be skipped.
    _make_active_contract_with_clause(db_session, base="0")
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0


def test_pair_without_rate_skipped(test_db, db_session):
    # The clause's pair has no rate, but another pair does, so latest_rates is
    # non-empty and we exercise the per-clause skip (not the early return).
    _make_active_contract_with_clause(db_session, ref="C-EURGBP", pair="EUR/GBP")
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0


def test_inactive_contract_skipped(test_db, db_session):
    contract = Contract(
        customer_name="Acme",
        contract_reference="C-INACTIVE",
        status="pending_extraction",
    )
    db_session.add(contract)
    db_session.flush()
    db_session.add(
        FXClause(
            contract_id=contract.id,
            currency_pair="USD/BRL",
            base_rate=Decimal("5.00"),
            threshold_pct=Decimal("5.00"),
        )
    )
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0


def test_existing_open_alert_is_deduped(test_db, db_session):
    contract, clause = _make_active_contract_with_clause(db_session)
    db_session.add(
        Alert(
            clause_id=clause.id,
            contract_id=contract.id,
            currency_pair="USD/BRL",
            base_rate=Decimal("5.00"),
            current_rate=Decimal("5.40"),
            deviation_pct=Decimal("8.00"),
            exposure_amount=Decimal("0"),
            status="pending_approval",
        )
    )
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 1  # no duplicate created


def test_closed_alert_does_not_block_new_alert(test_db, db_session):
    contract, clause = _make_active_contract_with_clause(db_session)
    db_session.add(
        Alert(
            clause_id=clause.id,
            contract_id=contract.id,
            currency_pair="USD/BRL",
            base_rate=Decimal("5.00"),
            current_rate=Decimal("5.40"),
            deviation_pct=Decimal("8.00"),
            exposure_amount=Decimal("0"),
            status="dismissed",
        )
    )
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert len(result) == 1
    assert db_session.query(Alert).count() == 2


def test_audit_entry_written_on_breach(test_db, db_session):
    _make_active_contract_with_clause(db_session)
    _seed_rate(db_session, "USD/BRL", "5.50")
    db_session.commit()

    result = check_all_thresholds()

    assert len(result) == 1
    entries = (
        db_session.query(AuditEntry)
        .filter(AuditEntry.event_type == "alert_triggered")
        .all()
    )
    assert len(entries) == 1
    assert entries[0].entity_type == "alert"
    assert entries[0].entity_id == result[0]["id"]


def test_no_rates_returns_empty(test_db, db_session):
    _make_active_contract_with_clause(db_session)
    db_session.commit()  # no FXRate rows seeded

    result = check_all_thresholds()

    assert result == []
    assert db_session.query(Alert).count() == 0
