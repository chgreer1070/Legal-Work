"""
Mock transaction data generator for MVP.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from fx.db import get_session
from fx.models import Transaction


def generate_mock_transactions(contract_id: int, currency_pair: str, months: int = 6):
    """Generate plausible monthly transaction volumes for a contract."""
    session = get_session()
    try:
        existing = (
            session.query(Transaction)
            .filter(
                Transaction.contract_id == contract_id,
                Transaction.currency_pair == currency_pair,
            )
            .count()
        )
        if existing > 0:
            return

        today = date.today()
        base_volume = random.uniform(500000, 5000000)

        for i in range(months):
            period_end = today - timedelta(days=30 * i)
            period_start = period_end - timedelta(days=30)

            # Add some variance
            volume = base_volume * random.uniform(0.8, 1.2)
            count = random.randint(50, 500)

            txn = Transaction(
                contract_id=contract_id,
                currency_pair=currency_pair,
                period_start=period_start,
                period_end=period_end,
                volume=Decimal(str(round(volume, 2))),
                transaction_count=count,
            )
            session.add(txn)

        session.commit()
    finally:
        session.close()
