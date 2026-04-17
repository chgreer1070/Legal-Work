"""
Core business logic: compare current FX rates against contract thresholds.
"""

from decimal import Decimal

from fx.db import get_session
from fx.models import Alert, Contract, FXClause
from fx.monitoring.rate_cache import get_latest_rates
from fx.exposure.calculator import calculate_exposure
from fx.audit.logger import log_event


def check_all_thresholds() -> list[dict]:
    """
    Compare current rates against all active contract FX clauses.
    Create Alert records when deviation exceeds threshold.
    """
    latest_rates = get_latest_rates()
    if not latest_rates:
        return []

    session = get_session()
    new_alerts = []
    try:
        active_clauses = (
            session.query(FXClause)
            .join(Contract)
            .filter(Contract.status == "active")
            .all()
        )

        for clause in active_clauses:
            pair = clause.currency_pair
            if pair not in latest_rates:
                continue

            current_rate = Decimal(str(latest_rates[pair]["rate"]))
            base_rate = clause.base_rate

            if base_rate == 0:
                continue

            deviation_pct = abs((current_rate - base_rate) / base_rate) * 100

            if deviation_pct > clause.threshold_pct:
                # Check if there's already an open alert for this clause
                existing = (
                    session.query(Alert)
                    .filter(
                        Alert.clause_id == clause.id,
                        Alert.status.in_(["triggered", "pending_approval"]),
                    )
                    .first()
                )
                if existing:
                    continue

                # Calculate exposure
                exposure = calculate_exposure(
                    clause.contract_id, pair, base_rate, current_rate, session=session
                )

                alert = Alert(
                    clause_id=clause.id,
                    contract_id=clause.contract_id,
                    currency_pair=pair,
                    base_rate=base_rate,
                    current_rate=current_rate,
                    deviation_pct=deviation_pct,
                    exposure_amount=exposure,
                    status="triggered",
                )
                session.add(alert)
                session.flush()

                log_event(
                    event_type="alert_triggered",
                    entity_type="alert",
                    entity_id=alert.id,
                    action=f"Threshold breached: {pair} at {float(deviation_pct):.2f}% (threshold: {float(clause.threshold_pct)}%)",
                    details={
                        "currency_pair": pair,
                        "base_rate": float(base_rate),
                        "current_rate": float(current_rate),
                        "deviation_pct": float(deviation_pct),
                        "threshold_pct": float(clause.threshold_pct),
                        "exposure_amount": float(exposure),
                    },
                    session=session,
                )

                new_alerts.append(alert.to_dict())

        session.commit()
    finally:
        session.close()

    return new_alerts
