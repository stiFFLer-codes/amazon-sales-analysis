# Amazon Sales Report — Findings & Recommendations

Project **78G0OL**. Source: `Amazon Sale Report.csv`, 128,976 line items across 120,229 orders,
**31 Mar – 29 Jun 2022** (91 days). All figures produced by `analyze.py`; charts and full tables
are in [`report.html`](report.html).

---

## Headline numbers

| Metric | Value |
|---|---|
| Gross order value | **₹78.59M** |
| Value in cancelled / returned rows | **₹8.31M** (10.6%) |
| **Realised revenue** | **₹70.28M** |
| Orders | 120,229 (128,976 line items) |
| Average order value | ₹654 |
| Units shipped | 116,646 |
| Cancelled | 18,334 rows (14.2%) |
| Returned / rejected / lost | 2,116 rows (1.6%) |

**The first thing to correct: ₹78.59M is not revenue.** `Amount` is populated on cancelled orders
too, so the naive `sum(Amount)` overstates the business by **₹8.31M**. Every figure below uses
gross value where it is comparing mix, and realised value where it is describing money earned.

---

## 1. Sales overview — the trend is down, and it is not a data artefact

| Month | Days | Gross | Realised | Revenue / day |
|---|---|---|---|---|
| Mar 2022 | 1 | ₹0.10M | ₹0.09M | — *(partial, exclude)* |
| Apr 2022 | 30 | ₹28.84M | ₹25.67M | **₹961k** |
| May 2022 | 31 | ₹26.23M | ₹23.47M | **₹846k** (−12.0%) |
| Jun 2022 | 29 | ₹23.43M | ₹21.05M | **₹808k** (−4.5%) |

March holds a single day (31 Mar) and June stops on the 29th, so raw monthly totals mislead —
normalised per day, revenue fell **16% from April to June**. AOV moved the other way (₹626 → ₹661),
so the decline is **volume, not price**: 49,068 line items in April against 37,697 in June, a 23%
drop in orders against a 16% drop in revenue.

Weekday demand is remarkably flat (Sunday strongest at ₹12.03M, Thursday weakest at ₹10.36M — a
16% spread with no weekend spike), which points to steady marketplace traffic rather than
campaign-driven bursts.

> **Caveat:** 91 days spanning one quarter cannot support any seasonality claim. This is a
> trend within a quarter, not a seasonal pattern.

## 2. Product analysis — two categories are the business

| Category | Gross | Share | Units | AOV |
|---|---|---|---|---|
| T-shirt | ₹39.21M | **49.9%** | 45,292 | ₹833 |
| Shirt | ₹21.30M | 27.1% | 45,044 | ₹456 |
| Blazzer | ₹11.22M | 14.3% | 13,943 | ₹763 |
| Trousers | ₹5.35M | 6.8% | 9,898 | ₹526 |
| Perfume / Wallet / Socks / Shoes / Watch | ₹1.52M | **1.9%** | 2,469 | — |

**T-shirt and Shirt sell in near-identical unit volumes (45.3k vs 45.0k) but T-shirt earns ₹17.9M
more**, purely on an AOV nearly double Shirt's. T-shirt is the margin engine; Shirt is the traffic
driver.

The five non-apparel categories together are **1.9% of revenue** and 153 pairs of shoes and 3
watches over a full quarter — this is an apparel business with a rounding error attached.

Sizes cluster tightly in the middle: **M, L, XL and XXL are 62.9% of revenue**, and the curve
decays symmetrically to XS (8.9%) and 4XL–6XL (1.6% combined). Notably, the extended sizes carry the
*highest* AOVs (4XL ₹820, 5XL ₹808, 6XL ₹817 vs M ₹653) — low volume, high value per order.

## 3. Fulfilment — the comparison everyone gets wrong

| | Amazon (FBA) | Merchant |
|---|---|---|
| Line items | 89,713 (69.6%) | 39,263 (30.4%) |
| Gross revenue | ₹54.33M (69.1%) | ₹24.26M (30.9%) |
| AOV | ₹649 | ₹647 |
| Cancelled | **12.79%** | **17.47%** |
| Returned / rejected | 0.00% | 5.37% |

**The 0.00% return rate for Amazon fulfilment is not an achievement — it is missing data.** The
two channels use completely disjoint status vocabularies:

- **Amazon:** `Shipped` (77,815), `Cancelled`, `Pending`, `Shipping` — and nothing else.
- **Merchant:** `Shipped - Delivered to Buyer` (28,756), `Shipped - Returned to Seller`,
  `Picked Up`, `Out for Delivery`, `Rejected by Buyer`, `Lost in Transit`, `Damaged`…

Amazon-fulfilled orders terminate at `Shipped` with **no delivery confirmation and no return
status recorded in this feed**. Merchant orders are tracked to their real outcome. So the
"Merchant fails at 22.9% vs Amazon at 12.8%" reading that falls out of a naive cross-tab is
**comparing two different measurement regimes, not two operations.**

The one metric that *is* comparable — `Cancelled` appears in both vocabularies — still shows a
real gap: **Merchant cancels 17.5% of orders against Amazon's 12.8%, a 4.7-point penalty.**

Also note `Fulfilment` and `ship-service-level` are effectively the same column: Merchant is 100%
Standard, Amazon is 98.8% Expedited. "Standard ships worse than Expedited" and "Merchant ships
worse than Amazon" are **one finding, not two**.

## 4. Customer segmentation — what this dataset can and cannot do

**There is no customer identifier in this file.** No customer ID, no email, no repeat-purchase key.
True customer segmentation (RFM, cohort retention, lifetime value) is **not possible** with this
data, and any deliverable claiming otherwise is inventing it. What can be segmented is the *order*:

| Tier | Orders | Value | Share of value | Avg order |
|---|---|---|---|---|
| Top 5% | 5,284 | ₹9.27M | **11.8%** | ₹1,754 |
| 80–95% | 16,460 | ₹18.03M | 22.9% | ₹1,096 |
| 50–80% | 33,156 | ₹25.17M | 32.0% | ₹759 |
| Bottom 50% | 55,647 | ₹26.12M | 33.2% | ₹469 |

The distribution is **unusually flat for retail** — no Pareto effect. The top 5% of orders carry
only 11.8% of value, where a typical e-commerce book would show 25–40%. Revenue here is broad and
shallow: a high volume of similar mid-value apparel orders, not a few whales. That has a direct
strategic consequence — **there is no high-value tail worth building a VIP programme around; growth
has to come from order volume and basket size.**

B2B is negligible: **872 line items (0.68%), ₹0.59M — 0.75% of revenue** — though B2B
cancels far less (9.4% vs 15.9%).

## 5. Geography — extreme concentration in five states

| State | Gross | Share | Cancel+return rate |
|---|---|---|---|
| Maharashtra | ₹13.34M | 17.0% | 15% |
| Karnataka | ₹10.48M | 13.3% | 14% |
| Telangana | ₹6.92M | 8.8% | 16% |
| Uttar Pradesh | ₹6.82M | 8.7% | **17%** |
| Tamil Nadu | ₹6.52M | 8.3% | 15% |

**Top 5 states = 56.1% of revenue. Top 10 = 78.7%.** At city level: Bengaluru (₹7.25M), Hyderabad
(₹5.60M), Mumbai (₹4.29M), New Delhi (₹3.95M), Chennai (₹3.61M) — **top 10 cities are 41.5% of
revenue** out of 7,291 cities shipped to. This is a metro-tier-1 business.

Failure rates are geographically tight (14–19%), so no state is operationally broken. Kerala is the
worst at 19% and Uttar Pradesh at 17% against a 15.9% national average — worth a look, not an alarm.

**Data quality note:** `ship-state` held 69 distinct values for ~36 real states. Case and whitespace
normalisation collapsed that to 47; the remaining ~11 are genuine misspellings and codes
(`RAJSHTHAN`, `RAJSTHAN`, `ORISSA`, `PB`, `RJ`, `NL`, `PUNJAB/MOHALI/ZIRAKPUR`) totalling **~15 rows
out of 128,976** — immaterial to every figure above, and deliberately not fuzzy-matched.

---

## Recommendations

**1. Fix the ₹8.31M reporting gap first.** Cancelled orders carry a populated `Amount`, so every
downstream dashboard summing that column overstates revenue by 10.6%. Report gross and realised
separately. *(The tool now emits both as standard.)*

**2. Attack cancellations, not returns — that is where the money is.** ₹6.92M sits in cancelled
orders versus ₹1.39M in returns. A 14.2% cancellation rate is high for apparel; the concentration in
`Qty=0` rows (12,704 of 18,334 cancellations) points at **stock-outs after order placement**.
Priority action: reconcile inventory feed latency against cancellation timestamps.

**3. Close the 4.7-point Merchant cancellation gap.** Merchant cancels 17.5% vs Amazon's 12.8% on
₹24.26M of volume. Closing even half that gap recovers roughly **₹590k per quarter**. If the gap
proves structural, the ~30% of volume on Merchant fulfilment is a candidate for migration to FBA.

**4. Instrument Amazon-fulfilled delivery outcomes.** Two-thirds of the business currently ends at
`Shipped` with no recorded outcome. Until FBA returns are ingested, the true return rate is unknown
and channel comparison is invalid. This is the single highest-value data fix.

**5. Stock the middle, price the edges.** M/L/XL/XXL are 62.9% of revenue and should never stock
out; 4XL–6XL are 1.6% of revenue at ~25% higher AOV — keep them as thin, high-margin long tail
rather than cutting them.

**6. Decide on non-apparel deliberately.** Perfume, Wallet, Socks, Shoes and Watch are 1.9% of
revenue combined. Either commit inventory and merchandising to make them a real line, or drop them
and reclaim the working capital — the current position earns neither.

**7. Defend the top 5 states, then investigate the decline.** 56% of revenue in five states means
a fulfilment or delivery problem in one metro is a material revenue event. Separately, the 16%
per-day revenue decline from April to June is the most important open question in this dataset and
**cannot be answered from this file** — it needs traffic, ad-spend, pricing and competitor data.

---

## Limitations

1. **No customer identifier** — no retention, repeat-rate, cohort or lifetime-value analysis is
   possible. Order-level segmentation is the honest substitute.
2. **91 days, one quarter** — a trend, never a seasonal claim.
3. **Asymmetric outcome tracking** between fulfilment channels (see §3) — the true return rate for
   69% of the business is unknown.
4. **`Amount` is missing on 7,800 rows** (6.0%), overwhelmingly cancellations; those rows are
   excluded from value totals but counted in order counts.
5. **No cost or margin data** — every figure here is revenue, so "T-shirt is the margin engine"
   means highest AOV, not verified contribution margin.
