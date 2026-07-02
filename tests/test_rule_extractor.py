"""
Unit tests for fx.ingestion.rule_extractor — the deterministic fallback
used when the Claude API is unavailable.
"""

from decimal import Decimal

from fx.exposure.formula import evaluate_formula, validate_formula
from fx.ingestion.rule_extractor import extract_clauses_rule_based


CORRIDOR_SHARED = """8.1 Brazilian Operations. All pricing is denominated in USD against a base
reference rate of USD/BRL = 4.7500. Should the prevailing market rate deviate
from the base rate by more than three percent (3%) measured quarterly, the
parties shall share equally (50/50) the incremental cost impact of the
movement beyond the three percent (3%) corridor. Any adjustment requires
thirty (30) days' written notice."""

CAPPED = """8.2 Mexican Operations. Pricing references a base rate of USD/MXN = 16.5000.
If the market rate deviates by more than five percent (5%), the full movement
shall be passed through to the Customer, capped at ten percent (10%), reviewed
monthly with fifteen (15) days' notice."""

FULL_PASSTHROUGH = """In the event that the prevailing market exchange rate for USD/BRL deviates
from the base rate of 5.0500 by more than three percent (3%), either party
may request a price adjustment on a monthly basis."""


def _single(text):
    clauses = extract_clauses_rule_based(text)
    assert len(clauses) == 1, f"expected 1 clause, got {len(clauses)}"
    return clauses[0]


def test_corridor_shared_clause():
    c = _single(CORRIDOR_SHARED)
    assert c.currency_pair == "USD/BRL"
    assert c.base_rate == 4.75
    assert c.threshold_pct == 3.0
    assert c.review_frequency == "quarterly"
    assert c.notification_period_days == 30
    assert c.adjustment_method == "shared"
    assert c.formula_type == "shared"
    assert c.formula_expression == "volume * max(0, abs_deviation - 0.03) * 0.5"


def test_capped_clause():
    c = _single(CAPPED)
    assert c.currency_pair == "USD/MXN"
    assert c.base_rate == 16.5
    assert c.threshold_pct == 5.0
    assert c.review_frequency == "monthly"
    assert c.notification_period_days == 15
    assert c.formula_type == "capped"
    assert c.formula_expression == "volume * min(abs_deviation, 0.1)"


def test_full_passthrough_clause():
    c = _single(FULL_PASSTHROUGH)
    assert c.currency_pair == "USD/BRL"
    assert c.base_rate == 5.05
    assert c.threshold_pct == 3.0
    assert c.formula_type == "full_passthrough"
    assert c.formula_expression == "volume * abs_deviation"


def test_multi_clause_document_extracts_all():
    text = "\n\n".join([CORRIDOR_SHARED, CAPPED, FULL_PASSTHROUGH])
    clauses = extract_clauses_rule_based(text)
    assert len(clauses) == 3
    pairs = sorted((c.currency_pair, c.base_rate) for c in clauses)
    assert pairs == [("USD/BRL", 4.75), ("USD/BRL", 5.05), ("USD/MXN", 16.5)]


def test_all_produced_formulas_validate_and_price_correctly():
    # Golden check: at a 6% adverse move on $1,000,000 the three formula
    # shapes produce hand-computed amounts.
    text = "\n\n".join([CORRIDOR_SHARED, CAPPED, FULL_PASSTHROUGH])
    expected = {
        ("USD/BRL", 4.75): Decimal("15000"),   # (6% - 3%) * 0.5 * 1M
        ("USD/MXN", 16.5): Decimal("60000"),   # min(6%, 10%) * 1M
        ("USD/BRL", 5.05): Decimal("60000"),   # 6% * 1M
    }
    variables = {
        "volume": Decimal("1000000"),
        "base_rate": Decimal("5"),
        "current_rate": Decimal("5.3"),
        "rate_delta": Decimal("0.3"),
        "abs_rate_delta": Decimal("0.3"),
        "deviation": Decimal("0.06"),
        "abs_deviation": Decimal("0.06"),
        "threshold": Decimal("0.03"),
    }
    for c in extract_clauses_rule_based(text):
        validate_formula(c.formula_expression)
        value = evaluate_formula(c.formula_expression, variables)
        assert value == expected[(c.currency_pair, c.base_rate)]


def test_pair_without_rate_or_threshold_is_skipped():
    assert extract_clauses_rule_based("Payments settle in USD/BRL each month.") == []


def test_no_pairs_yields_nothing():
    assert extract_clauses_rule_based("This agreement has no currency terms.") == []


def test_confidence_capped_below_llm_levels():
    for c in extract_clauses_rule_based("\n\n".join([CORRIDOR_SHARED, CAPPED])):
        assert c.confidence_score <= 0.7


def test_duplicate_clause_text_deduped():
    clauses = extract_clauses_rule_based(CORRIDOR_SHARED + "\n\n" + CORRIDOR_SHARED)
    assert len(clauses) == 1


def test_pdf_style_text_without_blank_lines():
    # pypdf output loses paragraph breaks: sections separate only on
    # numbered headings. Each clause must keep its own pair's terms —
    # regression for cross-contamination where USD/MXN borrowed the
    # USD/BRL base rate from the same undivided block.
    pdf_text = (
        "ARTICLE 8 — CURRENCY ADJUSTMENT\n"
        "8.1 Brazilian Operations. All pricing is denominated in USD against a base\n"
        "reference rate of USD/BRL = 4.7500. Should the prevailing market rate deviate\n"
        "from the base rate by more than three percent (3%) measured quarterly, the\n"
        "parties shall share equally (50/50) the incremental cost impact of the\n"
        "movement beyond the three percent (3%) corridor. Any adjustment requires\n"
        "thirty (30) days' written notice.\n"
        "8.2 Mexican Operations. Pricing references a base rate of USD/MXN = 16.5000.\n"
        "If the market rate deviates by more than five percent (5%), the full movement\n"
        "shall be passed through to the Customer, capped at ten percent (10%), reviewed\n"
        "monthly with fifteen (15) days' notice.\n"
        "ARTICLE 9 — TERM. This Agreement remains in force for thirty-six (36) months."
    )
    clauses = extract_clauses_rule_based(pdf_text)
    by_pair = {c.currency_pair: c for c in clauses}
    assert set(by_pair) == {"USD/BRL", "USD/MXN"}

    brl = by_pair["USD/BRL"]
    assert brl.base_rate == 4.75
    assert brl.threshold_pct == 3.0
    assert brl.review_frequency == "quarterly"
    assert brl.formula_expression == "volume * max(0, abs_deviation - 0.03) * 0.5"

    mxn = by_pair["USD/MXN"]
    assert mxn.base_rate == 16.5
    assert mxn.threshold_pct == 5.0
    assert mxn.review_frequency == "monthly"
    assert mxn.formula_expression == "volume * min(abs_deviation, 0.1)"
