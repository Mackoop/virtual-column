"""Print the statistics about the four suspicious quantities shown in the README.

Run it with ``uv run python sales_statistics.py``.
"""

import pandas as pd

from pipeline import (
    INPUT_PATH,
    SUSPICIOUS_Z_SCORE,
    add_revenue,
    clean_sales,
    modified_z_scores,
    read_sales,
)

# Chi-square limit for 39 degrees of freedom at the 95% level, from tables.
# Below it, the quantities 1 to 40 are spread evenly.
CHI_SQUARE_LIMIT = 54.57


def main() -> None:
    sales = add_revenue(clean_sales(read_sales(INPUT_PATH)))
    quantity = sales["quantity"]

    # The same rule that the pipeline uses to flag suspicious quantities.
    is_suspicious = modified_z_scores(quantity).abs() > SUSPICIOUS_Z_SCORE
    suspicious = sales[is_suspicious]
    normal = sales[~is_suspicious]

    print("Suspicious orders:", ", ".join(suspicious["order_id"]))
    print("Their quantities:", suspicious["quantity"].tolist())

    print("\n--- Other quantities ---")
    counts = normal["quantity"].value_counts().reindex(range(1, 41), fill_value=0)
    expected = len(normal) / 40
    chi_square = ((counts - expected) ** 2 / expected).sum()
    print(f"Chi-square: {chi_square:.1f} (limit {CHI_SQUARE_LIMIT:.1f})")

    max_per_product = normal.groupby("product")["quantity"].max()
    max_per_region = normal.groupby("region")["quantity"].max()
    print("Largest quantity per product:", max_per_product.unique().tolist())
    print("Largest quantity per region:", max_per_region.unique().tolist())
    print("Quantities between 41 and 1370:", quantity.between(41, 1370).sum())

    times_bigger = suspicious["quantity"] / normal["quantity"].max()
    print("Times bigger than the largest other:", times_bigger.round(1).tolist())

    print("\n--- Outlier scores ---")
    modified_z = modified_z_scores(quantity)[is_suspicious]
    ordinary_z = ((quantity - quantity.mean()) / quantity.std())[is_suspicious]
    print("Modified z-score:", modified_z.round().tolist())
    print("Limit for a suspicious value:", SUSPICIOUS_Z_SCORE)
    print("Ordinary z-score:", ordinary_z.round(1).tolist())

    print("\n--- Lines with a discount, by quantity range ---")
    has_discount = normal["discount"] > 0
    quantity_range = pd.cut(normal["quantity"], [0, 10, 20, 30, 40])
    share = has_discount.groupby(quantity_range, observed=True).mean()
    print((share * 100).round(1).astype(str).add("%").to_string())

    print("\n--- Revenue ---")
    suspicious_revenue = suspicious["revenue"].sum()
    share_of_revenue = suspicious_revenue / sales["revenue"].sum()
    print(f"Suspicious orders: {suspicious_revenue:,.2f} ({share_of_revenue:.1%})")

    largest = suspicious.loc[suspicious["revenue"].idxmax()]
    region_revenue = sales.loc[sales["region"] == largest["region"], "revenue"].sum()
    print(
        f"Largest: {largest['order_id']}, {largest['revenue']:,.2f}, "
        f"{largest['revenue'] / normal['revenue'].max():.0f} times the largest "
        f"other line, {largest['revenue'] / region_revenue:.1%} of "
        f"{largest['region']}"
    )

    print("\n--- Region ranking ---")
    ranking = pd.DataFrame(
        {
            "with_them": sales.groupby("region")["revenue"].sum(),
            "without_them": normal.groupby("region")["revenue"].sum(),
        }
    )
    ranking["rank_with"] = ranking["with_them"].rank(ascending=False).astype(int)
    ranking["rank_without"] = ranking["without_them"].rank(ascending=False).astype(int)
    print(ranking.sort_values("rank_with").round(2).to_string())


if __name__ == "__main__":
    main()
