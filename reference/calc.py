"""Deterministic calculator — exact arithmetic for LLM agents.

An LLM predicts digits; this computes them. Safe by construction: parses to an
AST and evaluates only a whitelist of arithmetic nodes/functions — no eval(),
no names, no attribute access, no calls except whitelisted math. Accepts raw
human notation (× ÷ − ^ ! ² ³ and parentheses) so the model can pass the
problem verbatim rather than risk mistranslating it.

Framework-agnostic: import calc(expr) as a tool. Returns (value, error).
"""
from __future__ import annotations

import ast
import math
import operator
import re

_SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUPER_RE = re.compile(r"([0-9)\]])\s*([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")


def _normalize(expr: str) -> str:
    s = _SUPER_RE.sub(lambda m: f"{m.group(1)}**{m.group(2).translate(_SUPER)}", expr.strip())
    s = (s.replace("×", "*").replace("·", "*").replace("∙", "*")
           .replace("÷", "/").replace("^", "**")
           .replace("−", "-").replace("–", "-").replace("—", "-")
           .replace("π", "pi"))
    # Strip only digit-GROUPING commas ("1,000"), not argument separators —
    # min(1,2) / max(3, 10) / gcd(12, 18) must keep theirs.
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
    # Factorial applies to literal integers only (500!) — not (3+2)! or 5!!.
    return re.sub(r"(\d+)\s*!", r"factorial(\1)", s)


_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
           ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_FACT = 10_000
_MAX_RESULT_DIGITS = 100_000


def _factorial(n):
    if n > _MAX_FACT:
        raise ValueError(f"factorial argument too large (max {_MAX_FACT})")
    return math.factorial(n)


_FUNCS = {"sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor,
          "ceil": math.ceil, "log": math.log10, "ln": math.log, "log2": math.log2,
          "sin": math.sin, "cos": math.cos, "tan": math.tan, "factorial": _factorial,
          "exp": math.exp, "gcd": math.gcd, "min": min, "max": max}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_MAX_POW = 1_000_000


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"non-numeric constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        if isinstance(node.op, ast.Pow):
            base, exp = _eval(node.left), _eval(node.right)
            if abs(exp) > _MAX_POW:
                raise ValueError("exponent too large")
            if abs(base) > 1 and abs(exp) * math.log10(abs(base)) > _MAX_RESULT_DIGITS:
                raise ValueError("result too large")
            return operator.pow(base, exp)
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        if node.keywords:
            raise ValueError("keyword args not allowed")
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def calc(expression: str):
    """Evaluate an arithmetic expression exactly. Returns (value, error).
    value is int when whole, else float rounded to 10 dp; error is None on
    success or a short string on failure."""
    if not expression or not str(expression).strip():
        return None, "empty expression"
    try:
        value = _eval(ast.parse(_normalize(str(expression)), mode="eval").body)
    except ZeroDivisionError:
        return None, "division by zero"
    except (ValueError, SyntaxError, TypeError, OverflowError) as e:
        return None, f"{type(e).__name__}: {e}"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return (value if isinstance(value, int) else round(value, 10)), None


if __name__ == "__main__":
    assert calc("17 × 23 − 4³")[0] == 327
    assert calc("6! / (14 + 22) × 3")[0] == 60
    assert calc("840 / 1.4 / 60")[0] == 10
    assert calc("2**10")[0] == 1024
    assert calc("sqrt(2401)")[0] == 49
    assert calc("1,000 + 1")[0] == 1001
    assert calc("__import__('os')")[0] is None      # refuses code
    assert calc("9**9**9")[0] is None                # refuses huge exponent
    assert calc("1/0")[1] == "division by zero"
    print("calc self-check ok")
