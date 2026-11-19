"""Tests for add_virtual_column, in addition to the provided test_virtual_column.py."""

import pandas as pd
import pytest

from solution import add_virtual_column


@pytest.fixture
def numbers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "a": [1, 2],
            "b": [3, 4],
            "c": [5, 6],
            "name": ["first", "second"],
            "flag": [True, False],
        }
    )


def test_example_from_task():
    fruit_sales = pd.DataFrame(
        {"name": ["banana", "apple"], "quantity": [10, 3], "price": [10, 1]}
    )
    result = add_virtual_column(fruit_sales, "quantity * price", "total")
    expected = fruit_sales.assign(total=[100, 3])
    pd.testing.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("a + b * c", [16, 26]),
        ("a * b - c", [-2, 2]),
        ("a - b - c", [-7, -8]),
        ("(a + b) * c", [20, 36]),
        ("a*b+c", [8, 14]),
        ("a + a", [2, 4]),
    ],
)
def test_calculates_with_usual_operator_precedence(numbers, role, expected):
    result = add_virtual_column(numbers, role, "result")
    assert result["result"].tolist() == expected


def test_works_with_floats_and_keeps_missing_values_missing():
    df = pd.DataFrame({"price": [1.5, None], "quantity": [2, 3]})
    result = add_virtual_column(df, "price * quantity", "total")
    assert result["total"].iloc[0] == 3.0
    assert pd.isna(result["total"].iloc[1])


def test_does_not_change_input(numbers):
    original = numbers.copy()
    add_virtual_column(numbers, "a + b", "total")
    pd.testing.assert_frame_equal(numbers, original)


def test_keeps_index_and_adds_column_at_the_end():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]}, index=["x", "y"])
    result = add_virtual_column(df, "a + b", "total")
    assert result.index.tolist() == ["x", "y"]
    assert result.columns.tolist() == ["a", "b", "total"]


def test_replaces_existing_column_with_the_same_name(numbers):
    result = add_virtual_column(numbers, "a + b", "c")
    assert result["c"].tolist() == [4, 6]
    assert result.columns.tolist() == numbers.columns.tolist()


@pytest.mark.parametrize(
    "new_column",
    ["", "label3", "new column", "new-column", " total", "total\n", "żółw"],
)
def test_returns_empty_dataframe_for_invalid_new_column(numbers, new_column):
    assert add_virtual_column(numbers, "a + b", new_column).empty


@pytest.mark.parametrize(
    "role",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="only spaces"),
        pytest.param("a / b", id="division"),
        pytest.param("a ** b", id="power"),
        pytest.param("a + 2", id="number"),
        pytest.param("a +", id="missing operand"),
        pytest.param("a b", id="missing operator"),
        pytest.param("-a", id="unary minus"),
        pytest.param("(a + b", id="unclosed parenthesis"),
        pytest.param("sum(a)", id="function call"),
        pytest.param("a.real", id="attribute"),
        pytest.param("a and b", id="keyword operator"),
        pytest.param("True + a", id="python constant"),
        pytest.param("a + missing", id="unknown column"),
        pytest.param("a + name", id="text column"),
        pytest.param("a + flag", id="boolean column"),
    ],
)
def test_returns_empty_dataframe_for_invalid_role(numbers, role):
    assert add_virtual_column(numbers, role, "result").empty


def test_returns_empty_dataframe_when_label_names_two_columns():
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    assert add_virtual_column(df, "a + a", "total").empty


def test_ignores_invalid_labels_of_columns_not_used_in_role():
    df = pd.DataFrame({"Order ID": ["SO-1"], "a": [1], "b": [2]})
    result = add_virtual_column(df, "a + b", "total")
    assert result["total"].tolist() == [3]
