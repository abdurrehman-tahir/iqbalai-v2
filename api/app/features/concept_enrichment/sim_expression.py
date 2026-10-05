"""Safe arithmetic for mini-sim specs — T-190/T-191.

The LLM writes the sim output as an expression string. It is NEVER executed:
this tiny recursive-descent parser accepts only numbers, declared variable
names, ``+ - * / ^``, parentheses and unary minus. The frontend ports the same
grammar (``mini-sim-expression.ts``); both must stay in lockstep.

Grammar:
    expr   := term (('+' | '-') term)*
    term   := factor (('*' | '/') factor)*
    factor := unary ('^' factor)?          # right-associative power
    unary  := '-' unary | atom
    atom   := NUMBER | NAME | '(' expr ')'
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([a-z][a-z0-9_]*)|(\S))")
MAX_TOKENS = 64


class ExpressionError(ValueError):
    """The expression is not in the safe grammar or references unknown names."""


def _tokenize(source: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    text = source.strip()
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None:
            raise ExpressionError("unexpected character")
        number, name, symbol = match.groups()
        token = number or name or symbol
        if symbol is not None and symbol not in "+-*/^()":
            raise ExpressionError(f"unsupported symbol {symbol!r}")
        tokens.append(token)
        pos = match.end()
        if len(tokens) > MAX_TOKENS:
            raise ExpressionError("expression too long")
    if not tokens:
        raise ExpressionError("empty expression")
    return tokens


class _Parser:
    def __init__(self, tokens: list[str], values: Mapping[str, float]) -> None:
        self._tokens = tokens
        self._values = values
        self._i = 0

    def _peek(self) -> str | None:
        return self._tokens[self._i] if self._i < len(self._tokens) else None

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise ExpressionError("unexpected end of expression")
        self._i += 1
        return token

    def parse(self) -> float:
        value = self._expr()
        if self._peek() is not None:
            raise ExpressionError("trailing tokens")
        return value

    def _expr(self) -> float:
        value = self._term()
        while self._peek() in ("+", "-"):
            op = self._take()
            rhs = self._term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _term(self) -> float:
        value = self._factor()
        while self._peek() in ("*", "/"):
            op = self._take()
            rhs = self._factor()
            if op == "*":
                value *= rhs
            else:
                if rhs == 0:
                    raise ZeroDivisionError("division by zero")
                value /= rhs
        return value

    def _factor(self) -> float:
        base = self._unary()
        if self._peek() == "^":
            self._take()
            exponent = self._factor()
            if base < 0 and not float(exponent).is_integer():
                raise ExpressionError("complex result")
            return float(math.pow(base, exponent))
        return base

    def _unary(self) -> float:
        if self._peek() == "-":
            self._take()
            return -self._unary()
        return self._atom()

    def _atom(self) -> float:
        token = self._take()
        if token == "(":
            value = self._expr()
            if self._take() != ")":
                raise ExpressionError("missing ')'")
            return value
        if token[0].isdigit():
            return float(token)
        if token[0].isalpha():
            if token not in self._values:
                raise ExpressionError(f"unknown variable {token!r}")
            return float(self._values[token])
        raise ExpressionError(f"unexpected token {token!r}")


def evaluate(expression: str, values: Mapping[str, float]) -> float | None:
    """Evaluate safely; ``None`` for a mathematically undefined point (÷0, inf, nan).

    Raises :class:`ExpressionError` when the expression itself is invalid.
    """
    try:
        result = _Parser(_tokenize(expression), values).parse()
    except (ZeroDivisionError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def validate(expression: str, variable_keys: set[str], defaults: Mapping[str, float]) -> bool:
    """True when the expression parses, uses only declared variables and is
    finite at the default slider values (so the sim renders a number on open)."""
    try:
        return evaluate(expression, {k: defaults[k] for k in variable_keys}) is not None
    except (ExpressionError, KeyError):
        return False
