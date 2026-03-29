"""
Scenario Engine — defines simulation scenarios for EMS contract risk,
computes cascade effects, and produces probabilistic outcomes.

Each scenario is an ordered activation chain showing how a triggering
event propagates through clause dependencies.
"""

from economics_engine import (
    DEFAULT_PARAMS,
    compute_clause_economics,
    monte_carlo_simulation,
)

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS = {
    "forecast_collapse": {
        "id": "forecast_collapse",
        "name": "Forecast Collapse",
        "description": (
            "Customer forecast drops 40%. Long-lead materials already ordered. "
            "NCNR commitments outstanding. E&O liability activates."
        ),
        "trigger_event": "Customer forecast reduction of 40%",
        "severity": "high",
        "probability": 0.15,
        "chain": [
            {
                "family": "forecasting",
                "delay_ms": 0,
                "effect": "Forecast drops 40% below binding commitment",
                "financial_multiplier": 0.40,
            },
            {
                "family": "purchase_orders",
                "delay_ms": 500,
                "effect": "Open POs exceed actual demand — cancellations requested",
                "financial_multiplier": 0.30,
            },
            {
                "family": "long_lead_ncnr",
                "delay_ms": 1000,
                "effect": "NCNR materials cannot be returned — exposure crystallizes",
                "financial_multiplier": 0.80,
            },
            {
                "family": "materials_management",
                "delay_ms": 1500,
                "effect": "Raw material inventory exceeds 90-day threshold",
                "financial_multiplier": 0.35,
            },
            {
                "family": "excess_obsolete",
                "delay_ms": 2000,
                "effect": "E&O liability activates — customer must reimburse or buy inventory",
                "financial_multiplier": 0.60,
            },
            {
                "family": "safety_stock",
                "delay_ms": 2300,
                "effect": "Safety stock becomes excess — additional E&O pool",
                "financial_multiplier": 0.50,
            },
            {
                "family": "payment_terms",
                "delay_ms": 2800,
                "effect": "Cash tied up in unreimbursed inventory — receivables spike",
                "financial_multiplier": 0.25,
            },
            {
                "family": "pricing",
                "delay_ms": 3200,
                "effect": "Lower volumes erode margin — fixed cost absorption drops",
                "financial_multiplier": 0.20,
            },
        ],
    },
    "quality_failure": {
        "id": "quality_failure",
        "name": "Quality Failure Spike",
        "description": (
            "Defect rate spikes to 5%. Warranty claims surge. "
            "Indemnification triggered. Liability cap tested."
        ),
        "trigger_event": "Manufacturing defect rate exceeds 5%",
        "severity": "high",
        "probability": 0.08,
        "chain": [
            {
                "family": "quality_standards",
                "delay_ms": 0,
                "effect": "Quality failure detected — defect rate exceeds threshold",
                "financial_multiplier": 0.50,
            },
            {
                "family": "inspection_rights",
                "delay_ms": 600,
                "effect": "Customer triggers audit — facility inspection demanded",
                "financial_multiplier": 0.10,
            },
            {
                "family": "warranty",
                "delay_ms": 1200,
                "effect": "Warranty claims surge — repair/replace obligations activate",
                "financial_multiplier": 0.70,
            },
            {
                "family": "rma_returns",
                "delay_ms": 1800,
                "effect": "RMA volume overwhelms failure analysis capacity",
                "financial_multiplier": 0.40,
            },
            {
                "family": "indemnification",
                "delay_ms": 2400,
                "effect": "Customer asserts third-party claims — indemnity triggered",
                "financial_multiplier": 0.60,
            },
            {
                "family": "liability_cap",
                "delay_ms": 3000,
                "effect": "Aggregate liability approaching cap — carveouts examined",
                "financial_multiplier": 0.30,
            },
            {
                "family": "termination_for_cause",
                "delay_ms": 3600,
                "effect": "Customer threatens termination for material breach",
                "financial_multiplier": 0.50,
            },
        ],
    },
    "engineering_change": {
        "id": "engineering_change",
        "name": "Major Engineering Change",
        "description": (
            "Customer revises BOM affecting 30% of components. "
            "Obsolete material pool, pricing reset, delivery disruption."
        ),
        "trigger_event": "Customer issues major BOM revision (ECO)",
        "severity": "medium",
        "probability": 0.25,
        "chain": [
            {
                "family": "engineering_changes",
                "delay_ms": 0,
                "effect": "ECO issued — 30% of BOM components affected",
                "financial_multiplier": 0.50,
            },
            {
                "family": "materials_management",
                "delay_ms": 800,
                "effect": "Current inventory for changed components becomes unusable",
                "financial_multiplier": 0.40,
            },
            {
                "family": "excess_obsolete",
                "delay_ms": 1500,
                "effect": "ECO-driven obsolete material pool identified",
                "financial_multiplier": 0.55,
            },
            {
                "family": "pricing",
                "delay_ms": 2000,
                "effect": "New components require pricing true-up",
                "financial_multiplier": 0.30,
            },
            {
                "family": "quality_standards",
                "delay_ms": 2500,
                "effect": "First article inspection required for revised product",
                "financial_multiplier": 0.15,
            },
            {
                "family": "delivery",
                "delay_ms": 3000,
                "effect": "New component lead times disrupt delivery schedule",
                "financial_multiplier": 0.35,
            },
        ],
    },
    "termination_convenience": {
        "id": "termination_convenience",
        "name": "Termination for Convenience",
        "description": (
            "Customer terminates without cause. Full inventory unwind, "
            "WIP settlement, NCNR exposure, transition costs."
        ),
        "trigger_event": "Customer issues 120-day termination notice",
        "severity": "critical",
        "probability": 0.10,
        "chain": [
            {
                "family": "termination_for_convenience",
                "delay_ms": 0,
                "effect": "Customer exercises convenience termination — 120-day notice",
                "financial_multiplier": 1.00,
            },
            {
                "family": "purchase_orders",
                "delay_ms": 500,
                "effect": "Open POs must be completed or settled",
                "financial_multiplier": 0.40,
            },
            {
                "family": "long_lead_ncnr",
                "delay_ms": 1000,
                "effect": "All outstanding NCNR commitments crystallize",
                "financial_multiplier": 0.90,
            },
            {
                "family": "excess_obsolete",
                "delay_ms": 1500,
                "effect": "All raw materials and WIP become buyback obligation",
                "financial_multiplier": 0.80,
            },
            {
                "family": "safety_stock",
                "delay_ms": 1800,
                "effect": "All safety stock must be purchased by customer",
                "financial_multiplier": 0.70,
            },
            {
                "family": "payment_terms",
                "delay_ms": 2200,
                "effect": "Final settlement — all outstanding invoices plus termination charges",
                "financial_multiplier": 0.50,
            },
            {
                "family": "ip_tooling",
                "delay_ms": 2800,
                "effect": "Customer tooling return — logistics and insurance costs",
                "financial_multiplier": 0.20,
            },
            {
                "family": "transition_assistance",
                "delay_ms": 3200,
                "effect": "6-month transition support — continuation of production during handover",
                "financial_multiplier": 0.35,
            },
        ],
    },
    "force_majeure": {
        "id": "force_majeure",
        "name": "Force Majeure Event",
        "description": (
            "Major supply chain disruption. Delivery obligations excused. "
            "Material shortages cascade through the system."
        ),
        "trigger_event": "Global supply chain disruption (pandemic, natural disaster)",
        "severity": "high",
        "probability": 0.05,
        "chain": [
            {
                "family": "force_majeure",
                "delay_ms": 0,
                "effect": "Force majeure declared — performance obligations suspended",
                "financial_multiplier": 1.00,
            },
            {
                "family": "materials_management",
                "delay_ms": 700,
                "effect": "Component supply disrupted — critical shortages emerge",
                "financial_multiplier": 0.60,
            },
            {
                "family": "delivery",
                "delay_ms": 1400,
                "effect": "Delivery schedule slips — OTD drops below threshold",
                "financial_multiplier": 0.50,
            },
            {
                "family": "pricing",
                "delay_ms": 2000,
                "effect": "Spot market pricing spikes for available components",
                "financial_multiplier": 0.45,
            },
            {
                "family": "forecasting",
                "delay_ms": 2500,
                "effect": "Customer revises demand — uncertainty compounds",
                "financial_multiplier": 0.30,
            },
            {
                "family": "termination_for_convenience",
                "delay_ms": 3500,
                "effect": "If event exceeds 90 days — termination rights activate",
                "financial_multiplier": 0.40,
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Scenario execution
# ---------------------------------------------------------------------------


def run_scenario(scenario_id, clauses, graph, params=None):
    """Execute a scenario simulation against parsed contract data.

    Returns scenario metadata plus activation chain with financial impacts.
    """
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        return {"error": f"Unknown scenario: {scenario_id}"}

    p = {**DEFAULT_PARAMS, **(params or {})}

    # Index clauses by family
    family_to_clause = {}
    for clause in clauses:
        family_to_clause.setdefault(clause["family"], clause)

    activations = []
    cumulative_exposure = 0
    cumulative_ev = 0

    for step in scenario["chain"]:
        family = step["family"]
        clause = family_to_clause.get(family)

        if clause:
            # Compute economics for this step
            economics = compute_clause_economics(clause, p)
            step_exposure = round(
                economics["adjusted_exposure"] * step["financial_multiplier"]
            )
            cumulative_exposure += step_exposure

            # Monte Carlo for this step
            mc_input = {**economics, "adjusted_exposure": step_exposure}
            mc = monte_carlo_simulation(mc_input, n=500, seed=hash(scenario_id + family) % 2**31)
            cumulative_ev += mc["ev"]

            activations.append({
                "clause_id": clause["id"],
                "clause_title": clause["title"],
                "family": family,
                "delay_ms": step["delay_ms"],
                "effect": step["effect"],
                "step_exposure": step_exposure,
                "cumulative_exposure": cumulative_exposure,
                "monte_carlo": mc,
                "cumulative_ev": cumulative_ev,
            })
        else:
            # Clause family not present in this contract
            activations.append({
                "clause_id": None,
                "clause_title": f"[{family} — not found in contract]",
                "family": family,
                "delay_ms": step["delay_ms"],
                "effect": step["effect"],
                "step_exposure": 0,
                "cumulative_exposure": cumulative_exposure,
                "monte_carlo": {"p5": 0, "p10": 0, "ev": 0, "p50": 0, "p90": 0, "p95": 0},
                "cumulative_ev": cumulative_ev,
            })

    return {
        "scenario": {
            "id": scenario["id"],
            "name": scenario["name"],
            "description": scenario["description"],
            "trigger_event": scenario["trigger_event"],
            "severity": scenario["severity"],
            "probability": scenario["probability"],
        },
        "activations": activations,
        "total_exposure": cumulative_exposure,
        "total_ev": cumulative_ev,
        "probability_weighted_impact": round(cumulative_ev * scenario["probability"]),
    }


def get_all_scenario_summaries(clauses, graph, params=None):
    """Run all scenarios and return summary-level results."""
    summaries = []
    for scenario_id in SCENARIOS:
        result = run_scenario(scenario_id, clauses, graph, params)
        summaries.append({
            "id": result["scenario"]["id"],
            "name": result["scenario"]["name"],
            "severity": result["scenario"]["severity"],
            "probability": result["scenario"]["probability"],
            "total_exposure": result["total_exposure"],
            "total_ev": result["total_ev"],
            "probability_weighted_impact": result["probability_weighted_impact"],
            "steps": len(result["activations"]),
        })
    summaries.sort(key=lambda s: s["total_ev"], reverse=True)
    return summaries
