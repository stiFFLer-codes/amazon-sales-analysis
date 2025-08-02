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


def _parses_as_date(s):
    """True if >=90% of a sample of non-null values parse as dates."""
    sample = s.dropna().astype(str).head(500)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed", dayfirst=False)
    return parsed.notna().mean() >= 0.9


def detect(df, ov=None):
    """Infer a role for each column. `ov` holds CLI overrides that win outright."""
    ov = {k: v for k, v in (ov or {}).items() if v}
    n = len(df)
    roles = {"date": None, "value": None, "qty": None, "id": None, "status": None,
             "dims": [], "geo_dims": []}
    taken = set(ov.get("exclude", []))

    def hint(col, key):
        return re.search(NAME_HINTS[key], col, re.I) is not None

    # date: prefer a date-looking name that actually parses, else anything that parses
    if "date" in ov:
        roles["date"] = ov["date"]
    else:
        cands = [c for c in df.columns if c not in taken and _parses_as_date(df[c])]
        named = [c for c in cands if hint(c, "date")]
        roles["date"] = (named or cands or [None])[0]

    numeric = [c for c in df.columns
               if c not in taken and pd.api.types.is_numeric_dtype(df[c])
               and not pd.api.types.is_bool_dtype(df[c])]

    # value: a money-ish name first, else the numeric column with the widest spread
    if "value" in ov:
        roles["value"] = ov["value"]
    else:
        named = [c for c in numeric if hint(c, "value")]
        roles["value"] = named[0] if named else (
            max(numeric, key=lambda c: df[c].std(skipna=True) or 0, default=None))

    # qty: small integers with a quantity-ish name
    if "qty" in ov:
        roles["qty"] = ov["qty"]
    else:
        for c in numeric:
            if c != roles["value"] and hint(c, "qty") and df[c].nunique() <= 50:
                roles["qty"] = c
                break

    # id: near-unique values, identifier-ish name
    if "id" in ov:
        roles["id"] = ov["id"]
    else:
        for c in df.columns:
            if c in taken or c in (roles["date"], roles["value"], roles["qty"]):
                continue
            if df[c].nunique() / n > ID_CARDINALITY_RATIO and hint(c, "id"):
                roles["id"] = c
                break

    used = {roles[k] for k in ("date", "value", "qty", "id")} | taken

    # dimensions: everything categorical that is left, split by cardinality
    for c in df.columns:
        if c in used or pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            continue
        k = df[c].nunique(dropna=True)
        if k < 2:
            continue                                    # single value tells us nothing
        if k <= MAX_DIM_CARDINALITY:
            roles["dims"].append(c)
        elif k / n < ID_CARDINALITY_RATIO:   # anything near-unique is an id, not a dimension
            roles["geo_dims"].append(c)

    # status: the dimension whose values look like order outcomes
    if "status" in ov:
        roles["status"] = ov["status"]
    else:
        for c in roles["dims"]:
            vals = " ".join(df[c].dropna().astype(str).unique()[:40]).lower()
            if re.search(STATUS_VALUE_HINT, vals):
                roles["status"] = c
                break
    return roles


def clean(df, roles):
    """Parse dates, normalise messy text keys, coerce the value column. Logs what it did."""
    log = []
    if roles["date"]:
        before = df[roles["date"]].notna().sum()
        df[roles["date"]] = pd.to_datetime(df[roles["date"]], errors="coerce",
                                           format="mixed", dayfirst=False)
        bad = before - df[roles["date"]].notna().sum()
        log.append(f"Parsed <b>{roles['date']}</b> as dates" + (f" ({bad:,} unparseable)" if bad else ""))

    for c in roles["geo_dims"] + roles["dims"]:
        if pd.api.types.is_object_dtype(df[c]) or isinstance(df[c].dtype, pd.StringDtype):
            before = df[c].nunique()
            df[c] = df[c].astype(str).str.strip().str.upper().replace({"NAN": None})
            after = df[c].nunique()
            if after < before:
                log.append(f"Normalised case/whitespace in <b>{c}</b>: {before} → {after} distinct values")

    if roles["value"]:
        df[roles["value"]] = pd.to_numeric(df[roles["value"]], errors="coerce")
        nulls = df[roles["value"]].isna().sum()
        if nulls:
            log.append(f"<b>{roles['value']}</b> is missing on {nulls:,} rows "
                       f"({nulls / len(df):.1%}) — excluded from value totals")
    return df, log


# ---------------------------------------------------------------- presentation

def fig_to_img(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'<img src="data:image/png;base64,{b64}">'


def plot(series, title, kind="bar", ylabel=""):
    """One styling path for every chart in the report."""
    fig, ax = plt.subplots(figsize=(9, 4))
    extra = {"marker": "o", "markersize": 3, "linewidth": 1.6} if kind == "line" else {}
    series.plot(kind=kind, ax=ax, color="#4c72b0", legend=False, **extra)
    ax.set_title(title, fontsize=12, weight="bold", loc="left")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    if kind == "bar":
        ax.tick_params(axis="x", labelrotation=45)
        for label in ax.get_xticklabels():
            label.set_ha("right")
    return fig_to_img(fig)


def table(df, index=True):
    return df.to_html(index=index, border=0, float_format=lambda v: f"{v:,.2f}",
                      classes="tbl", na_rep="—")


def kpi(label, value):
    return f'<div class="kpi"><span>{html.escape(label)}</span><strong>{value}</strong></div>'
