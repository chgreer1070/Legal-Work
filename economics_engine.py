"""
Economics Engine — Clause-level financial quantification, interaction
modeling, Monte Carlo simulation, and prescriptive recommendations.

This is the quantitative core that transforms contract analysis from
descriptive to decision-grade.
"""

import math
import random

from ems_ontology import CLAUSE_FAMILIES, RECOMMENDATION_TEMPLATES

# ---------------------------------------------------------------------------
# Base financial models per category
# ---------------------------------------------------------------------------

# Default contract parameters (can be overridden per contract)
DEFAULT_PARAMS = {
    "annual_revenue": 25_000_000,        # $25M annual program
    "material_cost_ratio": 0.65,          # 65% material cost
    "average_margin_pct": 0.08,           # 8% margin
    "payment_days": 60,                   # Net 60
    "forecast_accuracy_pct": 0.80,        # 80% forecast accuracy
    "ncnr_ratio": 0.25,                   # 25% of materials are NCNR
    "warranty_claim_rate": 0.02,          # 2% warranty claim rate
    "defect_rate": 0.005,                 # 0.5% defect rate
    "annual_eco_count": 6,                # 6 ECOs per year
    "eco_avg_cost": 75_000,               # $75K per ECO
    "safety_stock_weeks": 3,              # 3 weeks safety stock
    "termination_probability": 0.10,      # 10% annual termination prob
}

# Exposure models by financial category
_EXPOSURE_MODELS = {
    "revenue_risk": lambda p: p["annual_revenue"] * (1 - p["forecast_accuracy_pct"]) * 0.5,
    "revenue_commitment": lambda p: p["annual_revenue"] * 0.25,  # Quarterly commitment
    "cost_disruption": lambda p: p["annual_eco_count"] * p["eco_avg_cost"],
    "baseline": lambda p: 0,
    "cost_of_quality": lambda p: p["annual_revenue"] * p["defect_rate"] * 2.5,
    "compliance_cost": lambda p: p["annual_revenue"] * 0.005,
    "delivery_risk": lambda p: p["annual_revenue"] * 0.02,
    "material_cost": lambda p: p["annual_revenue"] * p["material_cost_ratio"] * 0.05,
    "material_liability": lambda p: (
        p["annual_revenue"] * p["material_cost_ratio"] * p["ncnr_ratio"] * 0.3
    ),
    "inventory_liability": lambda p: (
        p["annual_revenue"] * p["material_cost_ratio"] *
        (1 - p["forecast_accuracy_pct"]) * 0.5
    ),
    "working_capital": lambda p: (
        p["annual_revenue"] * p["material_cost_ratio"] *
        p["safety_stock_weeks"] / 52
    ),
    "margin": lambda p: p["annual_revenue"] * p["average_margin_pct"] * 0.15,
    "cash_flow": lambda p: p["annual_revenue"] * p["payment_days"] / 365 * 0.1,
    "warranty_cost": lambda p: (
        p["annual_revenue"] * p["warranty_claim_rate"] * 0.5
    ),
    "liability_tail": lambda p: p["annual_revenue"],  # Up to 12-month cap
    "asset_risk": lambda p: p["annual_revenue"] * 0.01,
    "legal_cost": lambda p: 150_000,
    "disruption_risk": lambda p: p["annual_revenue"] * 0.10,
    "exit_cost": lambda p: (
        p["annual_revenue"] * p["material_cost_ratio"] * 0.25 +
        p["annual_revenue"] * 0.05
    ),
}

# Interaction multipliers
_INTERACTION_MULTIPLIERS = {
    "additive": 1.0,
    "amplifying": 1.8,
    "cascading": 2.5,
}

# ---------------------------------------------------------------------------
# Clause-level economics
# ---------------------------------------------------------------------------


def compute_clause_economics(clause, params=None):
    """Compute financial metrics for a single clause.

    Returns dict with exposure_base, marginal_risk_contribution,
    cash_impact_days, and raw economics data.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    family_config = CLAUSE_FAMILIES.get(clause["family"], {})
    fin_category = family_config.get("financial_category", "baseline")

    # Base exposure from financial model
    model = _EXPOSURE_MODELS.get(fin_category, lambda _: 0)
    exposure_base = model(p)

    # Adjust for risk rating
    risk_multiplier = 0.5 + (clause["risk_rating"] / 5.0) * 1.0
    adjusted_exposure = exposure_base * risk_multiplier

    # Cash impact in days
    cash_days = _estimate_cash_impact_days(clause, p)

    # Marginal risk contribution (proportion of total potential exposure)
    total_potential = p["annual_revenue"] * 0.15  # 15% of revenue as risk base
    marginal = adjusted_exposure / total_potential if total_potential else 0

    return {
        "exposure_base": round(exposure_base),
        "adjusted_exposure": round(adjusted_exposure),
        "marginal_risk_contribution": round(min(marginal, 1.0), 3),
        "cash_impact_days": cash_days,
        "financial_category": fin_category,
        "risk_multiplier": round(risk_multiplier, 2),
    }


def _estimate_cash_impact_days(clause, params):
    """Estimate how long cash is at risk for this clause."""
    family = clause["family"]

    timing = clause.get("timing", {})
    if "payment_terms" in timing:
        # Extract days from "net 60 days" type strings
        try:
            return int("".join(c for c in timing["payment_terms"] if c.isdigit()))
        except (ValueError, TypeError):
            pass

    # Family-based defaults
    cash_day_defaults = {
        "payment_terms": params["payment_days"],
        "excess_obsolete": 90,
        "long_lead_ncnr": 120,
        "forecasting": 90,
        "warranty": 180,
        "termination_for_convenience": 150,
        "termination_for_cause": 60,
        "safety_stock": 45,
        "engineering_changes": 60,
    }
    return cash_day_defaults.get(family, 30)


# ---------------------------------------------------------------------------
# Interaction effects
# ---------------------------------------------------------------------------


def compute_interaction_effects(clause, graph, all_economics):
    """Compute interaction effects between this clause and its dependencies.

    Walks dependency edges and applies nonlinear interaction multipliers.
    Returns interaction_multiplier and compounded_exposure.
    """
    clause_id = clause["id"]
    # Find all edges involving this clause
    related_edges = [
        e for e in graph.get("edges", [])
        if e["source"] == clause_id or e["target"] == clause_id
    ]

    if not related_edges:
        return {
            "interaction_multiplier": 1.0,
            "compounded_exposure": all_economics.get(clause_id, {}).get("adjusted_exposure", 0),
            "interaction_count": 0,
            "dominant_effect": "none",
        }

    # Compute compound multiplier
    compound = 1.0
    effect_counts = {"additive": 0, "amplifying": 0, "cascading": 0}

    for edge in related_edges:
        effect = edge.get("interaction_effect", "additive")
        effect_counts[effect] = effect_counts.get(effect, 0) + 1
        mult = _INTERACTION_MULTIPLIERS.get(effect, 1.0)

        # Apply diminishing returns for multiple interactions of same type
        count = effect_counts[effect]
        diminished = 1.0 + (mult - 1.0) / math.sqrt(count)
        compound *= diminished

    # Cap compound multiplier to prevent runaway
    compound = min(compound, 5.0)

    base_exposure = all_economics.get(clause_id, {}).get("adjusted_exposure", 0)
    compounded = base_exposure * compound

    dominant = max(effect_counts, key=effect_counts.get)

    return {
        "interaction_multiplier": round(compound, 2),
        "compounded_exposure": round(compounded),
        "interaction_count": len(related_edges),
        "dominant_effect": dominant,
    }


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------

# Distribution parameters by financial category
_DISTRIBUTIONS = {
    "revenue_risk":       {"type": "normal",    "cv": 0.40},
    "revenue_commitment": {"type": "normal",    "cv": 0.25},
    "cost_disruption":    {"type": "lognormal", "cv": 0.60},
    "material_liability": {"type": "lognormal", "cv": 0.50},
    "inventory_liability":{"type": "lognormal", "cv": 0.55},
    "working_capital":    {"type": "normal",    "cv": 0.30},
    "margin":             {"type": "normal",    "cv": 0.35},
    "cash_flow":          {"type": "normal",    "cv": 0.25},
    "warranty_cost":      {"type": "lognormal", "cv": 0.70},
    "liability_tail":     {"type": "lognormal", "cv": 0.80},
    "exit_cost":          {"type": "lognormal", "cv": 0.50},
    "disruption_risk":    {"type": "lognormal", "cv": 0.90},
}


def monte_carlo_simulation(clause_economics, n=1000, seed=None):
    """Run Monte Carlo simulation on clause economics.

    Returns percentile outcomes: P5, P10, EV, P50, P90, P95.
    """
    if seed is not None:
        random.seed(seed)

    base = clause_economics.get("adjusted_exposure", 0)
    if base <= 0:
        return {"p5": 0, "p10": 0, "ev": 0, "p50": 0, "p90": 0, "p95": 0}

    category = clause_economics.get("financial_category", "baseline")
    dist_config = _DISTRIBUTIONS.get(category, {"type": "normal", "cv": 0.30})

    samples = []
    cv = dist_config["cv"]

    for _ in range(n):
        if dist_config["type"] == "lognormal":
            # Log-normal: right-skewed, good for downside risk
            sigma = math.sqrt(math.log(1 + cv ** 2))
            mu = math.log(base) - sigma ** 2 / 2
            sample = random.lognormvariate(mu, sigma)
        else:
            # Normal with floor at 0
            sample = max(0, random.gauss(base, base * cv))
        samples.append(sample)

    samples.sort()

    def percentile(pct):
        idx = int(len(samples) * pct / 100)
        idx = max(0, min(idx, len(samples) - 1))
        return round(samples[idx])

    return {
        "p5": percentile(95),    # 95th percentile = downside P5
        "p10": percentile(90),
        "ev": round(sum(samples) / len(samples)),
        "p50": percentile(50),
        "p90": percentile(10),
        "p95": percentile(5),
    }


# ---------------------------------------------------------------------------
# Time-based risk profile
# ---------------------------------------------------------------------------

_PHASE_PROFILES = {
    # (ramp_factor, steady_factor, decline_factor) for months 0-3, 4-8, 9-11
    "material_liability": (0.3, 1.0, 0.8),
    "inventory_liability": (0.2, 1.0, 1.5),  # Grows in decline
    "working_capital": (0.5, 1.0, 0.7),
    "warranty_cost": (0.1, 0.6, 1.0),        # Lags production
    "exit_cost": (0.1, 0.5, 1.0),
    "cash_flow": (0.4, 1.0, 0.8),
    "revenue_risk": (0.5, 1.0, 0.6),
    "disruption_risk": (0.3, 1.0, 1.2),
}


def compute_time_profile(clause_economics, months=12):
    """Compute risk accumulation over time.

    Returns list of monthly exposure values showing how risk evolves.
    """
    base = clause_economics.get("adjusted_exposure", 0)
    category = clause_economics.get("financial_category", "baseline")
    profile = _PHASE_PROFILES.get(category, (0.5, 1.0, 0.8))

    monthly = []
    for m in range(months):
        if m < 3:
            factor = profile[0] + (profile[1] - profile[0]) * (m / 3)
        elif m < 9:
            factor = profile[1]
        else:
            factor = profile[1] + (profile[2] - profile[1]) * ((m - 9) / 3)

        monthly.append(round(base * factor / 12))  # Monthly portion

    return monthly


# ---------------------------------------------------------------------------
# Prescriptive recommendations with quantified impact
# ---------------------------------------------------------------------------


def generate_recommendations(clause, clause_economics, interaction_data):
    """Generate prioritized recommendations with quantified financial impact.

    Each recommendation includes: action, impact_cash, impact_margin_pct,
    effort, priority_score.
    """
    family = clause["family"]
    templates = RECOMMENDATION_TEMPLATES.get(family, [])
    base_exposure = clause_economics.get("adjusted_exposure", 0)
    compounded = interaction_data.get("compounded_exposure", base_exposure)
    annual_revenue = DEFAULT_PARAMS["annual_revenue"]

    recommendations = []
    for tmpl in templates:
        impact_cash = round(compounded * tmpl["impact_multiplier"])
        impact_margin_pct = round(impact_cash / annual_revenue * 100, 2) if annual_revenue else 0

        effort_scores = {"low": 1, "medium": 2, "high": 3}
        effort_score = effort_scores.get(tmpl["effort"], 2)

        # Priority = (cash impact * margin impact) / effort
        priority = round(
            (impact_cash / 100_000) * (1 + impact_margin_pct) / effort_score, 1
        )

        recommendations.append({
            "action": tmpl["action"],
            "impact_cash": impact_cash,
            "impact_margin_pct": impact_margin_pct,
            "effort": tmpl["effort"],
            "priority_score": min(priority, 10.0),
        })

    # Sort by priority descending
    recommendations.sort(key=lambda r: r["priority_score"], reverse=True)
    return recommendations


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------


def compute_portfolio_summary(all_clauses_economics, all_monte_carlo):
    """Aggregate economics across all clauses into portfolio-level metrics.

    Returns total exposure, risk-adjusted margin, top risk clauses,
    highest ROI fixes.
    """
    total_exposure = sum(
        e.get("adjusted_exposure", 0) for e in all_clauses_economics.values()
    )
    total_compounded = sum(
        e.get("compounded_exposure", e.get("adjusted_exposure", 0))
        for e in all_clauses_economics.values()
    )

    annual_revenue = DEFAULT_PARAMS["annual_revenue"]
    risk_adjusted_margin = DEFAULT_PARAMS["average_margin_pct"] - (
        total_exposure / annual_revenue if annual_revenue else 0
    )

    # Aggregate Monte Carlo
    agg_p5 = sum(mc.get("p5", 0) for mc in all_monte_carlo.values())
    agg_p10 = sum(mc.get("p10", 0) for mc in all_monte_carlo.values())
    agg_ev = sum(mc.get("ev", 0) for mc in all_monte_carlo.values())

    # Top risk clauses by compounded exposure
    sorted_clauses = sorted(
        all_clauses_economics.items(),
        key=lambda x: x[1].get("compounded_exposure", x[1].get("adjusted_exposure", 0)),
        reverse=True,
    )
    top_risk = [cid for cid, _ in sorted_clauses[:5]]

    return {
        "total_exposure": round(total_exposure),
        "total_compounded_exposure": round(total_compounded),
        "risk_adjusted_margin": round(risk_adjusted_margin, 4),
        "monte_carlo_aggregate": {
            "p5": agg_p5,
            "p10": agg_p10,
            "ev": agg_ev,
        },
        "top_risk_clauses": top_risk,
    }
