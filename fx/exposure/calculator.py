"""
FX exposure and delta calculation.
"""

from decimal import Decimal

from fx.db import get_session
from fx.models import Transaction


def calculate_exposure(
    contract_id: int,
    currency_pair: str,
    base_rate: Decimal,
    current_rate: Decimal,
    session=None,
) -> Decimal:
    """
    Calculate financial exposure (delta) from rate deviation and transaction volume.

    Exposure = transaction_volume * (current_rate - base_rate) / base_rate
    """
    owns_session = session is None
    if owns_session:
        session = get_session()
    try:
        # Get total transaction volume for this contract and pair
        transactions = (
            session.query(Transaction)
            .filter(
                Transaction.contract_id == contract_id,
                Transaction.currency_pair == currency_pair,
            )
            .all()
        )

        total_volume = sum(t.volume for t in transactions) if transactions else Decimal("1000000")

        if base_rate == 0:
            return Decimal("0")

        rate_delta = current_rate - base_rate
        exposure = total_volume * rate_delta / base_rate

        return abs(round(exposure, 2))
    finally:
        if owns_session:
            session.close()


def get_total_exposure_by_pair() -> dict[str, float]:
    """Get aggregate exposure across all open alerts, grouped by currency pair."""
    from fx.models import Alert

    session = get_session()
    try:
        alerts = (
            session.query(Alert)
            .filter(Alert.status.in_(["triggered", "notification_drafted", "pending_approval"]))
            .all()
        )
        exposure_by_pair = {}
        for alert in alerts:
            pair = alert.currency_pair
            exposure_by_pair[pair] = exposure_by_pair.get(pair, 0.0) + float(alert.exposure_amount)
        return exposure_by_pair
    finally:
        session.close()
