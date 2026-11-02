# Amazon Sales Analysis

Data Analysis Internship (InnoByte Services) — Maitreya Sapariya
Project 78G0OL: analyze Amazon sales transactions and turn them into decisions someone can act on.

The analysis covers 128,976 line items across 120,229 orders, spanning 31 March to 29 June 2022.

Rather than writing a script that only understands this one file, the analysis runs through
`analyze.py`, a tool that infers what a CSV's columns mean and generates a full report from any of
them. Point it at this dataset and you get `report.html`. Point it at a different sales export and
it still works.

## What the analysis found

Full write-up with tables and reasoning: [`INSIGHTS.md`](INSIGHTS.md). Charts and every supporting
table: `report.html`. Three findings worth pulling out here.

**Rupees 78.59M is not the revenue figure.** The `Amount` column stays populated on cancelled
orders, so a plain `sum(Amount)` counts money that was never collected. Cancellations and returns
account for Rupees 8.31M of it. Realised revenue is Rupees 70.28M, and any dashboard summing that
column without filtering is running 10.6% high.

**The fulfilment comparison in this data is a trap.** A straight cross-tab says Merchant-fulfilled
orders fail at 22.9% against Amazon's 12.8%, which looks like a clear operational verdict. It isn't
one. The two channels write completely different status vocabularies: Amazon orders stop at
`Shipped` and never record a delivery or a return, while Merchant orders are tracked through to
`Delivered to Buyer` or `Returned to Seller`. Amazon's 0.00% return rate is missing instrumentation,
not performance. Cancellation is the only outcome both channels record the same way, and there the
gap is real but smaller: 17.5% against 12.8%.

**Customer segmentation, as the brief asks for it, cannot be done with this file.** There is no
customer ID, no email, no repeat-purchase key. Nothing links two orders to the same person, so
retention, cohorts and lifetime value are all out of reach. `INSIGHTS.md` segments by order value
tier, geography and B2B flag instead, and says plainly that this is a substitute.

## Running it

```bash
pip install -r requirements.txt
python analyze.py "Amazon Sale Report.csv"
```

That writes `report.html`, a single self-contained file with 22 charts and 28 tables. Images are
embedded, so it opens in a browser with no server and no assets folder.

Takes about 40 seconds on the full 129k-row dataset.

## How it reads an unfamiliar CSV

On load the tool drops any column that is entirely empty, then assigns each remaining column a role:

| Role | How it is inferred |
|---|---|
| date | name looks like a date, and at least 90% of a sample actually parses as one |
| value | numeric with a money-ish name (`amount`, `revenue`, `price`, `total`), otherwise the widest-spread numeric column |
| quantity | small-range integer named like a count |
| id | near-unique values with an identifier-ish name; used for order counts, never charted |
| status | a categorical whose *values* mention cancel, return, ship or deliver |
| dimension | any other categorical with 30 or fewer distinct values, which gets a full breakdown |
| high-cardinality | text with more distinct values than that but still well short of unique, such as cities and states, which gets top-N treatment |

Inference is a guess, so the tool prints its conclusions on every run and repeats them at the top of
the report. A wrong guess is visible rather than silent, and any of them can be overridden:

```bash
python analyze.py sales.csv --value-col Revenue --date-col "Invoice Date"
python analyze.py sales.csv --exclude notes internal_ref --top 25 -o q3.html
```

Available flags: `--date-col`, `--value-col`, `--qty-col`, `--id-col`, `--status-col`, `--exclude`,
`--top`, `-o`.

Missing roles degrade instead of crashing. A CSV with no date column skips the trend section and
reports the rest.

## Cleaning, and what it tells you about it

Three things happen automatically:

- Columns that are 100% empty are dropped. In this dataset that removes `New` and `PendingS`.
- Text dimensions are trimmed and upper-cased, which collapses duplicate keys. `ship-state` arrives
  with 69 distinct values for roughly 36 real states and comes out at 47.
- The value column is coerced to numeric, and the tool reports how many rows are missing it.

Every one of these actions is listed in the report's data quality section. The point is that a
reader can see what was changed underneath a number before trusting it.

The residue after normalisation is about 15 rows carrying genuine misspellings (`RAJSHTHAN`,
`ORISSA`, `PB`) out of 128,976. Fuzzy matching them was not worth the risk of merging two real
places by accident, so the tool leaves them and the write-up says so.

## Data notes

**Exact duplicate rows.** The report contains 959 rows that are exact copies of another row
(every column except the index), across 891 groups touching 873 orders.

The file has no SKU or ASIN column, so two identical units in one order look the same as an
export duplicate. The evidence points both ways:

- Towards export duplicates: cancelled lines are over-represented among the copies (28.8% of
  copied rows against 14.2% of all rows), and so are zero-quantity lines (26.1% against 9.9%).
  A cancelled line with no units, appearing twice, is hard to read as two purchases. In 689 of
  the 873 orders, every line is part of a copy.
- Towards real repeat units: the export normally puts each unit on its own line (only 387 of
  128,976 lines carry more than one unit), and 9,935 lines share an order, category and size
  with another line, of which only 1,850 are exact copies. Two of the same item bought together
  would produce exactly this kind of row.

**Decision:** the rows are kept, and all figures are reported as-is. Removing them would lower
the totals by about 0.5 to 0.7 percent (line items 128,976 to 128,017; gross order value
Rupees 78.59M to Rupees 78.18M). To reproduce:

```bash
python scripts/check_duplicates.py
```

## Tests

```bash
python test_analyze.py
```

Plain asserts, no framework. Five checks: role detection on a synthetic frame, override precedence,
key normalisation, a full end-to-end render, and the two degradation paths where the date column or
the numeric column is absent.

## Repository layout

```
analyze.py           the tool
scripts/             check_duplicates.py, the duplicate check in Data notes
test_analyze.py      its tests
requirements.txt     pandas, matplotlib
INSIGHTS.md          findings and recommendations
report.html          generated output
docs/                assignment brief and completion certificate
LICENSE              MIT
Amazon Sale Report.csv
```

An earlier version of this project split the work across `Data_Analysis.py` and four
`amazon_analysis_part*.py` scripts. They have been replaced, for three reasons worth recording:

- The filename and every column name were hardcoded (`df_clean['Amount']`, `df_clean['Qty']`), so
  running the analysis on a different export meant editing the scripts.
- The parts were not independently runnable. Part 3 opens with "Assuming df_clean is available from
  Part 2", which means the four files are one script that has to be pasted together in order.
- Part 3 reported `df_clean['Amount'].sum()` as total revenue and `len(df_clean)` as total orders.
  Both are wrong on this dataset: the first counts cancelled orders as revenue, and the second
  counts line items, of which there are 8,747 more than there are orders.

The old files remain in the git history if you need them.

## Assignment documents

The original brief is at [`docs/brief-78G0OL.pdf`](docs/brief-78G0OL.pdf). The internship was
completed with InnoByte Services; the certificate is at
[`docs/completion-certificate.pdf`](docs/completion-certificate.pdf).

## License

MIT. See [`LICENSE`](LICENSE).
