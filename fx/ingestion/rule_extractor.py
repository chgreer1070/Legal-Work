"""
Deterministic rule-based FX clause extractor.

Fallback for when the Claude API is unavailable: parses FX adjustment
clauses from contract text with regex and phrase patterns, including
deriving the adjustment formula from sharing/cap/corridor language.
Deliberately conservative — a clause is only produced when both a base
rate and a threshold are found near a currency pair, and confidence is
capped well below what the LLM extractor reports.
"""

import logging
import re

from fx.ingestion.schema import FXClauseSchema

logger = logging.getLogger(__name__)

MAX_CLAUSE_TEXT = 1000
MAX_CONFIDENCE = 0.7

_PAIR_RE = re.compile(r"\b([A-Z]{3})\s*/\s*([A-Z]{3})\b")

# Word-number map for spelled-out values ("three percent", "thirty days")
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "fifteen": 15, "twenty": 20, "thirty": 30, "forty-five": 45,
    "forty five": 45, "sixty": 60, "ninety": 90,
}

_BASE_RATE_PATTERNS = [
    # "base reference rate of USD/BRL = 4.7500", "base rate of 5.0500"
    re.compile(
        r"(?:base|reference|contractual)[\w\s]*?rate\s+of\s+"
        r"(?:[A-Z]{3}\s*/\s*[A-Z]{3}\s*=?\s*)?(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    ),
    # "USD/BRL at 4.7500", "USD/BRL = 4.7500"
    re.compile(r"[A-Z]{3}\s*/\s*[A-Z]{3}\s*(?:=|at)\s*(\d+(?:\.\d+)?)"),
]

# "(3%)", "(3.5 %)" — parenthetical numerals accompanying spelled-out values
_PAREN_PCT_RE = re.compile(r"\((\d+(?:\.\d+)?)\s*%\)")

_THRESHOLD_RE = re.compile(
    r"(?:more\s+than|exceed(?:s|ing)?|greater\s+than|beyond|in\s+excess\s+of|by\s+at\s+least)"
    r"[\s\w\-]*?\(?(\d+(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE,
)

_THRESHOLD_WORD_RE = re.compile(
    r"(?:more\s+than|exceed(?:s|ing)?|greater\s+than|beyond|in\s+excess\s+of)\s+"
    r"([a-z][a-z\- ]*?)\s+percent",
    re.IGNORECASE,
)

_FREQUENCY_RE = re.compile(r"\b(monthly|quarterly|annual(?:ly)?|yearly)\b", re.IGNORECASE)

_NOTICE_PATTERNS = [
    re.compile(r"\((\d+)\)\s*(?:calendar\s+|business\s+)?days", re.IGNORECASE),
    re.compile(
        r"(\d+)\s*(?:calendar\s+|business\s+)?days[’']?\s*(?:prior\s+)?(?:written\s+)?notice",
        re.IGNORECASE,
    ),
    re.compile(r"notice\s+period\s+of\s+(\d+)\s+days", re.IGNORECASE),
]

_SHARE_EQUAL_RE = re.compile(
    r"(?:shared?|borne|split)\s+equally|50\s*/\s*50|fifty[- ]fifty", re.IGNORECASE
)
_SHARE_PCT_RE = re.compile(
    r"(?:bear|absorb|share\s+of)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)", re.IGNORECASE
)

_CAP_RE = re.compile(
    r"(?:capped\s+at|cap\s+of|not\s+(?:to\s+)?exceed(?:ing)?|up\s+to\s+a\s+maximum\s+of|"
    r"maximum\s+of)[\s\w\-]*?\(?(\d+(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE,
)

_CORRIDOR_RE = re.compile(
    r"(?:beyond|in\s+excess\s+of|exceeding|above)\s+the\s+[\w\s\-]*?"
    r"(?:corridor|threshold|band|level|percentage)|movement\s+beyond",
    re.IGNORECASE,
)


def extract_clauses_rule_based(contract_text: str) -> list[FXClauseSchema]:
    """Parse FX clauses from contract text without an LLM."""
    clauses = []
    seen = set()
    for block in _clause_blocks(contract_text):
        for pair in _pairs_in(block):
            clause = _parse_block(block, pair)
            if clause is None:
                continue
            key = (clause.currency_pair, clause.base_rate, clause.threshold_pct)
            if key in seen:
                continue
            seen.add(key)
            clauses.append(clause)
    return clauses


# PDF text extraction rarely preserves blank lines, so blocks split on
# numbered subsections ("8.1 ", "12.3 ") and ARTICLE/Section headings too.
_BLOCK_SPLIT_RE = re.compile(
    r"\n\s*\n"
    r"|\n(?=\d+\.\d+\s)"
    r"|\n(?=(?:ARTICLE|Article|SECTION|Section)\s+\d)"
)


def _clause_blocks(text: str) -> list[str]:
    """Split text into candidate clause blocks (sections mentioning a pair)."""
    paragraphs = _BLOCK_SPLIT_RE.split(text)
    blocks = []
    for i, para in enumerate(paragraphs):
        if not _PAIR_RE.search(para):
            continue
        block = para.strip()
        # Short section headers often separate the pair from its terms —
        # pull in the following paragraph for context.
        if len(block) < 200 and i + 1 < len(paragraphs):
            block = block + "\n" + paragraphs[i + 1].strip()
        blocks.append(block)
    return blocks


def _pairs_in(block: str) -> list[str]:
    pairs = []
    for m in _PAIR_RE.finditer(block):
        pair = f"{m.group(1)}/{m.group(2)}"
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def _parse_block(block: str, pair: str) -> FXClauseSchema | None:
    base_rate = _find_base_rate(block, pair)
    threshold = _find_threshold(block)
    if base_rate is None or threshold is None:
        logger.debug(
            "Rule extractor skipping %s block (base_rate=%s, threshold=%s)",
            pair, base_rate, threshold,
        )
        return None

    frequency = _find_frequency(block)
    notice_days = _find_notice_days(block)
    share = _find_share(block)
    cap = _find_cap(block)
    corridor = bool(_CORRIDOR_RE.search(block))

    expression, formula_type, description = _build_formula(threshold, share, cap, corridor)
    adjustment_method = "shared" if share else ("capped" if cap else "full_passthrough")

    confidence = 0.4
    if frequency:
        confidence += 0.1
    if notice_days:
        confidence += 0.1
    if share or cap or corridor:
        confidence += 0.1
    confidence = min(confidence, MAX_CONFIDENCE)

    return FXClauseSchema(
        currency_pair=pair,
        base_rate=base_rate,
        threshold_pct=threshold,
        review_frequency=frequency or "monthly",
        adjustment_method=adjustment_method,
        notification_period_days=notice_days or 30,
        clause_text=block[:MAX_CLAUSE_TEXT],
        formula_type=formula_type,
        formula_expression=expression,
        formula_description=description,
        confidence_score=confidence,
    )


def _find_base_rate(block: str, pair: str) -> float | None:
    a, b = pair.split("/")
    pair_pattern = rf"{a}\s*/\s*{b}"
    # Pair-anchored matches first, so a block mentioning several pairs
    # never borrows another pair's rate.
    anchored = [
        re.compile(
            rf"(?:base|reference|contractual)[\w\s]*?rate\s+of\s+{pair_pattern}\s*=?\s*(\d+(?:\.\d+)?)",
            re.IGNORECASE,
        ),
        re.compile(rf"{pair_pattern}\s*(?:=|at)\s*(\d+(?:\.\d+)?)"),
    ]
    for pattern in anchored:
        m = pattern.search(block)
        if m:
            value = float(m.group(1))
            if value > 0:
                return value
    # Generic patterns are safe only when this pair is alone in the block
    if len(_pairs_in(block)) == 1:
        for pattern in _BASE_RATE_PATTERNS:
            m = pattern.search(block)
            if m:
                value = float(m.group(1))
                if value > 0:
                    return value
    return None


def _find_threshold(block: str) -> float | None:
    m = _THRESHOLD_RE.search(block)
    if m:
        return float(m.group(1))
    m = _THRESHOLD_WORD_RE.search(block)
    if m:
        word = m.group(1).strip().lower()
        if word in _WORD_NUMBERS:
            return float(_WORD_NUMBERS[word])
    # Last resort: a lone parenthetical percentage next to deviation language
    if re.search(r"deviat|fluctuat|move|chang", block, re.IGNORECASE):
        m = _PAREN_PCT_RE.search(block)
        if m:
            return float(m.group(1))
    return None


def _find_frequency(block: str) -> str | None:
    m = _FREQUENCY_RE.search(block)
    if not m:
        return None
    word = m.group(1).lower()
    if word in ("annually", "yearly"):
        return "annual"
    return word


def _find_notice_days(block: str) -> int | None:
    for pattern in _NOTICE_PATTERNS:
        m = pattern.search(block)
        if m:
            days = int(m.group(1))
            if 0 < days <= 365:
                return days
    return None


def _find_share(block: str) -> float | None:
    if _SHARE_EQUAL_RE.search(block):
        return 0.5
    m = _SHARE_PCT_RE.search(block)
    if m:
        pct = float(m.group(1))
        if 0 < pct < 100:
            return pct / 100.0
    return None


def _find_cap(block: str) -> float | None:
    m = _CAP_RE.search(block)
    if m:
        pct = float(m.group(1))
        if 0 < pct <= 100:
            return pct / 100.0
    return None


def _fmt(value: float) -> str:
    """Format a fraction as a compact literal (0.03, 0.5, 0.125)."""
    return format(value, ".4f").rstrip("0").rstrip(".")


def _build_formula(threshold_pct: float, share, cap, corridor: bool):
    """Assemble the adjustment formula from parsed clause semantics."""
    parts = []
    if corridor:
        inner = f"max(0, abs_deviation - {_fmt(threshold_pct / 100.0)})"
        parts.append(f"the movement beyond the {_fmt(threshold_pct)}% corridor")
    else:
        inner = "abs_deviation"
        parts.append("the full rate movement")

    if share is not None:
        inner = f"{inner} * {_fmt(share)}"
        parts.append(f"shared at {_fmt(share * 100)}%")

    if cap is not None:
        expression = f"volume * min({inner}, {_fmt(cap)})"
        parts.append(f"capped at {_fmt(cap * 100)}%")
    else:
        expression = f"volume * {inner}"

    if share is not None:
        formula_type = "shared"
    elif cap is not None:
        formula_type = "capped"
    elif corridor:
        formula_type = "corridor"
    else:
        formula_type = "full_passthrough"

    description = "Volume times " + ", ".join(parts) + " (rule-based extraction)."
    return expression, formula_type, description
