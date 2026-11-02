"""Count exact duplicate rows in the sales report and show what removing them would change.

A row counts as a duplicate when every column except the leading `index` matches an
earlier row. The file has no SKU or ASIN column, so this cannot tell an export
duplicate from two identical units bought in one order; the numbers below are the
size of the question, not an answer to it. See "Data notes" in the README.

Run from the repository root:

    python scripts/check_duplicates.py
    python scripts/check_duplicates.py path/to/other.csv
"""

import argparse

import pandas as pd

# The failed-outcome rule from analyze.py (CANCEL_HINT), so "realised revenue" here
# means exactly what it means in report.html and INSIGHTS.md. Copied rather than
# imported so this check needs only pandas; keep the two in step.
CANCEL_HINT = r"cancel|return|refund|reject|lost|damag|fail"

DEFAULT_CSV = "Amazon Sale Report.csv"


def totals(df):
    failed = df["Status"].astype(str).str.contains(CANCEL_HINT, case=False, na=False)
    gross = df["Amount"].sum()
    return {
        "line items": len(df),
        "orders": df["Order ID"].nunique(),
        "units": int(df["Qty"].sum()),
        "gross order value": gross,
        "realised revenue": gross - df.loc[failed, "Amount"].sum(),
    }


def fmt(key, value):
    if key in ("gross order value", "realised revenue"):
        return f"INR {value / 1e6:.2f}M"
    return f"{value:,}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="?", default=DEFAULT_CSV)
    args = ap.parse_args()

    df = pd.read_csv(args.csv, low_memory=False)
    cols = [c for c in df.columns if c != "index"]

    extra = df.duplicated(subset=cols, keep="first")
    in_group = df.duplicated(subset=cols, keep=False)
    groups = df[in_group].groupby(cols, dropna=False).ngroups
    orders = df.loc[in_group, "Order ID"].nunique()

    print("Exact duplicate rows (every column except the index)")
    print(f"  extra copies      {extra.sum():>8,}")
    print(f"  duplicate groups  {groups:>8,}")
    print(f"  orders touched    {orders:>8,}")
    print()

    before, after = totals(df), totals(df[~extra])
    print(f"{'':<19}{'as-is':>14}{'duplicates removed':>22}{'change':>10}")
    for key in before:
        change = (after[key] - before[key]) / before[key] * 100
        print(f"{key:<19}{fmt(key, before[key]):>14}{fmt(key, after[key]):>22}{change:>9.2f}%")


if __name__ == "__main__":
    main()
