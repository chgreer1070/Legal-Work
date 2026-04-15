"""
Unit tests for fx.exposure.calculator.
"""

from datetime import date
from decimal import Decimal

import pytest

from fx.exposure.calculator import calculate_exposure, get_total_exposure_by_pair
from fx.models import Alert, Contract, FXClause, Transaction


def _make_contract_with_clause(session, contract_ref="C-001"):
    contract = Contract(customer_name="Acme", contract_reference=contract_ref)
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
    return contract, clause


def _add_tx(session, contract_id, volume, pair="USD/BRL"):
    session.add(
        Transaction(
            contract_id=contract_id,
            currency_pair=pair,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            volume=Decimal(str(volume)),
            transaction_count=1,
        )
    )


def test_calculate_exposure_returns_zero_when_no_transactions(test_db, db_session):
    contract, _ = _make_contract_with_clause(db_session)
    db_session.commit()

    result = calculate_exposure(
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.25"),
        session=db_session,
    )

    assert result == Decimal("0")


def test_calculate_exposure_positive_delta(test_db, db_session):
    contract, _ = _make_contract_with_clause(db_session)
    _add_tx(db_session, contract.id, 1000)
    db_session.commit()

    result = calculate_exposure(
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.25"),
        session=db_session,
    )

    # 1000 * |5.25 - 5.00| = 250.00
    assert result == Decimal("250.00")


def test_calculate_exposure_uses_abs_for_negative_delta(test_db, db_session):
    contract, _ = _make_contract_with_clause(db_session)
    _add_tx(db_session, contract.id, 1000)
    db_session.commit()

    result = calculate_exposure(
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("4.75"),
        session=db_session,
    )

    assert result == Decimal("250.00")


def test_calculate_exposure_sums_multiple_transactions(test_db, db_session):
    contract, _ = _make_contract_with_clause(db_session)
    _add_tx(db_session, contract.id, 1000)
    _add_tx(db_session, contract.id, 2500)
    _add_tx(db_session, contract.id, 500)
    db_session.commit()

    result = calculate_exposure(
        contract_id=contract.id,
        currency_pair="USD/BRL",
        base_rate=Decimal("5.00"),
        current_rate=Decimal("5.10"),
        session=db_session,
    )

    # (1000 + 2500 + 500) * 0.10 = 400.00
    assert result == Decimal("400.00")


def test_get_total_exposure_by_pair_filters_by_status(test_db, db_session):
    contract, clause = _make_contract_with_clause(db_session)

    def make_alert(pair, status, exposure):
        return Alert(
            clause_id=clause.id,
            contract_id=contract.id,
            currency_pair=pair,
            base_rate=Decimal("5.00"),
            current_rate=Decimal("5.25"),
            deviation_pct=Decimal("5.00"),
            exposure_amount=Decimal(str(exposure)),
            status=status,
        )

    db_session.add_all([
        make_alert("USD/BRL", "triggered", 100),
        make_alert("USD/BRL", "pending_approval", 200),
        make_alert("USD/BRL", "approved", 999),   # excluded
        make_alert("USD/BRL", "sent", 999),       # excluded
        make_alert("USD/BRL", "dismissed", 999),  # excluded
        make_alert("USD/MXN", "triggered", 50),
    ])
    db_session.commit()

    totals = get_total_exposure_by_pair()

    assert totals == {"USD/BRL": 300.0, "USD/MXN": 50.0}
