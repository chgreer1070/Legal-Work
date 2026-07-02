"""
Claude API integration for extracting FX clauses from contract text.
"""

import json
import logging

import anthropic

from fx.config import CLAUDE_MODEL, CLAUSE_EXTRACTION_MAX_TOKENS
from fx.ingestion.schema import FXClauseSchema, ExtractionResult
from fx.audit.logger import log_event

SYSTEM_PROMPT = """You are a legal contract analyst specializing in foreign exchange adjustment clauses.
You extract structured data from contract text with high precision, including translating the
contract's adjustment mechanics into a precise arithmetic formula. Always return valid JSON."""

EXTRACTION_PROMPT = """Extract all foreign exchange (FX) adjustment clauses from this contract text.

For each FX clause found, identify:
- currency_pair: The currency pair (e.g., "USD/BRL", "USD/MXN")
- base_rate: The contractual base/reference exchange rate (numeric)
- threshold_pct: The deviation percentage that triggers an adjustment (numeric, e.g., 3.0 for 3%)
- review_frequency: How often the rate is reviewed ("monthly", "quarterly", "annual")
- adjustment_method: How adjustments are applied ("full_passthrough", "shared", "capped")
- notification_period_days: Required notice period in days before adjustment (integer)
- clause_text: The verbatim text of the clause from the contract
- formula_type: The calculation structure the clause defines ("full_passthrough", "shared", "capped", "corridor", "custom")
- formula_expression: The clause's adjustment calculation, translated into a single arithmetic expression (see rules below)
- formula_description: One plain-English sentence describing the calculation
- confidence_score: Your confidence in the extraction accuracy (0.0 to 1.0)

FORMULA EXPRESSION RULES:
The expression computes the USD adjustment/exposure amount for a settlement period.
It may use ONLY:
- variables: volume (USD transaction volume in the period), base_rate, current_rate,
  rate_delta (current_rate - base_rate, signed), abs_rate_delta, deviation
  ((current_rate - base_rate) / base_rate, signed fraction), abs_deviation,
  threshold (the threshold percentage as a fraction, e.g. 0.03)
- functions: min(), max(), abs()
- operators: + - * / **
- numeric literals

Encode all contract-specific constants (sharing ratios, caps, corridors) as numeric
literals taken from the clause language. Examples:
- Full passthrough of the rate movement: "volume * abs_deviation"
- 50/50 sharing of movement beyond a 3% corridor: "volume * max(0, abs_deviation - 0.03) * 0.5"
- Passthrough capped at 10%: "volume * min(abs_deviation, 0.10)"
- 60% sharing beyond a 2% corridor, capped at 8%: "volume * min(max(0, abs_deviation - 0.02) * 0.6, 0.08)"

If the clause does not define a computable adjustment calculation, set formula_expression
to "" and formula_type to your best classification of the method.

Return a JSON object with a single key "clauses" containing an array of clause objects.
If no FX clauses are found, return {"clauses": []}.

CONTRACT TEXT:
{contract_text}"""

# Strict JSON schema for structured outputs — guarantees parseable responses.
CLAUSE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "currency_pair": {"type": "string"},
                    "base_rate": {"type": "number"},
                    "threshold_pct": {"type": "number"},
                    "review_frequency": {"type": "string", "enum": ["monthly", "quarterly", "annual"]},
                    "adjustment_method": {"type": "string", "enum": ["full_passthrough", "shared", "capped"]},
                    "notification_period_days": {"type": "integer"},
                    "clause_text": {"type": "string"},
                    "formula_type": {"type": "string", "enum": ["full_passthrough", "shared", "capped", "corridor", "custom"]},
                    "formula_expression": {"type": "string"},
                    "formula_description": {"type": "string"},
                    "confidence_score": {"type": "number"},
                },
                "required": [
                    "currency_pair", "base_rate", "threshold_pct", "review_frequency",
                    "adjustment_method", "notification_period_days", "clause_text",
                    "formula_type", "formula_expression", "formula_description",
                    "confidence_score",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["clauses"],
    "additionalProperties": False,
}


def extract_clauses(contract_text: str, contract_id: int | None = None) -> ExtractionResult:
    """
    Extract structured FX clause data from contract text.

    Primary path is the Claude API. When the API is unavailable (no
    credentials, network failure, exhausted retries) the deterministic
    rule-based extractor takes over so ingestion keeps working — its
    clauses carry lower confidence scores and an audit annotation.

    Returns an ExtractionResult with validated clause schemas.
    """
    from fx.utils import call_claude_with_retry, get_anthropic_client

    # Plain replace, not str.format(): the template contains literal JSON
    # braces that format() would misread as fields (KeyError '"clauses"').
    prompt = EXTRACTION_PROMPT.replace("{contract_text}", contract_text)
    try:
        client = get_anthropic_client()
        request_kwargs = dict(
            model=CLAUDE_MODEL,
            max_tokens=CLAUSE_EXTRACTION_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            # Structured outputs guarantee schema-valid JSON on supporting models
            response = call_claude_with_retry(
                client,
                output_config={"format": {"type": "json_schema", "schema": CLAUSE_OUTPUT_SCHEMA}},
                **request_kwargs,
            )
        except anthropic.BadRequestError:
            # Model doesn't support structured outputs — fall back to prompt-only
            # JSON; _parse_clauses handles prose-wrapped responses.
            logging.getLogger(__name__).warning(
                "Structured outputs rejected by model %s; retrying without", CLAUDE_MODEL
            )
            response = call_claude_with_retry(client, **request_kwargs)
    except Exception as e:
        logging.getLogger(__name__).warning(
            "Claude extraction unavailable (%s) — using rule-based extractor", e
        )
        return _extract_rule_based(contract_text, contract_id, reason=str(e))

    raw_text = response.content[0].text

    # Parse JSON from response
    clauses = _parse_clauses(raw_text)

    # Log to audit trail
    log_event(
        event_type="clause_extraction",
        entity_type="contract",
        entity_id=contract_id,
        action=f"Extracted {len(clauses)} FX clauses",
        actor="claude_api",
        details={"clause_count": len(clauses), "model": CLAUDE_MODEL},
        ai_model_used=CLAUDE_MODEL,
        ai_prompt=prompt,
        ai_response=raw_text,
    )

    return ExtractionResult(clauses=clauses, raw_response=raw_text)


def _extract_rule_based(contract_text: str, contract_id: int | None, reason: str) -> ExtractionResult:
    """Run the deterministic extractor and audit the fallback."""
    from fx.ingestion.rule_extractor import extract_clauses_rule_based

    clauses = extract_clauses_rule_based(contract_text)
    raw_response = json.dumps([c.model_dump() for c in clauses])

    log_event(
        event_type="clause_extraction",
        entity_type="contract",
        entity_id=contract_id,
        action=f"Extracted {len(clauses)} FX clauses (rule-based fallback)",
        actor="rule_extractor",
        details={
            "clause_count": len(clauses),
            "extractor": "rule_based",
            "fallback_reason": reason[:200],
        },
    )

    return ExtractionResult(clauses=clauses, raw_response=raw_response)


def _parse_clauses(raw_text: str) -> list[FXClauseSchema]:
    """Parse and validate clause JSON from Claude's response."""
    # Try to find JSON in the response
    text = raw_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    logger = logging.getLogger(__name__)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Use brace-depth counter to find matching JSON object
        data = _extract_json_by_depth(text)
        if data is None:
            logger.warning("Could not find valid JSON in Claude response: %s", text[:200])
            return []

    clause_list = data.get("clauses", []) if isinstance(data, dict) else data

    validated = []
    for item in clause_list:
        try:
            clause = FXClauseSchema(**item)
            validated.append(clause)
        except Exception as e:
            logger.warning("Skipping malformed clause: %s — raw: %s", e, item)
            continue

    return validated


def _extract_json_by_depth(text: str):
    """Extract JSON object using brace-depth counting instead of rfind."""
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
