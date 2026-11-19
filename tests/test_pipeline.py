"""Tests for the cleaning steps and the whole pipeline."""

from pathlib import Path

import pandas as pd
import pytest

import pipeline

# A small export with one example of every problem found in sales.csv.
DIRTY_SALES_CSV = """\
Order ID,Region,Product,Quantity ,Unit Price,Discount,Order Date
SO-1,North,Mouse,2,10.00,,2026-01-01
SO-2, north ,Mouse,1 000,"10,00",5.00,2026-01-02
Order ID,Region,Product,Quantity ,Unit Price,Discount,Order Date
SO-3,SOUTH,Mouse,-1,,,2026-01-03
SO-3,SOUTH,Mouse,-1,,,2026-01-03
SO-3,South,Keyboard,1,50.00,,2026-01-03
TOTAL,,,1003,,5.00,
"""


def text_frame(**columns: list[str]) -> pd.DataFrame:
    """Build a DataFrame of text values, like read_sales returns."""
    return pd.DataFrame(columns, dtype=str)


@pytest.fixture
def dirty_sales_file(tmp_path: Path) -> Path:
    path = tmp_path / "sales.csv"
    path.write_text(DIRTY_SALES_CSV)
    return path


# --- Single cleaning steps ----------------------------------------------------


def test_rename_columns_strips_spaces_and_uses_snake_case():
    raw = text_frame(**{"Order ID": ["SO-1"], "Quantity ": ["1"], "Unit Price": ["2"]})
    assert pipeline.rename_columns(raw).columns.tolist() == [
        "order_id",
        "quantity",
        "unit_price",
    ]


def test_drop_repeated_headers_and_total_row():
    sales = text_frame(order_id=["SO-1", "Order ID", "SO-2", "TOTAL"])
    sales = pipeline.drop_total_row(pipeline.drop_repeated_headers(sales))
    assert sales["order_id"].tolist() == ["SO-1", "SO-2"]


def test_normalize_regions():
    sales = text_frame(region=["North", " South", "west  ", "EAST", "central"])
    assert pipeline.normalize_regions(sales)["region"].tolist() == [
        "North",
        "South",
        "West",
        "East",
        "Central",
    ]


def test_parse_quantities_reads_thousands_separator_and_removes_minus_sign():
    sales = text_frame(quantity=["12", "1 762", "-2"])
    assert pipeline.parse_quantities(sales)["quantity"].tolist() == [12, 1762, 2]


def test_parse_unit_prices_reads_decimal_comma_and_empty_price():
    sales = text_frame(unit_price=["39.90", "39,90", ""])
    unit_price = pipeline.parse_unit_prices(sales)["unit_price"]
    assert unit_price.iloc[:2].tolist() == [39.9, 39.9]
    assert pd.isna(unit_price.iloc[2])


def test_fill_missing_unit_prices_uses_price_of_same_product():
    sales = pd.DataFrame(
        {"product": ["Mouse", "Mouse", "Desk lamp"], "unit_price": [None, 29.5, 39.9]}
    )
    filled = pipeline.fill_missing_unit_prices(sales)
    assert filled["unit_price"].tolist() == [29.5, 29.5, 39.9]


def test_fill_missing_unit_prices_stops_when_product_has_two_prices():
    sales = pd.DataFrame(
        {"product": ["Mouse", "Mouse", "Mouse"], "unit_price": [None, 29.5, 30.0]}
    )
    with pytest.raises(ValueError, match="several unit prices"):
        pipeline.fill_missing_unit_prices(sales)


def test_parse_discounts_treats_empty_discount_as_zero():
    sales = text_frame(discount=["", "12.60"])
    assert pipeline.parse_discounts(sales)["discount"].tolist() == [0.0, 12.6]


def test_parse_order_dates_rejects_unknown_format():
    sales = text_frame(order_date=["2026-01-02", "02/01/2026"])
    with pytest.raises(ValueError, match="02/01/2026"):
        pipeline.parse_order_dates(sales)


def test_drop_duplicate_lines_keeps_other_lines_of_the_same_order():
    sales = pd.DataFrame(
        {"order_id": ["SO-1", "SO-1", "SO-1"], "product": ["Mouse", "Mouse", "Pen"]}
    )
    assert pipeline.drop_duplicate_lines(sales)["product"].tolist() == ["Mouse", "Pen"]


def test_check_no_missing_values_stops_on_missing_value():
    sales = pd.DataFrame({"quantity": [1, None]})
    with pytest.raises(ValueError, match="Missing values"):
        pipeline.check_no_missing_values(sales)


# --- Quality flags ------------------------------------------------------------


def test_modified_z_scores_follow_nist_formula():
    # median = 3, MAD = 1, so the score is 0.6745 * (value - 3)
    scores = pipeline.modified_z_scores(pd.Series([1, 2, 3, 4, 100]))
    assert scores.tolist() == pytest.approx([-1.349, -0.6745, 0.0, 0.6745, 65.4265])


def test_flag_suspicious_quantities_only_marks_lines_and_keeps_them():
    quantities = [*range(1, 41), 1762]
    sales = pd.DataFrame(
        {"order_id": [f"SO-{n}" for n in range(41)], "quantity": quantities}
    )
    flagged = pipeline.flag_suspicious_quantities(sales)

    assert flagged.loc[flagged["suspicious_quantity"], "quantity"].tolist() == [1762]
    assert flagged["quantity"].tolist() == quantities


def test_flag_suspicious_quantities_on_real_file():
    sales = pipeline.clean_sales(pipeline.read_sales(pipeline.INPUT_PATH))
    flagged = pipeline.flag_suspicious_quantities(sales)
    suspicious = flagged.loc[flagged["suspicious_quantity"], "order_id"]
    assert suspicious.tolist() == ["SO-10251", "SO-10734", "SO-11088", "SO-11312"]


# --- Calculation --------------------------------------------------------------


def test_add_revenue_is_quantity_times_unit_price_minus_discount():
    sales = pd.DataFrame({"quantity": [32, 2], "unit_price": [249.0, 119.0]})
    sales["discount"] = [398.40, 0.0]
    revenue = pipeline.add_revenue(sales)["revenue"]
    assert revenue.tolist() == pytest.approx([7569.60, 238.0])


# --- Whole pipeline -----------------------------------------------------------


def test_pipeline_on_small_dirty_file(dirty_sales_file, tmp_path):
    output_path = tmp_path / "revenue_by_region.csv"
    pipeline.run_pipeline(dirty_sales_file, output_path)

    # North: 2 * 10 + 1000 * 10 - 5 = 10015 (1000 is flagged, but still counts)
    # South: 1 * 10 (minus removed, duplicate dropped, Mouse price filled in)
    #        + 1 * 50 = 60
    assert output_path.read_text().splitlines() == [
        "region,total_revenue",
        "North,10015.00",
        "South,60.00",
    ]


def test_clean_sales_on_real_file():
    sales = pipeline.clean_sales(pipeline.read_sales(pipeline.INPUT_PATH))

    assert len(sales) == 1500
    assert sales["order_id"].is_unique
    assert set(sales["region"]) == {"Central", "East", "North", "South", "West"}
    assert not sales.isna().any(axis=None)

    by_order = sales.set_index("order_id")
    assert by_order.loc["SO-10251", "quantity"] == 1762  # was "1 762"
    assert by_order.loc["SO-10137", "unit_price"] == 59.0  # was "59,00"
    assert by_order.loc["SO-11477", "unit_price"] == 89.0  # was empty
    assert by_order.loc["SO-10002", "discount"] == 0.0  # was empty


def test_committed_output_file_is_up_to_date(tmp_path):
    output_path = tmp_path / "revenue_by_region.csv"
    pipeline.run_pipeline(pipeline.INPUT_PATH, output_path)
    assert output_path.read_text() == pipeline.OUTPUT_PATH.read_text()
