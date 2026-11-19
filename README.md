# Virtual columns in pandas

- `solution.py`: `add_virtual_column`, which adds a column calculated from a simple formula such as `"quantity * price"`.
- `pipeline.py`: cleans `sales.csv`, adds revenue with that function and saves the revenue of each region to `revenue_by_region.csv`.
- `sales_statistics.py`: prints the statistics about suspicious quantities shown below.

`test_virtual_column.py` and `sales.csv` are the original files, unchanged.

## How to run

You need Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```sh
uv sync                            # install dependencies
uv run python pipeline.py          # clean the data, write revenue_by_region.csv
uv run pytest                      # run all tests
uv run python sales_statistics.py  # print the statistics from this README
```

Without uv: `pip install pandas pytest`, then run the same commands without `uv run`.

The code is checked with `ruff check`, and formatted with `ruff format` and Prettier.

## `add_virtual_column`

The formula can use column names, `+`, `-`, `*` and brackets, for example `"quantity * unit_price - discount"`. Multiplication goes first, as in maths. If anything is wrong, the function returns an empty DataFrame. This covers a bad name, an unknown column, a text column and any other character. The formula is read with Python's own parser (`ast`) and never run with `eval`, so it cannot run any code.

Where the task was unclear, I assumed:

- The task example shows the new column as `price_total`, but passes `"total"`. I treat this as a typo and use the name that is passed.
- "Letters" means the English letters A–Z.
- Only the columns used in the formula, and the new column, must have valid names. Other columns can be named anything.
- Numbers, `/` and `**` are not allowed in the formula.
- If the new column already exists, it is replaced.

## Problems in `sales.csv`

| Problem                                             | Rows | What I did                                                  |
| --------------------------------------------------- | ---: | ----------------------------------------------------------- |
| Header `Quantity ` ends with a space                |    – | Trimmed. Columns renamed to `snake_case`, e.g. `unit_price` |
| Header repeated in the middle of the file           |    1 | Removed                                                     |
| `TOTAL` row at the end                              |    1 | Removed                                                     |
| Region written in different ways (`EAST`, ` south`) |   15 | Spaces trimmed, first letter capitalised                    |
| Quantity with a space, e.g. `1 762`                 |    4 | Space removed                                               |
| Negative quantity                                   |    6 | Minus removed: the file holds only sales                    |
| Price with a decimal comma, e.g. `39,90`            |    7 | Comma changed to a dot                                      |
| Missing price                                       |    4 | Filled with the product's price (each product has one)      |
| Empty discount                                      |  963 | Set to 0                                                    |
| Line copied twice                                   |    5 | Copy removed                                                |

No other rows are removed. 1,500 orders remain, from `SO-10001` to `SO-11500`. Dates, prices and discounts were checked and contain no other problems.

### Four suspicious quantities

Orders `SO-10251`, `SO-10734`, `SO-11088` and `SO-11312` have quantities between 1,371 and 1,762. The statistics below show that they do not fit the rest of the data. To print them, run `uv run python sales_statistics.py`.

| Statistic                                      | Value                                                              | What it means                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------- |
| Other 1,496 quantities                         | Spread evenly from 1 to 40 (chi-square 33.2, below the 54.6 limit) | Normal orders follow one simple pattern                                                |
| Largest other quantity                         | 40, in every product and region                                    | There is an upper limit                                                                |
| Quantities between 41 and 1,370                | None                                                               | These 4 are not a long tail of big orders                                              |
| Compared with the largest other quantity       | 34 to 44 times bigger                                              |                                                                                        |
| Modified z-score (median and MAD)              | 91 to 117 (limit: 3.5)                                             | Far beyond the outlier limit                                                           |
| Ordinary z-score (mean and standard deviation) | 16 to 21                                                           | Lower, because these 4 values inflate the standard deviation.                          |
| Lines with a discount, by quantity range       | 34% to 38% in every range                                          | Discounts do not depend on quantity, so the missing discount on these 4 proves nothing |
| Share of all revenue                           | 12.6% (324,349.00)                                                 |                                                                                        |
| Largest one: `SO-11312`, 1,427 headsets        | 169,813.00                                                         | 17 times the largest other line, 25.5% of North's revenue                              |

Their true values cannot be recovered, and rows must not be dropped. The pipeline therefore keeps them but flags them in a `suspicious_quantity` column and prints their IDs. A quantity is flagged when its modified z-score is above 3.5, as [NIST recommends](https://itl.nist.gov/div898/handbook/eda/section3/eda35h.htm).

They decide which region is first:

| Region  |  With them | Without them | Rank: with → without |
| ------- | ---------: | -----------: | :------------------: |
| North   | 666,057.12 |   459,242.12 |        1 → 2         |
| Central | 516,421.67 |   435,532.67 |        2 → 5         |
| South   | 504,036.04 |   467,391.04 |        3 → 1         |
| West    | 443,338.29 |   443,338.29 |        4 → 3         |
| East    | 442,219.91 |   442,219.91 |        5 → 4         |

**In a real project I would check them with the owner of the data.**

## Result

| Region  | Total revenue |
| ------- | ------------: |
| Central |    516,421.67 |
| East    |    442,219.91 |
| North   |    666,057.12 |
| South   |    504,036.04 |
| West    |    443,338.29 |
