"""Generic CSV analysis tool.

Point it at any tabular CSV; it infers what each column means (date, money,
quantity, id, status, dimension) and writes a self-contained HTML report with
charts and tables. Wrong guesses can be overridden with CLI flags.

    python analyze.py "Amazon Sale Report.csv"
    python analyze.py other.csv --value-col Revenue -o other.html
"""

import argparse
import base64
import html
import io
import re
import sys
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TOP_N = 15
MAX_DIM_CARDINALITY = 30        # above this a column is a "geo" dim: top-N only
ID_CARDINALITY_RATIO = 0.5      # unique/rows above this looks like an identifier

NAME_HINTS = {
    "date": r"date|time|day|month",
    "value": r"amount|revenue|sales|price|total|value|cost|gmv",
    "qty": r"qty|quantity|units|count|pcs",
    "id": r"\bid\b|order|invoice|transaction|receipt",
}
STATUS_VALUE_HINT = r"cancel|return|refund|deliver|ship|pending|complete|fail"
CANCEL_HINT = r"cancel|return|refund|reject|lost|damag|fail"


# ---------------------------------------------------------------- load / detect

def load(path):
    """Read the CSV, tidy column names, drop columns that are entirely empty."""
    try:
        df = pd.read_csv(path, low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, low_memory=False, encoding="latin-1")
    if df.empty:
        sys.exit(f"{path} has no rows.")
    df.columns = [str(c).strip() for c in df.columns]
    empty = [c for c in df.columns if df[c].isna().all()]
    return df.drop(columns=empty), empty

