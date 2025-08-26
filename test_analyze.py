"""Self-checks for analyze.py: python test_analyze.py"""

import os
import tempfile

import pandas as pd

from analyze import clean, detect, run

TMP = tempfile.mkdtemp()


def csv(df, name):
    p = os.path.join(TMP, name)
    df.to_csv(p, index=False)
    return p


def test_detect_roles():
    df = pd.DataFrame({
        "Order ID": [f"o{i}" for i in range(60)],
        "Date": ["01-05-22"] * 60,
        "Amount": range(60),
        "Qty": [1] * 30 + [2] * 30,
        "Status": ["Shipped", "Cancelled"] * 30,
        "Category": ["Shirt", "Shoes"] * 30,
        "Empty": [None] * 60,
    })
    r = detect(df, {})
    assert r["date"] == "Date", r
    assert r["value"] == "Amount", r
    assert r["qty"] == "Qty", r
    assert r["id"] == "Order ID", r
    assert r["status"] == "Status", r
    assert "Category" in r["dims"], r
    assert "Order ID" not in r["dims"], r          # ids never become chart dimensions


def test_overrides_win():
    df = pd.DataFrame({"Amount": range(10), "Revenue": range(10)})
    assert detect(df, {"value": "Revenue"})["value"] == "Revenue"


def test_clean_collapses_case_and_whitespace():
    df = pd.DataFrame({
        "city": ([" delhi", "DELHI", "Delhi "] * 20) + [f"c{i}" for i in range(40)],
        "amt": range(100),
    })
    roles = detect(df, {})
    assert "city" in roles["geo_dims"], roles
    out, log = clean(df, roles)
    assert (out["city"] == "DELHI").sum() == 60, out["city"].value_counts()
    assert any("Normalised" in x for x in log), log


def test_full_run_produces_sections():
    n = 120
    df = pd.DataFrame({
        "Order ID": [f"o{i}" for i in range(n)],
        "Date": pd.date_range("2022-01-01", periods=n).strftime("%m-%d-%y"),
        "Amount": [100 + i * 7 for i in range(n)],
        "Qty": [1] * n,
        "Status": ["Shipped"] * 90 + ["Cancelled"] * 30,
        "Category": ["Shirt", "Shoes"] * (n // 2),
        "ship-city": [f"CITY{i % 40}" for i in range(n)],
    })
    out = os.path.join(TMP, "r.html")
    run(csv(df, "full.csv"), out)
    html = open(out, encoding="utf-8").read()
    for heading in ("Overview", "Data quality", "Trends over time", "Category breakdowns",
                    "Outcome / fulfilment", "Geography", "Segmentation", "Numeric summary"):
        assert heading in html, f"missing section: {heading}"
    assert "data:image/png;base64," in html, "no charts rendered"
    assert "Failed outcome rate" in html and "25.0%" in html, "cancel rate wrong"


def test_degrades_without_date_or_numbers():
    """Missing roles must produce notes, not exceptions."""
    no_date = pd.DataFrame({"Category": ["a", "b"] * 20, "Amount": range(40)})
    run(csv(no_date, "nodate.csv"), os.path.join(TMP, "nd.html"))

    text_only = pd.DataFrame({"Category": ["a", "b"] * 20, "Size": ["S", "M"] * 20})
    out = os.path.join(TMP, "to.html")
    run(csv(text_only, "textonly.csv"), out)
    assert "segmentation skipped" in open(out, encoding="utf-8").read().lower()


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall passed")
