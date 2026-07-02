"""
FX exposure and delta calculation.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from fx.db import get_session
from fx.models import Transaction
from fx.exposure.formula import FormulaError, evaluate_formula

logger = logging.getLogger(__name__)

# Settlement window per review frequency: exposure is computed over the
# clause's current review period, not the contract's full transaction
# history. Transactions whose period ended on or before the cutoff belong
# to already-settled periods and must not inflate the current exposure.
_PERIOD_WINDOW_DAYS = {
    "monthly": 30,
    "quarterly": 90,
    "annual": 365,
}


def calculate_exposure(
    contract_id: int,
    currency_pair: str,
    base_rate: Decimal,
    current_rate: Decimal,
    session=None,
    clause=None,
) -> Decimal:
    """
    Calculate financial exposure from rate deviation and transaction volume.

    When a clause is supplied, only transactions inside the clause's current
    review period (monthly/quarterly/annual) are counted, and if the clause
    carries a contract-derived formula_expression the exposure is computed
    from that formula. Without a clause, the legacy behavior applies: all
    transactions, default formula volume * |rate_delta| (volume in USD).
    """
    owns_session = session is None
    if owns_session:
        session = get_session()
    try:
        query = session.query(Transaction).filter(
            Transaction.contract_id == contract_id,
            Transaction.currency_pair == currency_pair,
        )

        if clause is not None:
            frequency = (clause.review_frequency or "monthly").lower()
            window = _PERIOD_WINDOW_DAYS.get(frequency)
            if window is None:
                logger.warning(
                    "Unknown review frequency %r on clause %s — using monthly window",
                    frequency, getattr(clause, "id", "?"),
                )
                window = _PERIOD_WINDOW_DAYS["monthly"]
            cutoff = date.today() - timedelta(days=window)
            query = query.filter(Transaction.period_end > cutoff)

        transactions = query.all()

        if not transactions:
            return Decimal("0")

        total_volume = sum((t.volume or Decimal("0") for t in transactions), Decimal("0"))

        if clause is not None and clause.formula_expression:
            try:
                value = evaluate_formula(
                    clause.formula_expression,
                    _formula_variables(total_volume, base_rate, current_rate, clause),
                )
                # Adjustment amounts are non-negative by construction
                return round(max(value, Decimal("0")), 2)
            except FormulaError as e:
                logger.error(
                    "Formula evaluation failed for clause %s (%s): %s — falling back to default",
                    getattr(clause, "id", "?"), currency_pair, e,
                )

        # Default: volume in USD * |rate change| = USD exposure from FX movement
        rate_delta = abs(current_rate - base_rate)
        exposure = total_volume * rate_delta

        return round(exposure, 2)
    finally:
        if owns_session:
            session.close()


def _formula_variables(total_volume: Decimal, base_rate: Decimal, current_rate: Decimal, clause) -> dict[str, Decimal]:
    """Build the variable bindings for a contract formula evaluation.

    Everything stays Decimal end-to-end so monetary results carry no
    binary floating-point drift.
    """
    base = Decimal(str(base_rate))
    current = Decimal(str(current_rate))
    rate_delta = current - base
    deviation = rate_delta / base if base != 0 else Decimal("0")
    return {
        "volume": Decimal(str(total_volume)),
        "base_rate": base,
        "current_rate": current,
        "rate_delta": rate_delta,
        "abs_rate_delta": abs(rate_delta),
        "deviation": deviation,
        "abs_deviation": abs(deviation),
        "threshold": Decimal(str(clause.threshold_pct)) / 100,
    }


def get_total_exposure_by_pair() -> dict[str, float]:
    """Get aggregate exposure across all open alerts, grouped by currency pair."""
    from fx.models import Alert

    session = get_session()
    try:
        alerts = (
            session.query(Alert)
            .filter(Alert.status.in_(["triggered", "pending_approval"]))
            .all()
        )
        exposure_by_pair = {}
        for alert in alerts:
            pair = alert.currency_pair
            exposure_by_pair[pair] = exposure_by_pair.get(pair, 0.0) + float(alert.exposure_amount or 0)
        return exposure_by_pair
    finally:
        session.close()
