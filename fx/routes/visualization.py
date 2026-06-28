"""
3D contract visualization routes and graph data API.
"""

import math

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from fx.db import get_session
from fx.models import Alert, Contract, FXClause

viz_bp = Blueprint("fx_viz", __name__)


def _risk_level(clause, alert_count):
    if alert_count > 0 or float(clause.threshold_pct) <= 3.0:
        return "high"
    if float(clause.threshold_pct) <= 5.0:
        return "medium"
    return "low"


RISK_COLORS = {
    "high": "#e74c3c",
    "medium": "#f39c12",
    "low": "#2ecc71",
}

ALERT_STATUS_COLORS = {
    "triggered": "#e74c3c",
    "notification_drafted": "#f39c12",
    "pending_approval": "#f39c12",
    "approved": "#a29bfe",
    "sent": "#a29bfe",
    "dismissed": "#95a5a6",
}


def build_graph(contracts):
    nodes = []
    links = []
    seen_pairs = {}

    for contract in contracts:
        contract_node_id = f"contract-{contract.id}"
        nodes.append({
            "id": contract_node_id,
            "type": "contract",
            "label": contract.customer_name,
            "val": 20,
            "color": "#0f3460",
            "details": {
                "customer_name": contract.customer_name,
                "contract_reference": contract.contract_reference,
                "status": contract.status,
                "clause_count": len(contract.clauses) if contract.clauses else 0,
                "id": contract.id,
            },
        })

        for clause in (contract.clauses or []):
            clause_node_id = f"clause-{clause.id}"
            alert_count = len(clause.alerts) if clause.alerts else 0
            risk = _risk_level(clause, alert_count)

            nodes.append({
                "id": clause_node_id,
                "type": "clause",
                "label": f"{clause.currency_pair} {float(clause.threshold_pct)}%",
                "val": 12,
                "color": RISK_COLORS[risk],
                "risk": risk,
                "details": {
                    "id": clause.id,
                    "currency_pair": clause.currency_pair,
                    "base_rate": float(clause.base_rate),
                    "threshold_pct": float(clause.threshold_pct),
                    "review_frequency": clause.review_frequency,
                    "adjustment_method": clause.adjustment_method,
                    "notification_period_days": clause.notification_period_days,
                    "clause_text": clause.clause_text,
                    "confidence_score": clause.confidence_score,
                },
            })
            links.append({
                "source": contract_node_id,
                "target": clause_node_id,
                "label": "contains",
                "type": "contains",
            })

            pair = clause.currency_pair
            if pair not in seen_pairs:
                pair_node_id = f"pair-{pair}"
                seen_pairs[pair] = pair_node_id
                nodes.append({
                    "id": pair_node_id,
                    "type": "currency",
                    "label": pair,
                    "val": 8,
                    "color": "#f39c12",
                    "details": {"currency_pair": pair},
                })
            links.append({
                "source": clause_node_id,
                "target": seen_pairs[pair],
                "label": "monitors",
                "type": "monitors",
            })

            nodes.append({
                "id": f"oblig-{clause.id}-freq",
                "type": "obligation",
                "label": f"Review: {clause.review_frequency}",
                "val": 6,
                "color": "#2ecc71",
                "details": {"obligation": "review_frequency", "value": clause.review_frequency},
            })
            links.append({
                "source": clause_node_id,
                "target": f"oblig-{clause.id}-freq",
                "label": "requires",
                "type": "requires",
            })

            nodes.append({
                "id": f"oblig-{clause.id}-notice",
                "type": "obligation",
                "label": f"Notice: {clause.notification_period_days}d",
                "val": 6,
                "color": "#2ecc71",
                "details": {"obligation": "notification_period", "value": f"{clause.notification_period_days} days"},
            })
            links.append({
                "source": clause_node_id,
                "target": f"oblig-{clause.id}-notice",
                "label": "requires",
                "type": "requires",
            })

            nodes.append({
                "id": f"oblig-{clause.id}-method",
                "type": "obligation",
                "label": f"Method: {clause.adjustment_method}",
                "val": 6,
                "color": "#2ecc71",
                "details": {"obligation": "adjustment_method", "value": clause.adjustment_method},
            })
            links.append({
                "source": clause_node_id,
                "target": f"oblig-{clause.id}-method",
                "label": "requires",
                "type": "requires",
            })

            for alert in (clause.alerts or []):
                alert_node_id = f"alert-{alert.id}"
                nodes.append({
                    "id": alert_node_id,
                    "type": "alert",
                    "label": f"Alert: {float(alert.deviation_pct):.1f}% deviation",
                    "val": 10,
                    "color": ALERT_STATUS_COLORS.get(alert.status, "#e74c3c"),
                    "pulsing": alert.status == "triggered",
                    "details": {
                        "id": alert.id,
                        "currency_pair": alert.currency_pair,
                        "base_rate": float(alert.base_rate),
                        "current_rate": float(alert.current_rate),
                        "deviation_pct": float(alert.deviation_pct),
                        "exposure_amount": float(alert.exposure_amount),
                        "status": alert.status,
                    },
                })
                links.append({
                    "source": clause_node_id,
                    "target": alert_node_id,
                    "label": "triggered",
                    "type": "triggered",
                })

                exposure = float(alert.exposure_amount)
                if exposure > 0:
                    scaled = max(2, min(8, math.log10(max(exposure, 1))))
                    nodes.append({
                        "id": f"exposure-{alert.id}",
                        "type": "exposure",
                        "label": f"${exposure:,.0f}",
                        "val": scaled * 2,
                        "color": "#e94560",
                        "details": {
                            "amount": exposure,
                            "currency_pair": alert.currency_pair,
                        },
                    })
                    links.append({
                        "source": alert_node_id,
                        "target": f"exposure-{alert.id}",
                        "label": "exposes",
                        "type": "exposes",
                    })

    return nodes, links


@viz_bp.route("/contracts/3d")
@viz_bp.route("/contracts/<int:contract_id>/3d")
def contract_3d_view(contract_id=None):
    return render_template("contract_3d.html", contract_id=contract_id)


@viz_bp.route("/api/contracts/graph")
def api_contract_graph():
    contract_id = request.args.get("contract_id", type=int)
    session = get_session()
    try:
        query = session.query(Contract).options(
            joinedload(Contract.clauses).joinedload(FXClause.alerts),
        )
        if contract_id:
            query = query.filter(Contract.id == contract_id)
        else:
            query = query.filter(Contract.status == "active")

        contracts = query.all()
        if contract_id and not contracts:
            return jsonify({"error": "Contract not found"}), 404

        nodes, links = build_graph(contracts)
        return jsonify({"nodes": nodes, "links": links})
    finally:
        session.close()
