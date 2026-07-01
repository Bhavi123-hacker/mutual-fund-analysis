# Data Dictionary — Bluestock Mutual Fund Analysis
**Day 2 | Database:** `bluestock_mf.db` (SQLite, star schema)
**Source files:** `data/raw/*.xlsx` → cleaned in `data/processed/*.xlsx` → loaded via `load_to_sqlite.py`

---

## Schema Overview (Star Schema)

```
          dim_date
              │
dim_fund ─────┼──── fact_nav
              ├──── fact_transactions
              ├──── fact_performance
              └──── fact_aum  (fund_house degenerate dim)
```

---

## 1. dim_fund
**Grain:** One row per AMFI scheme code (each Direct/Regular plan gets its own code)
**Source:** `01_fund_master_clean.xlsx`

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `fund_key` | INTEGER PK | No | Auto-generated surrogate key |
| `amfi_code` | INTEGER UNIQUE | No | AMFI scheme registration code — the canonical fund identifier across all sources |
| `scheme_name` | TEXT | No | Full official scheme name as registered with SEBI |
| `fund_house` | TEXT | No | Asset Management Company (AMC) name |
| `category` | TEXT | Yes | Broad SEBI category: `Equity`, `Debt`, `Hybrid` |
| `sub_category` | TEXT | Yes | SEBI sub-category: `Large Cap`, `Mid Cap`, `Small Cap`, `Gilt`, `Liquid`, etc. |
| `plan` | TEXT | Yes | `Direct` (investor buys directly, lower TER) or `Regular` (via distributor, higher TER) |
| `benchmark` | TEXT | Yes | Index the fund tracks for performance comparison (e.g. `NIFTY 100 TRI`) |
| `fund_manager` | TEXT | Yes | Name of the lead portfolio manager |
| `risk_category` | TEXT | Yes | Risk label: `Low`, `Moderate`, `High`, `Very High` |
| `sebi_category_code` | TEXT | Yes | SEBI internal code (e.g. `EC01` = Equity Large Cap) |
| `launch_date` | DATE | Yes | Scheme inception date |
| `min_sip_amount` | REAL | Yes | Minimum SIP instalment (INR) |
| `min_lumpsum_amount` | REAL | Yes | Minimum one-time investment (INR) |
| `expense_ratio_pct` | REAL | Yes | Total Expense Ratio — annual fee charged as % of AUM |
| `exit_load_pct` | REAL | Yes | Exit load % charged on early redemption (typically 1% if redeemed within 1 year) |

---

## 2. dim_date
**Grain:** One row per calendar day (covers all dates referenced in fact tables)
**Source:** Auto-generated in `load_to_sqlite.py` — not sourced from any Excel file

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `date_key` | INTEGER PK | No | Surrogate date key in `YYYYMMDD` format (e.g. 20260630) — used as FK in all fact tables |
| `full_date` | DATE UNIQUE | No | ISO calendar date (`YYYY-MM-DD`) |
| `year` | INTEGER | No | Calendar year |
| `quarter` | INTEGER | No | Quarter: 1–4 |
| `month` | INTEGER | No | Month number: 1–12 |
| `month_name` | TEXT | No | Full month name (e.g. `January`) |
| `day` | INTEGER | No | Day of month: 1–31 |
| `day_of_week` | TEXT | No | Full weekday name (e.g. `Monday`) |
| `is_weekend` | INTEGER | No | `1` if Saturday or Sunday; `0` otherwise |
| `is_month_end` | INTEGER | No | `1` if last calendar day of the month; `0` otherwise |

---

## 3. fact_nav
**Grain:** One row per (fund, calendar day) — the daily NAV of each scheme
**Source:** `02_nav_history_clean.xlsx` | **Rows:** 64,320

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `nav_key` | INTEGER PK | No | Auto-generated surrogate key |
| `fund_key` | INTEGER FK | No | → `dim_fund.fund_key` |
| `date_key` | INTEGER FK | No | → `dim_date.date_key` |
| `nav` | REAL | No | Net Asset Value (INR per unit). Validated `> 0`. Constraint: CHECK (nav > 0) |
| `is_filled` | INTEGER | No | `1` = value was forward-filled (holiday / weekend gap, or repaired invalid NAV); `0` = original AMFI-published value |

**Cleaning applied:**
- Mixed date formats (`YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`) → parsed to `datetime64`
- Sorted by `amfi_code` + `date` after parsing
- 62 duplicate `(amfi_code, date)` rows removed (kept first occurrence)
- 23 records with `nav <= 0` → set to `NaN`, repaired by forward-fill
- Calendar expanded per fund so weekend/holiday gaps are forward-filled (`is_filled = 1`)

---

## 4. fact_transactions
**Grain:** One row per investor transaction
**Source:** `08_investor_transactions_clean.xlsx` | **Rows:** 32,778

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `transaction_key` | INTEGER PK | No | Auto-generated surrogate key |
| `transaction_id` | TEXT UNIQUE | No | Unique transaction reference (e.g. `TXN100000`) |
| `fund_key` | INTEGER FK | No | → `dim_fund.fund_key` |
| `date_key` | INTEGER FK | No | → `dim_date.date_key` |
| `investor_id` | TEXT | Yes | Anonymised investor identifier |
| `transaction_type` | TEXT | No | Standardised to one of: `SIP` / `Lumpsum` / `Redemption`. CHECK constraint enforced |
| `amount` | REAL | No | Transaction amount in INR. Validated `> 0` |
| `state` | TEXT | Yes | Investor's Indian state |
| `city` | TEXT | Yes | Investor's city |
| `city_tier` | TEXT | Yes | City classification: `T30` (top 30 cities) or `B30` (beyond top 30) |
| `age_group` | TEXT | Yes | Investor age bracket: `18-25`, `26-35`, `36-45`, `46-55`, `56+` |
| `gender` | TEXT | Yes | `Male` / `Female` / `Other` |
| `annual_income_lakh` | REAL | Yes | Investor's declared annual income (INR lakh) |
| `payment_mode` | TEXT | Yes | Payment method: `UPI`, `NEFT`, `Cheque`, `Auto-debit`, etc. |
| `kyc_status` | TEXT | Yes | KYC verification status: `Verified` / `Pending` / `Rejected`. CHECK constraint enforced |

**Cleaning applied:**
- `transaction_type` standardised via case/whitespace-insensitive map → unmappable values (`STP`, `Switch`, `??`) dropped and logged
- `amount <= 0` rows dropped
- Mixed date formats parsed; unparseable dates dropped
- `kyc_status` mapped to 3-value enum; ambiguous codes (`Y`, `N`) dropped for compliance review (not guessed)

---

## 5. fact_performance
**Grain:** One row per (fund, as-of-date) performance snapshot
**Source:** `07_scheme_performance_clean.xlsx` | **Rows:** 40 (as of 2026-06-30)

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `performance_key` | INTEGER PK | No | Auto-generated surrogate key |
| `fund_key` | INTEGER FK | No | → `dim_fund.fund_key` |
| `date_key` | INTEGER FK | No | → `dim_date.date_key` (snapshot date) |
| `return_1yr_pct` | REAL | Yes | Trailing 1-year point-to-point return (%) |
| `return_3yr_pct` | REAL | Yes | Trailing 3-year CAGR (%) |
| `return_5yr_pct` | REAL | Yes | Trailing 5-year CAGR (%) |
| `benchmark_3yr_pct` | REAL | Yes | Benchmark index 3-year CAGR (%) — for alpha calculation |
| `alpha` | REAL | Yes | Jensen's Alpha = fund 3yr CAGR − benchmark 3yr CAGR |
| `beta` | REAL | Yes | Beta coefficient — fund's sensitivity to benchmark movements (1.0 = market-neutral) |
| `sharpe_ratio` | REAL | Yes | Sharpe Ratio = (fund return − risk-free rate) / std deviation |
| `sortino_ratio` | REAL | Yes | Sortino Ratio = (fund return − risk-free rate) / downside deviation (only negative volatility penalised) |
| `std_dev_ann_pct` | REAL | Yes | Annualised standard deviation of daily returns (%) — measures total volatility |
| `max_drawdown_pct` | REAL | Yes | Maximum peak-to-trough decline (%, negative) — worst historical loss from a peak |
| `aum_crore` | REAL | Yes | Assets Under Management at snapshot date (INR crore) |
| `expense_ratio_pct` | REAL | Yes | TER at snapshot date (%). Nulled if outside SEBI band 0.1–2.5% |
| `morningstar_rating` | INTEGER | Yes | Morningstar star rating 1–5 (5 = best) |
| `risk_grade` | TEXT | Yes | Risk label: `Low` / `Moderate` / `High` / `Very High` |
| `is_outlier` | INTEGER | No | `1` if any return column was flagged by IQR-based outlier detection (k=3); `0` otherwise |

**Cleaning applied:**
- All return columns coerced to numeric — non-numeric placeholders (`NA`, `-`, `N/A`) → `NaN`
- IQR outlier detection (k=3) run per return column — flagged in `is_outlier`, rows **not** dropped
- `expense_ratio_pct` outside SEBI band [0.1%, 2.5%] → value nulled (row retained)

---

## 6. fact_aum
**Grain:** One row per (fund house, month-end date) — industry-level AUM snapshot
**Source:** `03_aum_by_fund_house_clean.xlsx` | **Rows:** 90

| Column | SQLite Type | Nullable | Business Definition |
|--------|------------|----------|---------------------|
| `aum_key` | INTEGER PK | No | Auto-generated surrogate key |
| `fund_house` | TEXT | No | AMC name — degenerate dimension (fund-house grain; not linked to dim_fund scheme grain) |
| `date_key` | INTEGER FK | No | → `dim_date.date_key` (month-end date of the snapshot) |
| `aum_crore` | REAL | No | Total AUM for the AMC on that date (INR crore). CHECK ≥ 0 |
| `num_schemes` | INTEGER | Yes | Number of active schemes operated by the AMC on that date |

---

## Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| `idx_fact_nav_fund` | `fact_nav` | `fund_key` | Fast fund-level NAV lookups |
| `idx_fact_nav_date` | `fact_nav` | `date_key` | Fast date-range NAV scans |
| `idx_fact_txn_fund` | `fact_transactions` | `fund_key` | Fund-level transaction aggregation |
| `idx_fact_txn_date` | `fact_transactions` | `date_key` | Date-range transaction filters |
| `idx_fact_txn_type` | `fact_transactions` | `transaction_type` | SIP / Lumpsum / Redemption split queries |
| `idx_fact_txn_state` | `fact_transactions` | `state` | Geographic distribution queries |
| `idx_fact_perf_fund` | `fact_performance` | `fund_key` | Fund-performance joins |
| `idx_fact_aum_house` | `fact_aum` | `fund_house` | AMC-level AUM trend queries |

---

## Cleaning Rules Summary

| Dataset | Key Cleaning Actions |
|---------|----------------------|
| `02_nav_history` | Date parsing (3 formats), sort by fund+date, 62 dupes removed, 23 invalid NAVs forward-filled, weekend/holiday gaps forward-filled (`is_filled` flag) |
| `08_investor_transactions` | `transaction_type` enum standardisation (case/whitespace map), amount > 0 validation, date parsing, `kyc_status` enum validation (ambiguous codes dropped) |
| `07_scheme_performance` | Return columns coerced to numeric, IQR outlier flagging (k=3), expense_ratio_pct SEBI-band enforcement (0.1–2.5%) |
| `01, 03, 04, 05, 06, 09, 10` | Date parsing, exact duplicate row removal, negative financial value flagging |

---

## Row Count Verification

| Table | Raw Source | Cleaned | Loaded to DB |
|-------|-----------|---------|-------------|
| `dim_fund` | 40 | 40 | 40 |
| `dim_date` | *(generated)* | *(generated)* | 1,640 |
| `fact_nav` | ~66,000 | 64,320 | 64,320 |
| `fact_transactions` | ~33,000 | 32,778 | 32,778 |
| `fact_performance` | 40 | 40 | 40 |
| `fact_aum` | 90 | 90 | 90 |

---

## Source File Reference

| # | Excel File | Cleaned As | Tables Fed |
|---|-----------|-----------|------------|
| 01 | `01_fund_master.xlsx` | `01_fund_master_clean.xlsx` | `dim_fund` |
| 02 | `02_nav_history.xlsx` | `02_nav_history_clean.xlsx` | `fact_nav` |
| 03 | `03_aum_by_fund_house.xlsx` | `03_aum_by_fund_house_clean.xlsx` | `fact_aum` |
| 04 | `04_monthly_sip_inflows.xlsx` | `04_monthly_sip_inflows_clean.xlsx` | *(reporting only)* |
| 05 | `05_category_inflows.xlsx` | `05_category_inflows_clean.xlsx` | *(reporting only)* |
| 06 | `06_industry_folio_count.xlsx` | `06_industry_folio_count_clean.xlsx` | *(reporting only)* |
| 07 | `07_scheme_performance.xlsx` | `07_scheme_performance_clean.xlsx` | `fact_performance` |
| 08 | `08_investor_transactions.xlsx` | `08_investor_transactions_clean.xlsx` | `fact_transactions` |
| 09 | `09_portfolio_holdings.xlsx` | `09_portfolio_holdings_clean.xlsx` | *(reporting only)* |
| 10 | `10_benchmark_indices.xlsx` | `10_benchmark_indices_clean.xlsx` | *(reporting only)* |
