"""
Mock transaction volume generation.
"""

from fx.exposure.transaction_data import generate_mock_transactions


def seed_transactions(contract_id: int, currency_pairs: list[str]):
    """Generate mock transactions for a contract across its currency pairs."""
    for pair in currency_pairs:
        generate_mock_transactions(contract_id, pair, months=6)
