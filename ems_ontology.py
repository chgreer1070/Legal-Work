"""
EMS Contract Ontology — Domain-specific classification system for
Electronics Manufacturing Services agreements.

Defines 25 clause families, 6 visualization zones, structural dependency
rules, actor patterns, and recommendation templates.
"""

# ---------------------------------------------------------------------------
# Zones — 3-D visualization regions
# ---------------------------------------------------------------------------
ZONES = {
    "customer": {
        "label": "Customer Demand",
        "color": "#3b82f6",
        "position": [-20, 0, -10],
        "description": "Forecast, POs, engineering changes, cancellations",
    },
    "manufacturer": {
        "label": "Manufacturer Execution",
        "color": "#10b981",
        "position": [0, 0, 0],
        "description": "Planning, sourcing, build, test, quality, delivery",
    },
    "supplier": {
        "label": "Supply Chain",
        "color": "#8b5cf6",
        "position": [20, 0, -10],
        "description": "Component sources, long-lead risk, NCNR exposure",
    },
    "financial": {
        "label": "Financial Flows",
        "color": "#f59e0b",
        "position": [-10, 0, 15],
        "description": "Invoice, payment, credits, true-up, reimbursement",
    },
    "risk": {
        "label": "Risk & Liability",
        "color": "#ef4444",
        "position": [10, 0, 15],
        "description": "Warranty, indemnity, liability cap, claims, disputes",
    },
    "exit": {
        "label": "Termination & Exit",
        "color": "#6b7280",
        "position": [0, 0, 25],
        "description": "Termination, transition, inventory disposition, unwind",
    },
}

# ---------------------------------------------------------------------------
# Clause Families — 25 EMS-specific clause categories
# ---------------------------------------------------------------------------
CLAUSE_FAMILIES = {
    # --- Customer zone ---
    "forecasting": {
        "zone": "customer",
        "keywords": [
            r"forecast", r"demand\s+plan", r"rolling\s+forecast",
            r"binding\s+forecast", r"non-?binding", r"forecast\s+horizon",
        ],
        "risk_weight": 4,
        "financial_category": "revenue_risk",
        "interaction_group": "demand",
        "description": "Forecast commitments, binding windows, demand planning",
    },
    "purchase_orders": {
        "zone": "customer",
        "keywords": [
            r"purchase\s+order", r"\bPO\b", r"order\s+acceptance",
            r"order\s+cancellation", r"order\s+precedence", r"firm\s+order",
        ],
        "risk_weight": 3,
        "financial_category": "revenue_commitment",
        "interaction_group": "demand",
        "description": "PO issuance, acceptance, cancellation, precedence rules",
    },
    "engineering_changes": {
        "zone": "customer",
        "keywords": [
            r"engineering\s+change", r"\bECO\b", r"\bECN\b",
            r"design\s+change", r"specification\s+change", r"BOM\s+change",
            r"bill\s+of\s+material",
        ],
        "risk_weight": 4,
        "financial_category": "cost_disruption",
        "interaction_group": "change",
        "description": "Engineering change orders, BOM revisions, spec changes",
    },

    # --- Manufacturer zone ---
    "scope_of_work": {
        "zone": "manufacturer",
        "keywords": [
            r"scope\s+of\s+work", r"services?\s+description",
            r"manufacturing\s+services", r"assembly", r"test\s+services",
            r"statement\s+of\s+work", r"\bSOW\b",
        ],
        "risk_weight": 2,
        "financial_category": "baseline",
        "interaction_group": "operations",
        "description": "What the manufacturer is contracted to build/deliver",
    },
    "quality_standards": {
        "zone": "manufacturer",
        "keywords": [
            r"quality", r"ISO\s*9001", r"IPC", r"inspection",
            r"acceptance\s+criteria", r"workmanship", r"defect",
            r"non-?conform", r"first\s+article",
        ],
        "risk_weight": 3,
        "financial_category": "cost_of_quality",
        "interaction_group": "quality",
        "description": "Quality certifications, inspection, acceptance criteria",
    },
    "inspection_rights": {
        "zone": "manufacturer",
        "keywords": [
            r"audit", r"right\s+to\s+inspect", r"facility\s+access",
            r"inspection\s+right", r"site\s+visit", r"audit\s+right",
        ],
        "risk_weight": 2,
        "financial_category": "compliance_cost",
        "interaction_group": "quality",
        "description": "Customer rights to audit and inspect manufacturer",
    },
    "delivery": {
        "zone": "manufacturer",
        "keywords": [
            r"delivery", r"shipment", r"ship\s+date", r"incoterms?",
            r"freight", r"logistics", r"lead\s*-?\s*time", r"on-?time",
            r"\bFOB\b", r"\bDDP\b", r"\bEXW\b",
        ],
        "risk_weight": 3,
        "financial_category": "delivery_risk",
        "interaction_group": "operations",
        "description": "Delivery terms, shipping, incoterms, lead times",
    },
    "reporting": {
        "zone": "manufacturer",
        "keywords": [
            r"report", r"status\s+update", r"KPI", r"scorecard",
            r"dashboard", r"periodic\s+review", r"business\s+review",
        ],
        "risk_weight": 1,
        "financial_category": "compliance_cost",
        "interaction_group": "governance",
        "description": "Reporting obligations, KPIs, business reviews",
    },

    # --- Supplier zone ---
    "materials_management": {
        "zone": "supplier",
        "keywords": [
            r"raw\s+material", r"component", r"procurement",
            r"approved\s+vendor", r"\bAVL\b", r"material\s+procurement",
            r"bill\s+of\s+material", r"sourcing",
        ],
        "risk_weight": 3,
        "financial_category": "material_cost",
        "interaction_group": "supply",
        "description": "Material procurement, AVL, sourcing requirements",
    },
    "long_lead_ncnr": {
        "zone": "supplier",
        "keywords": [
            r"long[\s-]*lead", r"\bNCNR\b", r"non-?cancell?able",
            r"non-?returnable", r"advance\s+procurement",
            r"material\s+authorization",
        ],
        "risk_weight": 5,
        "financial_category": "material_liability",
        "interaction_group": "supply",
        "description": "Long-lead and NCNR material commitments",
    },
    "consigned_inventory": {
        "zone": "supplier",
        "keywords": [
            r"consign", r"customer[\s-]*owned\s+material",
            r"customer[\s-]*furnished", r"title\s+to\s+material",
            r"bailment",
        ],
        "risk_weight": 3,
        "financial_category": "inventory_liability",
        "interaction_group": "supply",
        "description": "Consigned/customer-owned inventory terms",
    },
    "safety_stock": {
        "zone": "supplier",
        "keywords": [
            r"safety\s+stock", r"buffer\s+stock", r"minimum\s+stock",
            r"inventory\s+buffer", r"stocking\s+level",
        ],
        "risk_weight": 3,
        "financial_category": "working_capital",
        "interaction_group": "supply",
        "description": "Safety stock, buffer stock, minimum stocking levels",
    },

    # --- Financial zone ---
    "pricing": {
        "zone": "financial",
        "keywords": [
            r"pric(?:e|ing)", r"unit\s+price", r"cost\s+model",
            r"repric", r"price\s+adjustment", r"price\s+increase",
            r"cost\s+reduction", r"margin",
        ],
        "risk_weight": 4,
        "financial_category": "margin",
        "interaction_group": "financial",
        "description": "Pricing, repricing, cost models, price adjustments",
    },
    "payment_terms": {
        "zone": "financial",
        "keywords": [
            r"payment", r"invoice", r"net\s+\d+", r"due\s+date",
            r"set[\s-]*off", r"credit", r"true[\s-]*up",
            r"accounts?\s+(?:receivable|payable)",
        ],
        "risk_weight": 3,
        "financial_category": "cash_flow",
        "interaction_group": "financial",
        "description": "Payment terms, invoicing, setoff rights, credits",
    },
    "excess_obsolete": {
        "zone": "financial",
        "keywords": [
            r"excess", r"obsolete", r"\bE\s*&\s*O\b", r"scrap",
            r"dead\s+stock", r"unusable\s+(?:material|inventory)",
            r"obsolescence", r"write[\s-]*off",
            r"excess\s+and\s+obsolete", r"deemed\s+.{0,20}excess",
            r"handling\s+charge",
        ],
        "risk_weight": 5,
        "financial_category": "inventory_liability",
        "interaction_group": "financial",
        "description": "E&O inventory liability, scrap, reimbursement",
    },

    # --- Risk zone ---
    "warranty": {
        "zone": "risk",
        "keywords": [
            r"warrant", r"defect", r"repair", r"replace",
            r"workmanship\s+guarantee", r"warranty\s+period",
            r"latent\s+defect",
        ],
        "risk_weight": 4,
        "financial_category": "warranty_cost",
        "interaction_group": "quality",
        "description": "Warranty scope, period, remedies, exclusions",
    },
    "rma_returns": {
        "zone": "risk",
        "keywords": [
            r"\bRMA\b", r"return\s+material", r"field\s+failure",
            r"failure\s+analysis", r"return\s+authorization",
        ],
        "risk_weight": 3,
        "financial_category": "warranty_cost",
        "interaction_group": "quality",
        "description": "RMA process, field failure analysis, return handling",
    },
    "indemnification": {
        "zone": "risk",
        "keywords": [
            r"indemnif", r"hold\s+harmless", r"defend\s+and\s+indemnif",
            r"third[\s-]*party\s+claim", r"infringement",
        ],
        "risk_weight": 5,
        "financial_category": "liability_tail",
        "interaction_group": "liability",
        "description": "Indemnification obligations, third-party claims",
    },
    "liability_cap": {
        "zone": "risk",
        "keywords": [
            r"limitation?\s+of\s+liability", r"liability\s+cap",
            r"consequential\s+damage", r"direct\s+damage",
            r"aggregate\s+liability", r"exclusive\s+remed",
        ],
        "risk_weight": 5,
        "financial_category": "liability_tail",
        "interaction_group": "liability",
        "description": "Liability caps, damage exclusions, remedy limitations",
    },
    "insurance": {
        "zone": "risk",
        "keywords": [
            r"insurance", r"coverage", r"policy", r"general\s+liability",
            r"product\s+liability\s+insurance", r"certificate\s+of\s+insurance",
        ],
        "risk_weight": 2,
        "financial_category": "compliance_cost",
        "interaction_group": "liability",
        "description": "Insurance requirements, coverage minimums",
    },
    "force_majeure": {
        "zone": "risk",
        "keywords": [
            r"force\s+majeure", r"act\s+of\s+god", r"natural\s+disaster",
            r"pandemic", r"supply\s+disruption", r"unforeseeable",
        ],
        "risk_weight": 3,
        "financial_category": "disruption_risk",
        "interaction_group": "risk_events",
        "description": "Force majeure events, excused performance",
    },

    # --- Exit zone ---
    "termination_for_cause": {
        "zone": "exit",
        "keywords": [
            r"terminat(?:e|ion)\s+for\s+cause", r"material\s+breach",
            r"cure\s+period", r"default", r"terminat(?:e|ion)\s+for\s+breach",
        ],
        "risk_weight": 4,
        "financial_category": "exit_cost",
        "interaction_group": "exit",
        "description": "Termination for cause, breach, cure periods",
    },
    "termination_for_convenience": {
        "zone": "exit",
        "keywords": [
            r"terminat(?:e|ion)\s+for\s+convenience",
            r"terminat(?:e|ion)\s+without\s+cause",
            r"terminat(?:e|ion)\s+(?:at\s+)?(?:any\s+time|will)",
            r"last[\s-]*time\s+buy",
            r"termination\s+charge", r"wind[\s-]*down\s+cost",
            r"cancelled\s+orders",
        ],
        "risk_weight": 5,
        "financial_category": "exit_cost",
        "interaction_group": "exit",
        "description": "Termination for convenience, unwind obligations",
    },
    "transition_assistance": {
        "zone": "exit",
        "keywords": [
            r"transition", r"wind[\s-]*down", r"disengagement",
            r"transfer\s+of\s+production", r"last[\s-]*time\s+buy",
            r"tooling\s+return",
        ],
        "risk_weight": 3,
        "financial_category": "exit_cost",
        "interaction_group": "exit",
        "description": "Transition assistance, production transfer, tooling return",
    },

    # --- Cross-cutting (assigned to closest primary zone) ---
    "ip_tooling": {
        "zone": "manufacturer",
        "keywords": [
            r"intellectual\s+property", r"\bIP\b", r"tooling",
            r"work\s+product", r"proprietary", r"trade\s+secret",
            r"patent", r"copyright", r"license",
        ],
        "risk_weight": 3,
        "financial_category": "asset_risk",
        "interaction_group": "ip",
        "description": "IP ownership, tooling, work product, licensing",
    },
    "confidentiality": {
        "zone": "manufacturer",
        "keywords": [
            r"confidential", r"\bNDA\b", r"non[\s-]*disclosure",
            r"proprietary\s+information", r"trade\s+secret",
            r"export\s+control", r"\bITAR\b", r"\bEAR\b",
        ],
        "risk_weight": 2,
        "financial_category": "compliance_cost",
        "interaction_group": "compliance",
        "description": "Confidentiality, NDA, export control, compliance",
    },
    "compliance": {
        "zone": "manufacturer",
        "keywords": [
            r"compliance", r"regulat", r"RoHS", r"REACH",
            r"conflict\s+mineral", r"environmental",
            r"product[\s-]*specific\s+requirement",
        ],
        "risk_weight": 2,
        "financial_category": "compliance_cost",
        "interaction_group": "compliance",
        "description": "Regulatory compliance, RoHS, REACH, environmental",
    },
    "dispute_resolution": {
        "zone": "risk",
        "keywords": [
            r"dispute", r"arbitrat", r"mediat", r"governing\s+law",
            r"jurisdiction", r"venue", r"litigation",
        ],
        "risk_weight": 2,
        "financial_category": "legal_cost",
        "interaction_group": "governance",
        "description": "Dispute resolution, governing law, arbitration",
    },
    "term_renewal": {
        "zone": "exit",
        "keywords": [
            r"term\s+(?:of|and)\s+(?:this\s+)?agreement",
            r"initial\s+term", r"renewal", r"auto[\s-]*renew",
            r"expir(?:e|ation)", r"effective\s+date",
        ],
        "risk_weight": 2,
        "financial_category": "baseline",
        "interaction_group": "governance",
        "description": "Agreement term, renewal, expiration",
    },
}

# ---------------------------------------------------------------------------
# Structural Dependency Rules — how clause families interact
# ---------------------------------------------------------------------------
# (source_family, target_family, relationship_type, label, interaction_effect)
# interaction_effect: "additive" | "amplifying" | "cascading"
DEPENDENCY_RULES = [
    # Demand chain
    ("forecasting", "purchase_orders", "triggers", "Forecast drives PO issuance", "additive"),
    ("forecasting", "materials_management", "triggers", "Forecast authorizes procurement", "amplifying"),
    ("forecasting", "long_lead_ncnr", "triggers", "Forecast drives long-lead material buys", "cascading"),
    ("forecasting", "excess_obsolete", "triggers", "Forecast inaccuracy creates E&O liability", "cascading"),
    ("forecasting", "safety_stock", "triggers", "Forecast variability drives buffer stock requirements", "amplifying"),
    ("purchase_orders", "materials_management", "triggers", "POs authorize material procurement", "additive"),
    ("purchase_orders", "delivery", "triggers", "POs create delivery obligations", "additive"),

    # Supply chain
    ("materials_management", "long_lead_ncnr", "triggers", "Procurement includes NCNR commitments", "amplifying"),
    ("materials_management", "excess_obsolete", "triggers", "Material buys create E&O exposure", "cascading"),
    ("long_lead_ncnr", "excess_obsolete", "triggers", "NCNR materials amplify E&O risk", "cascading"),
    ("consigned_inventory", "excess_obsolete", "modifies", "Consigned inventory shifts E&O ownership", "additive"),
    ("safety_stock", "excess_obsolete", "triggers", "Buffer stock increases E&O pool", "amplifying"),

    # Financial chain
    ("pricing", "payment_terms", "modifies", "Pricing affects cash flow timing", "additive"),
    ("excess_obsolete", "payment_terms", "triggers", "E&O reimbursement timing affects cash", "cascading"),
    ("delivery", "payment_terms", "triggers", "Shipment triggers invoice/payment cycle", "additive"),
    ("pricing", "excess_obsolete", "modifies", "Price changes may create obsolete inventory at old cost", "amplifying"),

    # Quality chain
    ("quality_standards", "warranty", "triggers", "Quality failures trigger warranty claims", "amplifying"),
    ("quality_standards", "inspection_rights", "modifies", "Quality standards define audit scope", "additive"),
    ("warranty", "rma_returns", "triggers", "Warranty claims drive RMA process", "additive"),
    ("warranty", "indemnification", "triggers", "Warranty failures may trigger indemnity", "cascading"),
    ("rma_returns", "payment_terms", "triggers", "RMA credits affect payment flows", "additive"),

    # Change chain
    ("engineering_changes", "materials_management", "triggers", "ECOs change material requirements", "amplifying"),
    ("engineering_changes", "excess_obsolete", "triggers", "ECOs create obsolete material", "cascading"),
    ("engineering_changes", "pricing", "triggers", "ECOs may require price adjustments", "amplifying"),
    ("engineering_changes", "delivery", "triggers", "ECOs disrupt delivery schedule", "amplifying"),
    ("engineering_changes", "quality_standards", "modifies", "ECOs may change acceptance criteria", "additive"),

    # Liability chain
    ("indemnification", "liability_cap", "modifies", "Indemnity obligations subject to liability cap carveouts", "cascading"),
    ("warranty", "liability_cap", "modifies", "Warranty exposure bounded by liability cap", "amplifying"),
    ("insurance", "indemnification", "modifies", "Insurance backstops indemnity obligations", "additive"),
    ("insurance", "liability_cap", "modifies", "Insurance coverage relates to liability cap", "additive"),

    # Exit chain
    ("termination_for_convenience", "excess_obsolete", "triggers", "Termination triggers full E&O unwind", "cascading"),
    ("termination_for_convenience", "long_lead_ncnr", "triggers", "Termination exposes NCNR commitments", "cascading"),
    ("termination_for_convenience", "transition_assistance", "triggers", "Termination requires transition support", "additive"),
    ("termination_for_convenience", "payment_terms", "triggers", "Termination requires final settlement", "amplifying"),
    ("termination_for_cause", "excess_obsolete", "triggers", "Breach termination triggers inventory unwind", "cascading"),
    ("termination_for_cause", "indemnification", "triggers", "Breach may trigger indemnity claims", "cascading"),
    ("term_renewal", "termination_for_convenience", "modifies", "Term expiration is a termination path", "additive"),

    # Risk events
    ("force_majeure", "delivery", "triggers", "Force majeure excuses delivery delays", "amplifying"),
    ("force_majeure", "materials_management", "triggers", "Disruption affects material supply", "cascading"),
    ("force_majeure", "pricing", "triggers", "Disruption may trigger cost increases", "amplifying"),

    # IP/compliance
    ("ip_tooling", "termination_for_convenience", "triggers", "Termination requires tooling return", "additive"),
    ("ip_tooling", "transition_assistance", "triggers", "Transition includes IP/tooling transfer", "additive"),
    ("confidentiality", "termination_for_convenience", "modifies", "Confidentiality survives termination", "additive"),
]

# ---------------------------------------------------------------------------
# Actor patterns — regex → canonical actor name
# ---------------------------------------------------------------------------
ACTOR_PATTERNS = {
    r"\b(?:customer|buyer|client|purchaser|OEM)\b": "customer",
    r"\b(?:manufacturer|supplier|vendor|contractor|provider|CM|EMS)\b": "manufacturer",
    r"\b(?:sub-?supplier|sub-?contractor|component\s+supplier|third[\s-]*party\s+supplier)\b": "supplier",
    r"\b(?:both\s+parties|each\s+party|the\s+parties|mutual)\b": "both",
}

# ---------------------------------------------------------------------------
# Recommendation templates — prescriptive actions per family
# ---------------------------------------------------------------------------
RECOMMENDATION_TEMPLATES = {
    "forecasting": [
        {
            "action": "Shorten binding forecast window from {current} to reduce procurement exposure",
            "impact_type": "material_liability_reduction",
            "impact_multiplier": 0.35,
            "effort": "high",
        },
        {
            "action": "Add forecast accuracy penalty/incentive mechanism",
            "impact_type": "margin_protection",
            "impact_multiplier": 0.15,
            "effort": "medium",
        },
    ],
    "excess_obsolete": [
        {
            "action": "Tighten E&O reimbursement window to 30 days",
            "impact_type": "cash_improvement",
            "impact_multiplier": 0.40,
            "effort": "medium",
        },
        {
            "action": "Add automatic E&O true-up at each quarterly review",
            "impact_type": "inventory_liability_reduction",
            "impact_multiplier": 0.25,
            "effort": "low",
        },
    ],
    "long_lead_ncnr": [
        {
            "action": "Require customer pre-approval for NCNR purchases above threshold",
            "impact_type": "material_liability_reduction",
            "impact_multiplier": 0.50,
            "effort": "medium",
        },
        {
            "action": "Cap NCNR exposure at percentage of quarterly revenue",
            "impact_type": "cash_improvement",
            "impact_multiplier": 0.30,
            "effort": "high",
        },
    ],
    "payment_terms": [
        {
            "action": "Reduce payment terms from Net 60 to Net 30",
            "impact_type": "cash_improvement",
            "impact_multiplier": 0.50,
            "effort": "high",
        },
        {
            "action": "Add late payment interest clause at prime + 2%",
            "impact_type": "cash_improvement",
            "impact_multiplier": 0.10,
            "effort": "low",
        },
    ],
    "pricing": [
        {
            "action": "Add annual cost-index repricing mechanism",
            "impact_type": "margin_protection",
            "impact_multiplier": 0.20,
            "effort": "medium",
        },
    ],
    "warranty": [
        {
            "action": "Limit warranty to manufacturing defects only, excluding design",
            "impact_type": "warranty_cost_reduction",
            "impact_multiplier": 0.40,
            "effort": "high",
        },
        {
            "action": "Cap warranty period at 12 months from shipment",
            "impact_type": "warranty_cost_reduction",
            "impact_multiplier": 0.25,
            "effort": "medium",
        },
    ],
    "indemnification": [
        {
            "action": "Ensure mutual indemnification, not manufacturer-only",
            "impact_type": "liability_reduction",
            "impact_multiplier": 0.30,
            "effort": "high",
        },
    ],
    "liability_cap": [
        {
            "action": "Set aggregate liability cap at 12 months of fees paid",
            "impact_type": "liability_reduction",
            "impact_multiplier": 0.50,
            "effort": "high",
        },
    ],
    "termination_for_convenience": [
        {
            "action": "Require minimum 90-day notice for convenience termination",
            "impact_type": "exit_cost_reduction",
            "impact_multiplier": 0.30,
            "effort": "medium",
        },
        {
            "action": "Add termination fee covering WIP + committed materials + margin on cancelled orders",
            "impact_type": "exit_cost_reduction",
            "impact_multiplier": 0.60,
            "effort": "high",
        },
    ],
    "engineering_changes": [
        {
            "action": "Require customer to bear all ECO-related material obsolescence costs",
            "impact_type": "material_liability_reduction",
            "impact_multiplier": 0.45,
            "effort": "medium",
        },
    ],
    "force_majeure": [
        {
            "action": "Include supply chain disruption in force majeure definition",
            "impact_type": "disruption_protection",
            "impact_multiplier": 0.20,
            "effort": "low",
        },
    ],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
import re


def classify_clause(title, text):
    """Classify a clause into a family based on keyword matching.
    Returns (family_name, confidence_score).

    Title matches are weighted 3x higher than body matches to ensure
    section headings drive classification.
    """
    title_lower = title.lower()
    text_lower = text.lower()
    best_family = None
    best_score = 0.0

    for family, config in CLAUSE_FAMILIES.items():
        score = 0
        matches = 0
        for pattern in config["keywords"]:
            title_hits = re.findall(pattern, title_lower, re.IGNORECASE)
            body_hits = re.findall(pattern, text_lower, re.IGNORECASE)
            hit_count = len(title_hits) * 3 + len(body_hits)
            if hit_count > 0:
                matches += 1
                score += hit_count

        if matches > 0:
            keyword_coverage = matches / len(config["keywords"])
            normalized = keyword_coverage * (1 + min(score / 10, 1.0))
            if normalized > best_score:
                best_score = normalized
                best_family = family

    confidence = min(best_score / 1.5, 1.0)
    return best_family or "scope_of_work", round(confidence, 2)


def get_zone(family):
    """Return the zone for a clause family."""
    config = CLAUSE_FAMILIES.get(family)
    return config["zone"] if config else "manufacturer"


def get_risk_weight(family):
    """Return the base risk weight (1–5) for a clause family."""
    config = CLAUSE_FAMILIES.get(family)
    return config["risk_weight"] if config else 2


def get_recommendations(family, clause_data=None):
    """Return prescriptive recommendations for a clause family."""
    templates = RECOMMENDATION_TEMPLATES.get(family, [])
    recommendations = []
    for tmpl in templates:
        rec = {
            "action": tmpl["action"],
            "impact_type": tmpl["impact_type"],
            "impact_multiplier": tmpl["impact_multiplier"],
            "effort": tmpl["effort"],
        }
        recommendations.append(rec)
    return recommendations


def get_dependency_rules_for(family):
    """Return all dependency rules where this family is source or target."""
    rules = []
    for src, tgt, rel_type, label, effect in DEPENDENCY_RULES:
        if src == family or tgt == family:
            rules.append({
                "source": src,
                "target": tgt,
                "type": rel_type,
                "label": label,
                "interaction_effect": effect,
            })
    return rules
