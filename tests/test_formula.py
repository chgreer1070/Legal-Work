"""
Unit tests for fx.exposure.formula — validation, Decimal arithmetic,
and the security whitelist.
"""

from decimal import Decimal

import pytest

from fx.exposure.formula import FormulaError, evaluate_formula, validate_formula


VARS = {
    "volume": Decimal("1000000"),
    "base_rate": Decimal("5.00"),
    "current_rate": Decimal("5.30"),
    "rate_delta": Decimal("0.30"),
    "abs_rate_delta": Decimal("0.30"),
    "deviation": Decimal("0.06"),
    "abs_deviation": Decimal("0.06"),
    "threshold": Decimal("0.03"),
}


# ── Arithmetic correctness ───────────────────────────────────────────────────

def test_full_passthrough():
    assert evaluate_formula("volume * abs_deviation", VARS) == Decimal("60000.00")


def test_shared_beyond_corridor():
    result = evaluate_formula("volume * max(0, abs_deviation - 0.03) * 0.5", VARS)
    assert result == Decimal("15000.000")  # (0.06 - 0.03) * 0.5 * 1M


def test_capped_passthrough():
    result = evaluate_formula("volume * min(abs_deviation, 0.10)", VARS)
    assert result == Decimal("60000.00")


def test_cap_binds_when_move_exceeds_it():
    wide = dict(VARS, abs_deviation=Decimal("0.15"))
    result = evaluate_formula("volume * min(abs_deviation, 0.10)", wide)
    assert result == Decimal("100000.0")


def test_corridor_zero_inside_band():
    inside = dict(VARS, abs_deviation=Decimal("0.02"))
    result = evaluate_formula("volume * max(0, abs_deviation - 0.03) * 0.5", inside)
    assert result == Decimal("0.00")


def test_decimal_exactness_no_float_drift():
    # 0.1 + 0.2 style drift must not appear: Decimal arithmetic is exact.
    result = evaluate_formula("volume * (0.1 + 0.2)", {**VARS, "volume": Decimal("100")})
    assert result == Decimal("30.0")


def test_float_variables_are_coerced_via_str():
    # Float inputs keep their printed value, not their binary expansion.
    result = evaluate_formula("volume * abs_deviation", {**VARS, "abs_deviation": 0.06})
    assert result == Decimal("60000.00")


def test_unary_minus_and_signed_deviation():
    result = evaluate_formula("volume * max(0, -deviation)", VARS)
    assert result == Decimal("0")


def test_integer_exponent_allowed():
    assert evaluate_formula("deviation ** 2", VARS) == Decimal("0.0036")


def test_fractional_exponent_rejected():
    with pytest.raises(FormulaError, match="integer"):
        evaluate_formula("volume ** 0.5", VARS)


def test_division_by_zero_rejected():
    with pytest.raises(FormulaError, match="[Dd]ivision"):
        evaluate_formula("volume / (threshold - 0.03)", VARS)


def test_returns_decimal_type():
    assert isinstance(evaluate_formula("volume * abs_deviation", VARS), Decimal)


# ── Security whitelist ───────────────────────────────────────────────────────

@pytest.mark.parametrize("attack", [
    "__import__('os').system('id')",
    "open('/etc/passwd').read()",
    "volume.__class__",
    "[x for x in range(10)]",
    "exec('import os')",
    "volume if True else 0",
    "unknown_variable * 2",
    "volume; volume",
    "lambda: 1",
])
def test_malicious_expressions_rejected(attack):
    with pytest.raises(FormulaError):
        validate_formula(attack)


def test_keyword_arguments_rejected():
    with pytest.raises(FormulaError):
        validate_formula("max(volume, default=0)")


def test_overlong_expression_rejected():
    with pytest.raises(FormulaError, match="exceeds"):
        validate_formula("volume + " * 200 + "volume")


def test_empty_expression_rejected():
    with pytest.raises(FormulaError, match="[Ee]mpty"):
        validate_formula("   ")


def test_pow_bounds_enforced():
    with pytest.raises(FormulaError, match="range"):
        evaluate_formula("(volume * 10) ** 2", VARS)  # base 1e7 exceeds the 1e6 limit
