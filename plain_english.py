"""
Plain English Translation Layer — converts structured clause data into
business-readable explanations without dumbing down the meaning.

Uses template-based translation keyed by clause family, with slot-filling
from extracted obligations, actors, and timing.
"""

# ---------------------------------------------------------------------------
# Family-specific templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "forecasting": {
        "summary": (
            "The customer must provide a rolling demand forecast to the manufacturer. "
            "Part of this forecast creates a binding purchase commitment — meaning the "
            "customer is on the hook for those quantities. The non-binding portion is "
            "for planning only, but the manufacturer will likely buy materials against "
            "it, creating financial exposure if the forecast drops."
        ),
        "what_matters": "Forecast accuracy directly drives inventory risk, capacity planning, and cash exposure.",
        "watch_for": "Gap between binding window and actual material lead times — the manufacturer may be buying materials beyond the binding commitment.",
    },
    "purchase_orders": {
        "summary": (
            "Purchase orders formalize the customer's actual buy commitment. "
            "This clause defines how POs are issued, accepted, and cancelled, "
            "including what penalties apply for late cancellations."
        ),
        "what_matters": "PO cancellation terms determine who absorbs cost when demand changes.",
        "watch_for": "Cancellation windows that don't align with material procurement lead times.",
    },
    "engineering_changes": {
        "summary": (
            "The customer can change product designs at any time. The manufacturer "
            "must evaluate the impact and the customer pays for resulting costs — "
            "including scrapped materials, retooling, and requalification."
        ),
        "what_matters": "ECOs create unplanned cost and schedule disruption. Frequency matters as much as individual impact.",
        "watch_for": "Whether the cost allocation for ECO-driven obsolete inventory is clearly defined.",
    },
    "scope_of_work": {
        "summary": (
            "This defines what the manufacturer is contracted to do — the specific "
            "manufacturing services, testing, and deliverables. Everything else in "
            "the contract flows from this scope definition."
        ),
        "what_matters": "Scope creep risk — if the scope is vague, disputes about what's included are likely.",
        "watch_for": "Ambiguous language about what constitutes 'services' vs. out-of-scope work.",
    },
    "quality_standards": {
        "summary": (
            "The manufacturer must meet specific quality standards (typically ISO 9001 "
            "and IPC workmanship standards). Quality failures can trigger warranty "
            "claims, production holds, and financial penalties."
        ),
        "what_matters": "Quality standards define the baseline against which all product acceptance is measured.",
        "watch_for": "Whether the standard is tied only to manufacturing defects or also to design compliance.",
    },
    "inspection_rights": {
        "summary": (
            "The customer has the right to audit and inspect the manufacturer's "
            "facility, processes, and records. This gives the customer oversight "
            "but creates operational disruption for the manufacturer."
        ),
        "what_matters": "Audit frequency and scope can become a significant operational burden.",
        "watch_for": "Unlimited audit rights with minimal notice periods.",
    },
    "delivery": {
        "summary": (
            "This defines when and how products must be delivered, including "
            "shipping terms (Incoterms), on-time delivery targets, and what "
            "happens when deliveries are late."
        ),
        "what_matters": "Delivery performance directly affects the customer's production schedule and revenue.",
        "watch_for": "OTD targets that don't account for supplier delays or force majeure.",
    },
    "reporting": {
        "summary": (
            "The manufacturer must provide regular status reports, KPIs, and "
            "business reviews to the customer."
        ),
        "what_matters": "Reporting requirements consume resources and create documentation obligations.",
        "watch_for": "Excessive reporting frequency without clear business value.",
    },
    "materials_management": {
        "summary": (
            "The manufacturer procures materials according to the customer's "
            "approved vendor and manufacturer lists. Material sourcing, tracking, "
            "and inventory management rules are defined here."
        ),
        "what_matters": "Material management rules determine procurement flexibility and inventory liability.",
        "watch_for": "Restrictions that prevent the manufacturer from finding cost-effective alternatives.",
    },
    "long_lead_ncnr": {
        "summary": (
            "Some components have long lead times and cannot be cancelled or "
            "returned once ordered (NCNR). The customer authorizes these purchases "
            "and takes financial responsibility for them — even if demand drops."
        ),
        "what_matters": "NCNR commitments are the single largest source of stranded inventory risk.",
        "watch_for": "Whether the customer authorization process is clear and whether there's a cap on total NCNR exposure.",
    },
    "consigned_inventory": {
        "summary": (
            "The customer provides certain materials that the manufacturer uses "
            "in production. The customer retains ownership, but the manufacturer "
            "is responsible for protecting them while in possession."
        ),
        "what_matters": "Consigned materials shift ownership risk but create custody liability for the manufacturer.",
        "watch_for": "Liability for losses caused by defective consigned materials.",
    },
    "safety_stock": {
        "summary": (
            "The manufacturer must maintain buffer inventory to protect against "
            "supply chain variability. These stocking levels add working capital "
            "pressure and E&O exposure."
        ),
        "what_matters": "Safety stock ties up cash and creates additional E&O exposure if demand drops.",
        "watch_for": "Who bears the carrying cost and who owns the safety stock if it becomes excess.",
    },
    "pricing": {
        "summary": (
            "Product pricing is defined in the SOW pricing exhibit. The contract "
            "includes mechanisms for price adjustments (up and down) based on cost "
            "changes and continuous improvement targets."
        ),
        "what_matters": "Pricing mechanisms determine whether the manufacturer can protect margin against cost inflation.",
        "watch_for": "One-sided cost reduction targets without corresponding price increase mechanisms.",
    },
    "payment_terms": {
        "summary": (
            "The manufacturer invoices upon shipment and the customer pays within "
            "the agreed payment window. Late payment penalties and setoff rights "
            "are defined here."
        ),
        "what_matters": "Payment terms directly affect working capital. Longer terms = more cash tied up in receivables.",
        "watch_for": "Broad setoff rights that let the customer withhold payment for disputed amounts.",
    },
    "excess_obsolete": {
        "summary": (
            "When inventory can no longer be used — because forecasts dropped, "
            "orders were cancelled, or designs changed — this clause determines "
            "who pays for it. The customer is typically required to buy back "
            "excess and obsolete inventory."
        ),
        "what_matters": "E&O is where forecast risk, ECO risk, and termination risk all converge into real cash exposure.",
        "watch_for": "Vague definitions of 'excess' and 'obsolete' — and how quickly the customer must act.",
    },
    "warranty": {
        "summary": (
            "The manufacturer guarantees products meet specifications for a "
            "defined period. If defects are found, the manufacturer must repair, "
            "replace, or refund. But the warranty typically excludes design "
            "defects — only manufacturing workmanship is covered."
        ),
        "what_matters": "Warranty scope and duration determine the manufacturer's ongoing cost exposure after shipment.",
        "watch_for": "Whether warranty covers only manufacturing defects or extends to design and field performance.",
    },
    "rma_returns": {
        "summary": (
            "Defines the process for returning defective products. The manufacturer "
            "must analyze failures and either repair under warranty or charge for "
            "non-warranty repairs."
        ),
        "what_matters": "RMA volume and turnaround time affect operational cost and customer satisfaction.",
        "watch_for": "Whether failure analysis costs are fairly allocated between warranty and non-warranty returns.",
    },
    "indemnification": {
        "summary": (
            "Each party agrees to protect the other from third-party claims in "
            "specific situations. The manufacturer typically indemnifies for "
            "manufacturing defects; the customer indemnifies for design issues."
        ),
        "what_matters": "Indemnification can create uncapped liability exposure if not properly bounded.",
        "watch_for": "Whether indemnification is mutual and whether it's subject to the liability cap.",
    },
    "liability_cap": {
        "summary": (
            "Sets the maximum financial exposure for each party. Typically capped "
            "at 12 months of fees. Consequential damages are usually excluded. "
            "But watch for carveouts — indemnification and confidentiality "
            "breaches often sit outside the cap."
        ),
        "what_matters": "The liability cap is the ultimate financial safety net. Carveouts can render it meaningless.",
        "watch_for": "Broad carveouts that effectively eliminate the cap for the highest-risk obligations.",
    },
    "insurance": {
        "summary": (
            "The manufacturer must maintain specified insurance coverage "
            "throughout the contract term, including general liability and "
            "product liability policies."
        ),
        "what_matters": "Insurance provides a financial backstop for indemnification obligations.",
        "watch_for": "Whether coverage amounts are adequate relative to the liability cap.",
    },
    "force_majeure": {
        "summary": (
            "Neither party is liable for failures caused by events beyond their "
            "control — natural disasters, pandemics, government actions, etc. "
            "If the event lasts too long, either party can terminate."
        ),
        "what_matters": "Force majeure defines the boundary of performance obligations during disruptions.",
        "watch_for": "Whether supply chain disruptions are included and what the termination threshold is.",
    },
    "termination_for_cause": {
        "summary": (
            "Either party can terminate if the other materially breaches and "
            "fails to fix it within the cure period. Bankruptcy also triggers "
            "termination rights."
        ),
        "what_matters": "Termination for cause determines consequences when the relationship breaks down.",
        "watch_for": "Whether 'material breach' is defined with specificity or left vague.",
    },
    "termination_for_convenience": {
        "summary": (
            "Either party can walk away with advance notice, even without a "
            "reason. The customer must buy all inventory and WIP, plus pay a "
            "termination fee. This is the 'what if we just stop' clause."
        ),
        "what_matters": "Convenience termination is the most likely exit path. The unwind cost formula is critical.",
        "watch_for": "Whether the termination fee covers the manufacturer's actual stranded costs.",
    },
    "transition_assistance": {
        "summary": (
            "After termination, the manufacturer must help transfer production "
            "to a new provider — including documentation, tooling return, and "
            "last-time buy support."
        ),
        "what_matters": "Transition period and scope determine whether production transfer is smooth or chaotic.",
        "watch_for": "Whether transition assistance is compensated and how long it lasts.",
    },
    "ip_tooling": {
        "summary": (
            "Customer owns its designs, specs, and firmware. Tooling built for "
            "the customer is customer property. The manufacturer's process "
            "know-how remains the manufacturer's IP."
        ),
        "what_matters": "IP ownership determines what happens to tools and knowledge when the contract ends.",
        "watch_for": "Ambiguity about who owns process improvements that involve customer IP.",
    },
    "confidentiality": {
        "summary": (
            "Both parties must protect each other's confidential information. "
            "This includes trade secrets, pricing, and technical data. "
            "Obligations survive after the contract ends."
        ),
        "what_matters": "Confidentiality breaches can sit outside the liability cap as a carveout.",
        "watch_for": "Duration of survival clause and breadth of 'confidential information' definition.",
    },
    "compliance": {
        "summary": (
            "The manufacturer must comply with all applicable regulations — "
            "RoHS, REACH, conflict minerals, and other product-specific "
            "environmental and safety requirements."
        ),
        "what_matters": "Non-compliance can halt shipments and create regulatory liability for both parties.",
        "watch_for": "Whether the customer shares responsibility for product-specific regulatory requirements.",
    },
    "dispute_resolution": {
        "summary": (
            "Disputes must first be escalated to senior executives for "
            "negotiation. If that fails, the contract specifies binding "
            "arbitration under defined rules and jurisdiction."
        ),
        "what_matters": "Dispute resolution mechanisms determine how fast and expensive conflicts get resolved.",
        "watch_for": "Whether arbitration is binding, where it takes place, and who bears costs.",
    },
    "term_renewal": {
        "summary": (
            "The contract has an initial term with automatic renewal unless "
            "either party opts out with advance notice."
        ),
        "what_matters": "Auto-renewal can lock parties in if notice deadlines are missed.",
        "watch_for": "Whether renewal preserves all original terms or allows renegotiation.",
    },
}


# ---------------------------------------------------------------------------
# Translation function
# ---------------------------------------------------------------------------

def translate_clause(clause_data):
    """Generate plain-English translation for a parsed clause.

    Returns dict with summary, what_matters, watch_for, and role-specific views.
    """
    family = clause_data.get("family", "scope_of_work")
    template = TEMPLATES.get(family, TEMPLATES["scope_of_work"])

    # Build role-specific explanations
    roles = _build_role_views(clause_data, template)

    return {
        "plain_english": template["summary"],
        "what_matters": template["what_matters"],
        "watch_for": template["watch_for"],
        "role_views": roles,
    }


def _build_role_views(clause_data, template):
    """Generate role-specific explanations for the same clause."""
    family = clause_data.get("family", "")
    risk = clause_data.get("risk_rating", 2)
    actors = clause_data.get("actors", [])
    financials = clause_data.get("financial_terms", {})

    base = template["summary"]
    matters = template["what_matters"]

    roles = {
        "executive": f"{base} Bottom line: {matters}",
        "program_manager": (
            f"{base} Operationally, this means tracking compliance with "
            f"this obligation across the program lifecycle."
        ),
        "supply_chain": _supply_chain_view(clause_data, template),
        "finance": _finance_view(clause_data, template),
        "operations": (
            f"{base} Operations must ensure processes and systems are in "
            f"place to meet these requirements."
        ),
        "quality": _quality_view(clause_data, template),
        "legal": (
            f"{base} Key risk: {template['watch_for']} "
            f"Risk rating: {risk}/5. "
            f"Ambiguities: {len(clause_data.get('ambiguity_flags', []))} flagged."
        ),
    }
    return roles


def _supply_chain_view(clause_data, template):
    family = clause_data.get("family", "")
    if family in ("forecasting", "materials_management", "long_lead_ncnr",
                   "safety_stock", "consigned_inventory", "excess_obsolete"):
        return (
            f"{template['summary']} Supply chain impact: {template['what_matters']} "
            f"Action required: monitor material commitments against this clause."
        )
    return f"{template['summary']} Limited direct supply chain impact."


def _finance_view(clause_data, template):
    financials = clause_data.get("financial_terms", {})
    dollars = financials.get("dollar_amounts", [])
    payment = financials.get("payment_days")

    finance_note = template["what_matters"]
    if dollars:
        finance_note += f" Financial terms referenced: {', '.join(dollars)}."
    if payment:
        finance_note += f" Payment terms: Net {payment} days."

    return f"{template['summary']} Financial impact: {finance_note}"


def _quality_view(clause_data, template):
    family = clause_data.get("family", "")
    if family in ("quality_standards", "inspection_rights", "warranty",
                   "rma_returns", "compliance"):
        return (
            f"{template['summary']} Quality team must ensure compliance systems "
            f"and documentation meet these requirements. {template['watch_for']}"
        )
    return f"{template['summary']} Limited direct quality impact."
