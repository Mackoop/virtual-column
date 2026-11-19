"""Clean sales.csv, add a revenue column and write the total revenue of each region.

Run it with ``python pipeline.py``. Every cleaning step logs how many rows it
fixed, so the numbers in the README can be checked.
"""

import logging
from pathlib import Path

import pandas as pd

from solution import add_virtual_column

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
INPUT_PATH = PROJECT_DIR / "sales.csv"
OUTPUT_PATH = PROJECT_DIR / "revenue_by_region.csv"

# add_virtual_column accepts only letters and underscores in column labels.
COLUMN_NAMES = {
    "Order ID": "order_id",
    "Region": "region",
    "Product": "product",
    "Quantity": "quantity",
    "Unit Price": "unit_price",
    "Discount": "discount",
    "Order Date": "order_date",
}
REVENUE_ROLE = "quantity * unit_price - discount"

# Modified z-score above which a value is a potential outlier (Iglewicz and
# Hoaglin, as recommended by the NIST/SEMATECH e-Handbook of Statistical Methods).
SUSPICIOUS_Z_SCORE = 3.5


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    revenue_by_region = run_pipeline()
    logger.info(
        "\nWrote %s:\n%s",
        OUTPUT_PATH.name,
        revenue_by_region.to_string(index=False),
    )


def run_pipeline(
    input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH
) -> pd.DataFrame:
    """Run all steps and return the table that is written to ``output_path``."""
    sales = clean_sales(read_sales(input_path))
    sales = flag_suspicious_quantities(sales)
    sales = add_revenue(sales)
    revenue_by_region = total_revenue_by_region(sales)
    revenue_by_region.to_csv(
        output_path, index=False, float_format="%.2f", lineterminator="\n"
    )
    return revenue_by_region


def read_sales(path: Path) -> pd.DataFrame:
    """Read every field as text, so that no value is converted before cleaning."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# --- Cleaning: one function for each problem found in sales.csv ---------------


def clean_sales(raw_sales: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw export into one row per order line, with typed values."""
    sales = rename_columns(raw_sales)
    sales = drop_repeated_headers(sales)
    sales = drop_total_row(sales)
    sales = normalize_regions(sales)
    sales = parse_quantities(sales)
    sales = parse_unit_prices(sales)
    sales = fill_missing_unit_prices(sales)
    sales = parse_discounts(sales)
    sales = parse_order_dates(sales)
    sales = drop_duplicate_lines(sales)
    check_no_missing_values(sales)
    return sales.reset_index(drop=True)


def rename_columns(sales: pd.DataFrame) -> pd.DataFrame:
    """Strip spaces around header names ("Quantity ") and use snake_case labels."""
    return sales.rename(columns=str.strip).rename(columns=COLUMN_NAMES)


def drop_repeated_headers(sales: pd.DataFrame) -> pd.DataFrame:
    """Drop copies of the header row that appear between the data rows."""
    is_header = sales["order_id"] == "Order ID"
    report("repeated header row", is_header.sum())
    return sales[~is_header]


def drop_total_row(sales: pd.DataFrame) -> pd.DataFrame:
    """Drop the TOTAL summary row: it is not an order line."""
    is_total = sales["order_id"] == "TOTAL"
    report("TOTAL summary row", is_total.sum())
    return sales[~is_total]


def normalize_regions(sales: pd.DataFrame) -> pd.DataFrame:
    """Write every region the same way: " south  " and "SOUTH" become "South"."""
    region = sales["region"].str.strip().str.title()
    report("region with extra spaces or wrong case", (region != sales["region"]).sum())
    return sales.assign(region=region)


def parse_quantities(sales: pd.DataFrame) -> pd.DataFrame:
    """Convert quantities to numbers and remove the minus sign from negative ones.

    The file holds only sales, so a negative quantity is a sign error.
    """
    has_space = sales["quantity"].str.contains(" ", regex=False)
    report("quantity with a space as thousands separator", has_space.sum())
    quantity = parse_numbers(sales["quantity"])
    report("negative quantity (minus sign removed)", (quantity < 0).sum())
    return sales.assign(quantity=quantity.abs())


def parse_unit_prices(sales: pd.DataFrame) -> pd.DataFrame:
    """Convert unit prices to numbers. An empty price becomes NaN for now."""
    has_decimal_comma = sales["unit_price"].str.contains(",", regex=False)
    report("unit price with a decimal comma", has_decimal_comma.sum())
    return sales.assign(unit_price=parse_numbers(sales["unit_price"]))


def fill_missing_unit_prices(sales: pd.DataFrame) -> pd.DataFrame:
    """Fill a missing unit price with the price of the same product.

    Every product has exactly one unit price in the file, so the missing price
    is known. If a product ever has more prices, this step stops with an error
    instead of guessing.
    """
    prices_per_product = sales.groupby("product")["unit_price"].nunique()
    if (prices_per_product > 1).any():
        raise ValueError(f"Product with several unit prices:\n{prices_per_product}")

    is_missing = sales["unit_price"].isna()
    report("missing unit price (filled with product price)", is_missing.sum())
    product_price = sales.groupby("product")["unit_price"].transform("first")
    return sales.assign(unit_price=sales["unit_price"].fillna(product_price))


def parse_discounts(sales: pd.DataFrame) -> pd.DataFrame:
    """Convert discounts to numbers. An empty discount means no discount (0)."""
    is_empty = sales["discount"] == ""
    report("empty discount (set to 0)", is_empty.sum())
    return sales.assign(discount=parse_numbers(sales["discount"]).fillna(0.0))


def parse_order_dates(sales: pd.DataFrame) -> pd.DataFrame:
    """Convert order dates to datetimes. Fails on any date not in YYYY-MM-DD."""
    order_date = pd.to_datetime(sales["order_date"], format="%Y-%m-%d")
    return sales.assign(order_date=order_date)


def drop_duplicate_lines(sales: pd.DataFrame) -> pd.DataFrame:
    """Drop lines that are an exact copy of an earlier line.

    One order can have many lines, so lines that only share an order ID are
    kept. Runs after the other steps, so copies that differ only in formatting
    are found too.
    """
    is_duplicate = sales.duplicated()
    report("duplicate line (exact copy)", is_duplicate.sum())
    return sales[~is_duplicate]


def check_no_missing_values(sales: pd.DataFrame) -> None:
    """Stop if a value is still missing, so it cannot silently skew the totals."""
    missing_per_column = sales.isna().sum()
    if missing_per_column.any():
        raise ValueError(f"Missing values after cleaning:\n{missing_per_column}")


def parse_numbers(text: pd.Series) -> pd.Series:
    """Parse numbers like "1 762" or "39,90". An empty text becomes NaN.

    The export sometimes uses a European number format: a space as the
    thousands separator and a comma as the decimal separator.
    """
    without_spaces = text.str.replace(" ", "", regex=False)
    return pd.to_numeric(without_spaces.str.replace(",", ".", regex=False))


def report(problem: str, row_count: int) -> None:
    logger.info("%-48s %4d rows", problem, row_count)


# --- Quality flags: mark suspicious lines, never change or drop them ----------


def flag_suspicious_quantities(sales: pd.DataFrame) -> pd.DataFrame:
    """Add a ``suspicious_quantity`` column: True for an extreme quantity.

    A quantity is suspicious when its modified z-score is above
    SUSPICIOUS_Z_SCORE. Flagged lines keep their values and still count in the
    revenue; the warning lists them so the data owner can confirm them.
    """
    is_suspicious = modified_z_scores(sales["quantity"]).abs() > SUSPICIOUS_Z_SCORE
    report("suspicious quantity (flagged, kept)", is_suspicious.sum())
    if is_suspicious.any():
        suspicious_orders = ", ".join(sales.loc[is_suspicious, "order_id"])
        logger.warning("Check these orders with the data owner: %s", suspicious_orders)
    return sales.assign(suspicious_quantity=is_suspicious)


def modified_z_scores(values: pd.Series) -> pd.Series:
    """Return 0.6745 * (value - median) / MAD for every value.

    Median and MAD (median absolute deviation) are not distorted by the
    outliers themselves, unlike mean and standard deviation. If MAD is 0, every
    value different from the median gets an infinite score.
    """
    median = values.median()
    median_absolute_deviation = (values - median).abs().median()
    return 0.6745 * (values - median) / median_absolute_deviation


# --- Calculation --------------------------------------------------------------


def add_revenue(sales: pd.DataFrame) -> pd.DataFrame:
    """Add revenue = quantity * unit price - discount, using add_virtual_column."""
    sales_with_revenue = add_virtual_column(sales, REVENUE_ROLE, "revenue")
    if "revenue" not in sales_with_revenue.columns:
        raise ValueError(f"Cannot calculate revenue with role {REVENUE_ROLE!r}")
    return sales_with_revenue


def total_revenue_by_region(sales: pd.DataFrame) -> pd.DataFrame:
    """Sum the revenue of each region, rounded to cents."""
    revenue_by_region = sales.groupby("region", as_index=False)["revenue"].sum()
    return revenue_by_region.rename(columns={"revenue": "total_revenue"}).round(2)


if __name__ == "__main__":
    main()
