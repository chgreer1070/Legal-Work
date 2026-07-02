"""
Safe evaluation of contract-derived FX adjustment formulas.

Formulas are arithmetic expressions extracted from contract language
(e.g. "volume * max(0, abs_deviation - 0.03) * 0.5" for a 50/50 sharing
arrangement beyond a 3% corridor). They are validated against a strict
AST whitelist before storage and evaluated without eval().
"""

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow

MAX_EXPRESSION_LENGTH = 500

_POW_BASE_LIMIT = Decimal("1e6")
_POW_EXP_LIMIT = Decimal("100")

ALLOWED_FUNCTIONS = {"min": min, "max": max, "abs": abs}

ALLOWED_VARIABLES = frozenset({
    "volume",          # total USD transaction volume for the period
    "base_rate",       # contractual base/reference rate
    "current_rate",    # current market rate
    "rate_delta",      # current_rate - base_rate (signed)
    "abs_rate_delta",  # |current_rate - base_rate|
    "deviation",       # (current_rate - base_rate) / base_rate (signed fraction)
    "abs_deviation",   # |deviation|
    "threshold",       # clause threshold_pct as a fraction (3.0% -> 0.03)
})

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.USub, ast.UAdd)


class FormulaError(ValueError):
    """Raised when a formula fails validation or evaluation."""


def _validate_node(node: ast.AST) -> None:
    if isinstance(node, ast.Expression):
        _validate_node(node.body)
    elif isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise FormulaError(f"Operator not allowed: {type(node.op).__name__}")
        _validate_node(node.left)
        _validate_node(node.right)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise FormulaError(f"Operator not allowed: {type(node.op).__name__}")
        _validate_node(node.operand)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise FormulaError("Only min(), max(), and abs() calls are allowed")
        if node.keywords:
            raise FormulaError("Keyword arguments are not allowed")
        for arg in node.args:
            _validate_node(arg)
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise FormulaError(f"Constant not allowed: {node.value!r}")
    elif isinstance(node, ast.Name):
        if node.id not in ALLOWED_VARIABLES:
            raise FormulaError(f"Unknown variable: {node.id}")
    else:
        raise FormulaError(f"Syntax not allowed: {type(node).__name__}")


def validate_formula(expression: str) -> None:
    """Validate a formula expression. Raises FormulaError if invalid."""
    if not expression or not expression.strip():
        raise FormulaError("Empty expression")
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise FormulaError(f"Expression exceeds {MAX_EXPRESSION_LENGTH} characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Invalid syntax: {e}") from e
    _validate_node(tree)


def _to_decimal(value) -> Decimal:
    """Coerce a numeric input to Decimal without float representation drift."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise FormulaError(f"Non-numeric value: {value!r}") from e


def _eval_node(node: ast.AST, variables: dict) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise FormulaError("Division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(left) > _POW_BASE_LIMIT or abs(right) > _POW_EXP_LIMIT:
                raise FormulaError("Exponentiation operands out of range")
            if right != right.to_integral_value():
                raise FormulaError("Exponent must be an integer")
            try:
                return left ** int(right)
            except (InvalidOperation, Overflow, DivisionByZero) as e:
                raise FormulaError(f"Exponentiation failed: {e}") from e
        raise FormulaError(f"Operator not allowed: {type(node.op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        return -operand if isinstance(node.op, ast.USub) else +operand
    if isinstance(node, ast.Call):
        func = ALLOWED_FUNCTIONS[node.func.id]
        args = [_eval_node(arg, variables) for arg in node.args]
        return func(*args)
    if isinstance(node, ast.Constant):
        return _to_decimal(node.value)
    if isinstance(node, ast.Name):
        return _to_decimal(variables[node.id])
    raise FormulaError(f"Syntax not allowed: {type(node).__name__}")


def evaluate_formula(expression: str, variables: dict) -> Decimal:
    """
    Validate and evaluate a formula against the supplied variables.

    All arithmetic is done in Decimal so monetary results carry no binary
    floating-point drift; float inputs are converted via str() to preserve
    their printed value. Returns the computed value as a Decimal. Raises
    FormulaError on any validation or evaluation failure (bad syntax,
    unknown variable, division by zero, non-integer exponent).
    """
    validate_formula(expression)
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree, variables)
