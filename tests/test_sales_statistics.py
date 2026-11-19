"""Check that sales_statistics.py prints the numbers used in the README."""

import sales_statistics


def test_prints_statistics_used_in_readme(capsys):
    sales_statistics.main()
    output = capsys.readouterr().out

    assert "Suspicious orders: SO-10251, SO-10734, SO-11088, SO-11312" in output
    assert "Quantities between 41 and 1370: 0" in output
    assert "324,349.00 (12.6%)" in output
