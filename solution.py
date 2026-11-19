"""Add a calculated ("virtual") column to a pandas DataFrame."""

import ast
import logging
import operator
import re

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype

logger = logging.getLogger(__name__)

# A column label has only letters and underscores, e.g. "unit_price".
LABEL_PATTERN = re.compile(r"[A-Za-z_]+")

# A role has only labels, the + - * operators, parentheses and whitespace.
# Digits are not allowed, so every name in a role is a valid label too.
ROLE_PATTERN = re.compile(r"[A-Za-z_+\-*()\s]+")

OPERATIONS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
}


class InvalidInputError(ValueError):
    """The role or the new column label cannot be used."""


def add_virtual_column(df: pd.DataFrame, role: str, new_column: str) -> pd.DataFrame:
    """Return a copy of ``df`` with a new column calculated from ``role``.

    ``role`` combines column labels with ``+``, ``-`` and ``*``, for example
    ``"quantity * unit_price - discount"``. The usual precedence applies
    (``*`` before ``+`` and ``-``) and parentheses can group terms.

    Returns an empty DataFrame when ``new_column`` is not a valid label, or when
    ``role`` uses anything other than numeric columns of ``df`` and these
    operators. ``df`` itself is never changed.
    """
    try:
        _check_label(new_column)
        values = _evaluate_role(df, role)
    except InvalidInputError as error:
        logger.warning("Cannot add virtual column %r: %s", new_column, error)
        return pd.DataFrame([])

    result = df.copy()
    result[new_column] = values
    return result


def _check_label(label: str) -> None:
    if not LABEL_PATTERN.fullmatch(label):
        raise InvalidInputError(f"{label!r} must contain only letters and underscores")


def _evaluate_role(df: pd.DataFrame, role: str) -> pd.Series:
    if not ROLE_PATTERN.fullmatch(role):
        raise InvalidInputError(f"role {role!r} contains unsupported characters")
    try:
        # Python's own parser checks the syntax and applies operator precedence.
        expression = ast.parse(role.strip(), mode="eval").body
    except SyntaxError as error:
        raise InvalidInputError(f"role {role!r} is not a valid expression") from error
    return _evaluate_node(df, expression)


def _evaluate_node(df: pd.DataFrame, node: ast.expr) -> pd.Series:
    """Evaluate one part of the parsed role: a column label or an operation."""
    if isinstance(node, ast.Name):
        return _numeric_column(df, node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
        operation = OPERATIONS[type(node.op)]
        return operation(_evaluate_node(df, node.left), _evaluate_node(df, node.right))
    raise InvalidInputError(f"{ast.unparse(node)!r} is not a column or + - * operation")


def _numeric_column(df: pd.DataFrame, label: str) -> pd.Series:
    if list(df.columns).count(label) != 1:
        raise InvalidInputError(f"there is no single column named {label!r}")
    column = df[label]
    if is_bool_dtype(column) or not is_numeric_dtype(column):
        raise InvalidInputError(f"column {label!r} is not numeric")
    return column
