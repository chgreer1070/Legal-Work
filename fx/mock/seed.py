"""
Seed the database with demo data for the FX Recovery System.

Usage:
    python -m fx.mock.seed
"""

from decimal import Decimal

from fx.db import init_db, get_session
from fx.models import Contract, FXClause
from fx.mock.sample_contracts import SAMPLE_CONTRACTS
from fx.mock.sample_rates import seed_rates
from fx.mock.sample_transactions import seed_transactions
from fx.audit.logger import log_event

# Pre-defined clause extractions for demo data (bypassing Claude API)
DEMO_CLAUSES = {
    "MSA-2025-0142": [
        {
            "currency_pair": "USD/BRL",
            "base_rate": 5.0500,
            "threshold_pct": 3.0,
            "review_frequency": "monthly",
            "adjustment_method": "full_passthrough",
            "notification_period_days": 30,
            "clause_text": "In the event that the prevailing market exchange rate for USD/BRL deviates from the base rate of 5.0500 by more than three percent (3%), either party may request a price adjustment.",
            "confidence_score": 0.95,
        },
        {
            "currency_pair": "USD/MXN",
            "base_rate": 17.5000,
            "threshold_pct": 5.0,
            "review_frequency": "quarterly",
            "adjustment_method": "shared",
            "notification_period_days": 60,
            "clause_text": "If the USD/MXN rate deviates from the base rate of 17.5000 by more than five percent (5%), pricing shall be adjusted on a quarterly basis using a shared adjustment method.",
            "confidence_score": 0.92,
        },
    ],
    "SOW-2025-0089": [
        {
            "currency_pair": "USD/CNY",
            "base_rate": 7.2500,
            "threshold_pct": 4.0,
            "review_frequency": "quarterly",
            "adjustment_method": "capped",
            "notification_period_days": 45,
            "clause_text": "Should the USD/CNY exchange rate move beyond a four percent (4%) threshold from the base rate of 7.2500, the Provider reserves the right to adjust unit pricing.",
            "confidence_score": 0.93,
        },
    ],
    "MFG-2024-0215": [
        {
            "currency_pair": "USD/BRL",
            "base_rate": 4.9800,
            "threshold_pct": 5.0,
            "review_frequency": "semi-annual",
            "adjustment_method": "full_passthrough",
            "notification_period_days": 90,
            "clause_text": "If the USD/BRL exchange rate deviates by more than five percent (5.0%) from the base rate, a price review shall be triggered.",
            "confidence_score": 0.96,
        },
    ],
}


def seed_all():
    """Seed the complete demo dataset."""
    print("[Seed] Initializing database...")
    init_db()

    session = get_session()
    try:
        # Check if already seeded
        existing = session.query(Contract).count()
        if existing > 0:
            print(f"[Seed] Database already has {existing} contracts. Skipping seed.")
            return

        print("[Seed] Creating sample contracts and clauses...")
        for contract_data in SAMPLE_CONTRACTS:
            contract = Contract(
                customer_name=contract_data["customer_name"],
                contract_reference=contract_data["contract_reference"],
                file_path=contract_data.get("filepath", ""),
                raw_text=contract_data["content"],
                status="active",
            )
            session.add(contract)
            session.flush()

            ref = contract_data["contract_reference"]
            clauses_data = DEMO_CLAUSES.get(ref, [])
            currency_pairs = []

            for cd in clauses_data:
                clause = FXClause(
                    contract_id=contract.id,
                    currency_pair=cd["currency_pair"],
                    base_rate=Decimal(str(cd["base_rate"])),
                    threshold_pct=Decimal(str(cd["threshold_pct"])),
                    review_frequency=cd["review_frequency"],
                    adjustment_method=cd["adjustment_method"],
                    notification_period_days=cd["notification_period_days"],
                    clause_text=cd["clause_text"],
                    confidence_score=cd["confidence_score"],
                )
                session.add(clause)
                currency_pairs.append(cd["currency_pair"])

            session.commit()

            # Generate mock transactions
            print(f"  - {contract_data['customer_name']}: {len(clauses_data)} clauses, generating transactions...")
            seed_transactions(contract.id, currency_pairs)

            log_event(
                event_type="seed_data",
                entity_type="contract",
                entity_id=contract.id,
                action=f"Seeded contract: {contract_data['customer_name']}",
                actor="seed_script",
            )

        print("[Seed] Seeding historical FX rates (90 days)...")
        seed_rates()

        print("[Seed] Done! Database seeded with:")
        print(f"  - {len(SAMPLE_CONTRACTS)} contracts")
        print(f"  - {sum(len(v) for v in DEMO_CLAUSES.values())} FX clauses")
        print(f"  - 90 days of historical rates for 3 currency pairs")
        print(f"  - Mock transaction data for each contract")

    finally:
        session.close()


if __name__ == "__main__":
    seed_all()
