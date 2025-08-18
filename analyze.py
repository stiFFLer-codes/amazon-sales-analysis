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


# ---------------------------------------------------------------- sections
# Each builder returns HTML, or a note when the data can't support it.

def s_overview(df, roles):
    v, d, q, i = roles["value"], roles["date"], roles["qty"], roles["id"]
    tiles = [kpi("Rows", f"{len(df):,}"), kpi("Columns", f"{df.shape[1]}")]
    if d and df[d].notna().any():
        tiles.append(kpi("Date range", f"{df[d].min():%d %b %Y} → {df[d].max():%d %b %Y}"))
    unit = "order" if i else "record"
    orders = df[i].nunique() if i else len(df)
    tiles.append(kpi(unit.capitalize() + "s", f"{orders:,}"))
    if v:
        total = df[v].sum()
        tiles += [kpi(f"Total {v}", f"{total:,.0f}"),
                  kpi(f"Avg {v} per {unit}", f"{total / orders:,.0f}")]
    if q:
        tiles.append(kpi(f"Total {q}", f"{df[q].sum():,.0f}"))
    if roles["status"]:
        bad = df[roles["status"]].astype(str).str.contains(CANCEL_HINT, case=False, na=False)
        tiles.append(kpi("Failed outcome rate", f"{bad.mean():.1%}"))
        if v:
            # gross totals quietly include failed rows; show what actually stuck
            lost = df.loc[bad, v].sum()
            tiles += [kpi(f"{v} in failed rows", f"{lost:,.0f}"),
                      kpi(f"Realised {v}", f"{df[v].sum() - lost:,.0f}")]
    return f'<div class="kpis">{"".join(tiles)}</div>'


def s_quality(df, roles, log, dropped):
    parts = []
    if dropped:
        parts.append(f"<p>Dropped {len(dropped)} entirely empty column(s): "
                     f"<b>{html.escape(', '.join(dropped))}</b></p>")
    if log:
        parts.append("<ul>" + "".join(f"<li>{x}</li>" for x in log) + "</ul>")
    if roles["id"]:
        dup = df[roles["id"]].duplicated().sum()
        parts.append(f"<p><b>{roles['id']}</b> repeats on {dup:,} rows — "
                     f"{len(df):,} line items across {df[roles['id']].nunique():,} orders."
                     f" Order-level figures are de-duplicated.</p>")
    miss = df.isna().sum()
    miss = miss[miss > 0].sort_values(ascending=False)
    if not miss.empty:
        m = miss.to_frame("Missing")
        m["% of rows"] = (m["Missing"] / len(df) * 100).round(1)
        parts.append(table(m))
    return "".join(parts) or "<p class='note'>No data quality issues found.</p>"


def s_trends(df, roles):
    d, v = roles["date"], roles["value"]
    if not d or df[d].notna().sum() < 2:
        return "<p class='note'>No usable date column — trend analysis skipped.</p>"
    t = df.dropna(subset=[d]).set_index(d)
    metric = t[v] if v else t.iloc[:, 0].notna().astype(int)
    label = v if v else "records"
    out = [plot(metric.resample("D").sum(), f"Daily {label}", "line", label),
           plot(metric.resample("D").size(), "Daily record count", "line", "records")]
    monthly = metric.resample("MS").agg(["sum", "size", "mean"])
    monthly.columns = [f"Total {label}", "Records", f"Avg {label}"]
    monthly.index = monthly.index.strftime("%b %Y")
    out.append(table(monthly))
    dow = metric.groupby(t.index.dayofweek).sum()
    dow.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][:len(dow)]
    out.append(plot(dow, f"{label} by day of week", "bar", label))
    return "".join(out)


def _breakdown(df, col, roles, top):
    """value / share / average per category — the workhorse table."""
    v, q, i = roles["value"], roles["qty"], roles["id"]
    agg = {"Records": (col, "size")}
    if i:
        agg["Orders"] = (i, "nunique")
    if v:
        agg[f"Total {v}"] = (v, "sum")
        agg[f"Avg {v}"] = (v, "mean")
    if q:
        agg[f"Total {q}"] = (q, "sum")
    g = df.groupby(col, dropna=True).agg(**agg)
    sort_col = f"Total {v}" if v else "Records"
    g = g.sort_values(sort_col, ascending=False)
    g["Share %"] = (g[sort_col] / g[sort_col].sum() * 100).round(1)
    return g.head(top), sort_col


def s_breakdowns(df, roles, top):
    if not roles["dims"]:
        return "<p class='note'>No low-cardinality categorical columns found.</p>"
    out = []
    for col in roles["dims"]:
        g, sort_col = _breakdown(df, col, roles, top)
        out.append(f"<h3>{html.escape(col)}</h3>")
        out.append(plot(g[sort_col].head(10), f"{sort_col} by {col}", "bar", sort_col))
        out.append(table(g))
    return "".join(out)


def s_outcomes(df, roles, top):
    st = roles["status"]
    if not st:
        return "<p class='note'>No status-like column found — outcome analysis skipped.</p>"
    df = df.copy()
    df["_bad"] = df[st].astype(str).str.contains(CANCEL_HINT, case=False, na=False)
    out = [f"<p>Rows whose <b>{html.escape(st)}</b> matches "
           f"<code>{CANCEL_HINT}</code> count as a failed outcome "
           f"(overall {df['_bad'].mean():.1%}).</p>",
           table(df[st].value_counts().to_frame("Records").assign(
               **{"Share %": lambda x: (x.Records / len(df) * 100).round(1)}))]
    for col in [c for c in roles["dims"] if c != st] + roles["geo_dims"][:1]:
        g = df.groupby(col).agg(Records=(col, "size"), Failed=("_bad", "sum"))
        g["Failure %"] = (g.Failed / g.Records * 100).round(1)
        g = g[g.Records >= max(30, len(df) * 0.001)].sort_values("Failure %", ascending=False)
        if g.empty:
            continue
        out.append(f"<h3>Failure rate by {html.escape(col)}</h3>")
        out.append(plot(g["Failure %"].head(10), f"Failure % by {col}", "bar", "%"))
        out.append(table(g.head(top)))
    return "".join(out)

