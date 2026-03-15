"""
Claude API integration for extracting FX clauses from contract text.
"""

import json
import anthropic

from fx.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUSE_EXTRACTION_MAX_TOKENS
from fx.ingestion.schema import FXClauseSchema, ExtractionResult
from fx.audit.logger import log_event

SYSTEM_PROMPT = """You are a legal contract analyst specializing in foreign exchange adjustment clauses.
You extract structured data from contract text with high precision. Always return valid JSON."""

EXTRACTION_PROMPT = """Extract all foreign exchange (FX) adjustment clauses from this contract text.

For each FX clause found, identify:
- currency_pair: The currency pair (e.g., "USD/BRL", "USD/MXN")
- base_rate: The contractual base/reference exchange rate (numeric)
- threshold_pct: The deviation percentage that triggers an adjustment (numeric, e.g., 3.0 for 3%)
- review_frequency: How often the rate is reviewed ("monthly", "quarterly", "annual")
- adjustment_method: How adjustments are applied ("full_passthrough", "shared", "capped")
- notification_period_days: Required notice period in days before adjustment (integer)
- clause_text: The verbatim text of the clause from the contract
- confidence_score: Your confidence in the extraction accuracy (0.0 to 1.0)

Return a JSON object with a single key "clauses" containing an array of clause objects.
If no FX clauses are found, return {"clauses": []}.

CONTRACT TEXT:
{contract_text}"""


def extract_clauses(contract_text: str, contract_id: int | None = None) -> ExtractionResult:
    """
    Send contract text to Claude API and extract structured FX clause data.

    Returns an ExtractionResult with validated clause schemas.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not configured")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = EXTRACTION_PROMPT.format(contract_text=contract_text)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUSE_EXTRACTION_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

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


def _parse_clauses(raw_text: str) -> list[FXClauseSchema]:
    """Parse and validate clause JSON from Claude's response."""
    # Try to find JSON in the response
    text = raw_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
        else:
            return []

    clause_list = data.get("clauses", []) if isinstance(data, dict) else data

    validated = []
    for item in clause_list:
        try:
            clause = FXClauseSchema(**item)
            validated.append(clause)
        except Exception:
            continue  # Skip malformed clauses

    return validated
