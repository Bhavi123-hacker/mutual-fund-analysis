-- ═══════════════════════════════════════════════════════════════════════
--  schema.sql
--  Mutual Fund Analysis — SQLite Star Schema
--  Day 2, Task 4
--
--  Grain summary
--  -------------
--  dim_fund          : one row per AMFI scheme code (amfi_code)
--  dim_date          : one row per calendar day
--  fact_nav          : one row per (fund, day) - daily NAV
--  fact_transactions : one row per investor transaction
--  fact_performance  : one row per (fund, as_of_date) - return snapshot
--  fact_aum          : one row per (fund_house, date) - AUM by AMC
-- ═══════════════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_fund;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_fund (
    fund_key            INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code            INTEGER NOT NULL UNIQUE,
    scheme_name           TEXT    NOT NULL,
    fund_house            TEXT    NOT NULL,
    category               TEXT,
    sub_category           TEXT,
    plan                   TEXT,
    benchmark              TEXT,
    fund_manager           TEXT,
    risk_category          TEXT,
    sebi_category_code     TEXT,
    launch_date            DATE,
    min_sip_amount         REAL,
    min_lumpsum_amount     REAL,
    expense_ratio_pct      REAL,
    exit_load_pct          REAL
);

CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,
    full_date     DATE    NOT NULL UNIQUE,
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    month_name    TEXT    NOT NULL,
    day           INTEGER NOT NULL,
    day_of_week   TEXT    NOT NULL,
    is_weekend    INTEGER NOT NULL,
    is_month_end  INTEGER NOT NULL
);

CREATE TABLE fact_nav (
    nav_key      INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_key     INTEGER NOT NULL,
    date_key     INTEGER NOT NULL,
    nav          REAL    NOT NULL CHECK (nav > 0),
    is_filled    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (fund_key) REFERENCES dim_fund(fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    UNIQUE (fund_key, date_key)
);

CREATE TABLE fact_transactions (
    transaction_key   INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id    TEXT    NOT NULL UNIQUE,
    fund_key          INTEGER NOT NULL,
    date_key          INTEGER NOT NULL,
    investor_id       TEXT,
    transaction_type  TEXT    NOT NULL CHECK (transaction_type IN ('SIP','Lumpsum','Redemption')),
    amount            REAL    NOT NULL CHECK (amount > 0),
    state             TEXT,
    city              TEXT,
    city_tier         TEXT,
    age_group         TEXT,
    gender            TEXT,
    annual_income_lakh REAL,
    payment_mode      TEXT,
    kyc_status        TEXT    CHECK (kyc_status IN ('Verified','Pending','Rejected')),
    FOREIGN KEY (fund_key) REFERENCES dim_fund(fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key)
);

CREATE TABLE fact_performance (
    performance_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_key            INTEGER NOT NULL,
    date_key             INTEGER NOT NULL,
    return_1yr_pct        REAL,
    return_3yr_pct        REAL,
    return_5yr_pct        REAL,
    benchmark_3yr_pct     REAL,
    alpha                 REAL,
    beta                  REAL,
    sharpe_ratio          REAL,
    sortino_ratio         REAL,
    std_dev_ann_pct       REAL,
    max_drawdown_pct      REAL,
    aum_crore             REAL,
    expense_ratio_pct     REAL,
    morningstar_rating    INTEGER,
    risk_grade            TEXT,
    is_outlier            INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (fund_key) REFERENCES dim_fund(fund_key),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    UNIQUE (fund_key, date_key)
);

CREATE TABLE fact_aum (
    aum_key        INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_house     TEXT    NOT NULL,
    date_key       INTEGER NOT NULL,
    aum_crore      REAL    NOT NULL CHECK (aum_crore >= 0),
    num_schemes    INTEGER,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    UNIQUE (fund_house, date_key)
);

CREATE INDEX idx_fact_nav_fund        ON fact_nav(fund_key);
CREATE INDEX idx_fact_nav_date        ON fact_nav(date_key);
CREATE INDEX idx_fact_txn_fund        ON fact_transactions(fund_key);
CREATE INDEX idx_fact_txn_date        ON fact_transactions(date_key);
CREATE INDEX idx_fact_txn_type        ON fact_transactions(transaction_type);
CREATE INDEX idx_fact_txn_state       ON fact_transactions(state);
CREATE INDEX idx_fact_perf_fund       ON fact_performance(fund_key);
CREATE INDEX idx_fact_aum_house       ON fact_aum(fund_house);
