"""
Contract Parser — Regex-based clause splitting and structured extraction
for EMS manufacturing agreements.

Extracts obligations, actors, triggers, timing, financial terms, and
cross-references from each clause.
"""

import re
import uuid

from ems_ontology import (
    ACTOR_PATTERNS,
    classify_clause,
    get_recommendations,
    get_risk_weight,
    get_zone,
)

# ---------------------------------------------------------------------------
# Clause splitting
# ---------------------------------------------------------------------------

# Matches top-level numbered sections: "1.", "2.", etc.  followed by title
_SECTION_PATTERN = re.compile(
    r"^(\d{1,2})\.\s+([A-Z][A-Z\s,&/\-]+)\s*$",
    re.MULTILINE,
)

# Matches sub-sections: "1.1", "1.2", etc.
_SUBSECTION_PATTERN = re.compile(
    r"^(\d{1,2}\.\d{1,2})\s+",
    re.MULTILINE,
)


def split_into_clauses(text):
    """Split contract text into top-level clause objects.

    Returns list of {"number", "title", "text", "subsections"}.
    """
    matches = list(_SECTION_PATTERN.finditer(text))
    if not matches:
        # Fallback: treat entire text as one clause
        return [{
            "number": "1",
            "title": "Agreement",
            "text": text.strip(),
            "subsections": [],
        }]

    clauses = []
    for i, m in enumerate(matches):
        number = m.group(1)
        title = m.group(2).strip().rstrip(".")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # Extract sub-sections
        subs = list(_SUBSECTION_PATTERN.finditer(body))
        subsections = []
        for j, s in enumerate(subs):
            sub_start = s.start()
            sub_end = subs[j + 1].start() if j + 1 < len(subs) else len(body)
            subsections.append({
                "number": s.group(1),
                "text": body[sub_start:sub_end].strip(),
            })

        clauses.append({
            "number": number,
            "title": title,
            "text": body,
            "subsections": subsections,
        })

    return clauses


# ---------------------------------------------------------------------------
# Obligation extraction
# ---------------------------------------------------------------------------

_OBLIGATION_PATTERNS = [
    # (pattern, obligation_type)
    (re.compile(r"(\w[\w\s]*?)\s+shall\s+not\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "prohibition"),
    (re.compile(r"(\w[\w\s]*?)\s+shall\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "ongoing"),
    (re.compile(r"(\w[\w\s]*?)\s+must\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "ongoing"),
    (re.compile(r"(\w[\w\s]*?)\s+will\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "ongoing"),
    (re.compile(r"(\w[\w\s]*?)\s+agrees?\s+to\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "commitment"),
    (re.compile(r"(\w[\w\s]*?)\s+is\s+responsible\s+for\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "ongoing"),
    (re.compile(r"(\w[\w\s]*?)\s+(?:may|has\s+the\s+right\s+to)\s+([\w\s,]+?)(?:\.|;|$)", re.IGNORECASE), "right"),
]


def extract_obligations(text):
    """Extract structured obligations from clause text."""
    obligations = []
    seen = set()
    for pattern, obl_type in _OBLIGATION_PATTERNS:
        for m in pattern.finditer(text):
            actor_raw = m.group(1).strip()[-40:]  # Last 40 chars of actor phrase
            verb_phrase = m.group(2).strip()[:80]  # First 80 chars of verb

            # Resolve actor to canonical name
            actor = _resolve_actor(actor_raw)

            key = (actor, verb_phrase[:30])
            if key in seen:
                continue
            seen.add(key)

            obligations.append({
                "actor": actor,
                "verb": verb_phrase,
                "type": obl_type,
            })
    return obligations[:10]  # Cap at 10 per clause for readability


def _resolve_actor(raw):
    """Map raw actor text to canonical actor name."""
    raw_lower = raw.lower()
    for pattern, actor in ACTOR_PATTERNS.items():
        if re.search(pattern, raw_lower, re.IGNORECASE):
            return actor
    # Heuristic fallback
    if "customer" in raw_lower or "buyer" in raw_lower:
        return "customer"
    if "manufacturer" in raw_lower or "supplier" in raw_lower:
        return "manufacturer"
    return "both"


# ---------------------------------------------------------------------------
# Actor extraction
# ---------------------------------------------------------------------------

def extract_actors(text):
    """Find which actors are mentioned in a clause."""
    actors = set()
    text_lower = text.lower()
    for pattern, actor in ACTOR_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            actors.add(actor)
    # Always include at least one
    if not actors:
        actors.add("both")
    return sorted(actors)


# ---------------------------------------------------------------------------
# Timing extraction
# ---------------------------------------------------------------------------

_TIMING_PATTERNS = [
    (r"within\s+(\d+)\s+(business\s+)?days?", "deadline"),
    (r"(\d+)\s+(business\s+)?days?\s+(?:prior|before|after|of|from)", "deadline"),
    (r"net\s+(\d+)\s+days?", "payment_terms"),
    (r"(\d+)\s+(?:calendar\s+)?months?", "duration"),
    (r"(?:annual|quarterly|monthly|weekly)", "frequency"),
    (r"no\s+(?:more|less)\s+than\s+(?:once\s+per\s+)?(\w+)", "frequency"),
    (r"(?:upon|immediately|promptly)", "immediate"),
]


def extract_timing(text):
    """Extract timing/deadline information from clause text."""
    timing = {}
    text_lower = text.lower()
    for pattern, timing_type in _TIMING_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            timing[timing_type] = m.group(0)
    return timing


# ---------------------------------------------------------------------------
# Trigger extraction
# ---------------------------------------------------------------------------

_TRIGGER_PHRASES = [
    r"in\s+the\s+event\s+(?:of|that)\s+([\w\s,]+?)(?:\.|,|;)",
    r"(?:if|where|when|should)\s+([\w\s,]+?)(?:\.|,|;)",
    r"upon\s+([\w\s,]+?)(?:\.|,|;)",
    r"in\s+case\s+of\s+([\w\s,]+?)(?:\.|,|;)",
    r"(?:triggered?\s+by|arising\s+from)\s+([\w\s,]+?)(?:\.|,|;)",
]


def extract_triggers(text):
    """Extract trigger conditions from clause text."""
    triggers = []
    seen = set()
    for pattern in _TRIGGER_PHRASES:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            trigger = m.group(1).strip()[:60]
            trigger_key = trigger[:20].lower()
            if trigger_key not in seen:
                seen.add(trigger_key)
                triggers.append(trigger)
    return triggers[:6]  # Cap for readability


# ---------------------------------------------------------------------------
# Financial term extraction
# ---------------------------------------------------------------------------

_DOLLAR_PATTERN = re.compile(
    r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|thousand|billion))?",
    re.IGNORECASE,
)
_PERCENT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:percent|%)",
    re.IGNORECASE,
)
_PAYMENT_PATTERN = re.compile(
    r"net\s+(\d+)\s+days?",
    re.IGNORECASE,
)


def extract_financial_terms(text):
    """Extract dollar amounts, percentages, payment terms."""
    financials = {}

    dollars = _DOLLAR_PATTERN.findall(text)
    if dollars:
        financials["dollar_amounts"] = dollars

    percents = _PERCENT_PATTERN.findall(text)
    if percents:
        financials["percentages"] = [f"{p}%" for p in percents]

    payment = _PAYMENT_PATTERN.search(text)
    if payment:
        financials["payment_days"] = int(payment.group(1))

    return financials


# ---------------------------------------------------------------------------
# Cross-reference extraction
# ---------------------------------------------------------------------------

_XREF_PATTERN = re.compile(
    r"(?:Section|Clause|Article|paragraph)\s+(\d{1,2}(?:\.\d{1,2})?)",
    re.IGNORECASE,
)


def extract_cross_references(text, own_number):
    """Find references to other sections in the clause text."""
    refs = set()
    for m in _XREF_PATTERN.finditer(text):
        ref = m.group(1)
        # Don't count self-references
        if not ref.startswith(own_number + ".") and ref != own_number:
            # Normalize to top-level section number
            top = ref.split(".")[0]
            refs.add(top)
    return sorted(refs)


# ---------------------------------------------------------------------------
# Ambiguity detection
# ---------------------------------------------------------------------------

_AMBIGUITY_MARKERS = [
    (r"\breasonabl[ey]\b", "Uses 'reasonable' without specific standard"),
    (r"\bmaterial(?:ly)?\b", "Uses 'material' without quantitative threshold"),
    (r"\bbest\s+efforts?\b", "Uses 'best efforts' (undefined standard)"),
    (r"\bcommercially\s+reasonable\b", "Uses 'commercially reasonable' (subjective)"),
    (r"\bpromptly\b", "Uses 'promptly' without specific deadline"),
    (r"\bsubstantial(?:ly)?\b", "Uses 'substantially' without measurable criteria"),
    (r"\bfrom\s+time\s+to\s+time\b", "Uses 'from time to time' (timing unclear)"),
    (r"\bas\s+(?:mutually\s+)?agreed\b", "Defers to future agreement (may not happen)"),
    (r"\bunless\s+otherwise\b", "Contains exception clause that may override"),
]


def detect_ambiguities(text):
    """Find language patterns that indicate ambiguous terms."""
    flags = []
    for pattern, description in _AMBIGUITY_MARKERS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(description)
    return flags


# ---------------------------------------------------------------------------
# Risk rating computation
# ---------------------------------------------------------------------------

def compute_risk_rating(family, obligations, triggers, ambiguities, financials):
    """Compute composite risk rating (1–5) from multiple signals."""
    base = get_risk_weight(family)

    # Adjust for obligation density
    if len(obligations) > 5:
        base = min(base + 1, 5)

    # Adjust for trigger complexity
    if len(triggers) > 3:
        base = min(base + 1, 5)

    # Adjust for ambiguity
    if len(ambiguities) > 2:
        base = min(base + 1, 5)

    # Adjust for financial exposure
    if financials.get("dollar_amounts"):
        base = min(base + 1, 5)

    return min(base, 5)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(family, classification_score, ambiguities, obligations):
    """Compute extraction confidence (0.0–1.0)."""
    confidence = classification_score

    # Boost if we found clear obligations
    if len(obligations) >= 2:
        confidence = min(confidence + 0.1, 1.0)

    # Penalty for high ambiguity
    if len(ambiguities) > 3:
        confidence = max(confidence - 0.15, 0.1)

    return round(confidence, 2)


# ---------------------------------------------------------------------------
# Main parse orchestrator
# ---------------------------------------------------------------------------

def parse_contract(text):
    """Parse full contract text into structured clause objects.

    Returns a dict with contract metadata, clauses list, and raw data
    for graph building and economics computation.
    """
    raw_clauses = split_into_clauses(text)
    clauses = []
    clause_number_map = {c["number"]: i for i, c in enumerate(raw_clauses)}

    for raw in raw_clauses:
        family, cls_score = classify_clause(raw["title"], raw["text"])
        zone = get_zone(family)
        actors = extract_actors(raw["text"])
        obligations = extract_obligations(raw["text"])
        triggers = extract_triggers(raw["text"])
        timing = extract_timing(raw["text"])
        financials = extract_financial_terms(raw["text"])
        ambiguities = detect_ambiguities(raw["text"])
        cross_refs = extract_cross_references(raw["text"], raw["number"])
        risk = compute_risk_rating(family, obligations, triggers, ambiguities, financials)
        confidence = compute_confidence(family, cls_score, ambiguities, obligations)
        recommendations = get_recommendations(family)

        # Determine primary owner from obligations
        actor_counts = {}
        for obl in obligations:
            a = obl["actor"]
            actor_counts[a] = actor_counts.get(a, 0) + 1
        primary_owner = max(actor_counts, key=actor_counts.get) if actor_counts else "both"

        clause_id = f"clause-{raw['number'].zfill(3)}"

        clause = {
            "id": clause_id,
            "number": raw["number"],
            "title": raw["title"],
            "family": family,
            "zone": zone,
            "source_text": raw["text"][:1500],  # Truncate for JSON size
            "actors": actors,
            "primary_owner": primary_owner,
            "obligations": obligations,
            "triggers": triggers,
            "timing": timing,
            "financial_terms": financials,
            "cross_references": cross_refs,
            "risk_rating": risk,
            "confidence": confidence,
            "ambiguity_flags": ambiguities,
            "recommendations": recommendations,
            "audit_trail": [
                f"Classified as '{family}' (score: {cls_score})",
                f"Risk rating {risk} from base weight {get_risk_weight(family)} + signal adjustments",
                f"Confidence {confidence} based on classification + obligation extraction",
            ],
        }
        clauses.append(clause)

    contract_id = f"ct-{uuid.uuid4().hex[:12]}"

    return {
        "contract_id": contract_id,
        "title": _extract_title(text),
        "clauses": clauses,
    }


def _extract_title(text):
    """Try to extract the agreement title from the first few lines."""
    lines = text.strip().split("\n")
    for line in lines[:5]:
        line = line.strip()
        if len(line) > 10 and line.isupper():
            return line.title()
        if "agreement" in line.lower():
            return line.strip()
    return "EMS Manufacturing Agreement"
