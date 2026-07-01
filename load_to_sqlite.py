"""
load_to_sqlite.py
─────────────────────────────────────────────────────────────────────────────
Day 2 · Task 5 — Load all cleaned EXCEL datasets into SQLite (star schema)
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

BASE     = Path(__file__).parent
RAW_DIR  = BASE / "data" / "raw"
PROC_DIR = BASE / "data" / "processed"
DB_PATH  = BASE / "bluestock_mf.db"
SCHEMA   = BASE / "sql" / "schema.sql"

engine = create_engine(f"sqlite:///{DB_PATH}")


def build_schema():
    # Added encoding="utf-8" to fix Windows charmap UnicodeDecodeError
    ddl = SCHEMA.read_text(encoding="utf-8")
    raw_conn = engine.raw_connection()
    try:
        raw_conn.executescript(ddl)
        raw_conn.commit()
    finally:
        raw_conn.close()
    log.info("Schema built from %s", SCHEMA)


def date_key(d) -> int:
    return int(pd.Timestamp(d).strftime("%Y%m%d"))


def build_dim_date(all_dates: pd.Series):
    lo, hi = all_dates.min(), all_dates.max()
    cal = pd.DataFrame({"full_date": pd.date_range(lo, hi, freq="D")})
    cal["date_key"]     = cal["full_date"].apply(date_key)
    cal["year"]         = cal["full_date"].dt.year
    cal["quarter"]      = cal["full_date"].dt.quarter
    cal["month"]        = cal["full_date"].dt.month
    cal["month_name"]   = cal["full_date"].dt.month_name()
    cal["day"]          = cal["full_date"].dt.day
    cal["day_of_week"]  = cal["full_date"].dt.day_name()
    cal["is_weekend"]   = cal["full_date"].dt.dayofweek.isin([5, 6]).astype(int)
    cal["is_month_end"] = cal["full_date"].dt.is_month_end.astype(int)
    cal["full_date"]    = cal["full_date"].dt.strftime("%Y-%m-%d")
    cal.to_sql("dim_date", engine, if_exists="append", index=False)
    log.info("dim_date loaded — %d days (%s → %s)", len(cal), lo.date(), hi.date())
    return cal


def load_dim_fund() -> pd.DataFrame:
    df = pd.read_excel(PROC_DIR / "01_fund_master_clean.xlsx")
    before = len(df)
    df = df.drop_duplicates(subset=["amfi_code"])
    out = df[["amfi_code", "scheme_name", "fund_house", "category", "sub_category",
              "plan", "benchmark", "fund_manager", "risk_category", "sebi_category_code",
              "launch_date", "min_sip_amount", "min_lumpsum_amount",
              "expense_ratio_pct", "exit_load_pct"]].copy()
    out.to_sql("dim_fund", engine, if_exists="append", index=False)
    log.info("dim_fund loaded — %d / %d rows (dupes on amfi_code dropped: %d)",
              len(out), before, before - len(out))
    return out


def fund_key_lookup() -> dict:
    return dict(pd.read_sql("SELECT amfi_code, fund_key FROM dim_fund", engine).values.tolist())


def load_fact_nav(fk_map: dict):
    df = pd.read_excel(PROC_DIR / "02_nav_history_clean.xlsx")
    df["date"] = pd.to_datetime(df["date"])
    raw_len = len(df)
    df["fund_key"] = df["amfi_code"].map(fk_map)
    orphans = df["fund_key"].isna().sum()
    df = df.dropna(subset=["fund_key"])
    df["fund_key"] = df["fund_key"].astype(int)
    df["date_key"] = df["date"].apply(date_key)
    out = df[["fund_key", "date_key", "nav", "is_filled"]]
    out.to_sql("fact_nav", engine, if_exists="append", index=False)
    log.info("fact_nav loaded — %d / %d rows (orphan amfi_code: %d)", len(out), raw_len, orphans)
    return out, raw_len


def load_fact_transactions(fk_map: dict):
    df = pd.read_excel(PROC_DIR / "08_investor_transactions_clean.xlsx")
    df["date"] = pd.to_datetime(df["date"])
    raw_len = len(df)
    df["fund_key"] = df["amfi_code"].map(fk_map)
    orphans = df["fund_key"].isna().sum()
    df = df.dropna(subset=["fund_key"])
    df["fund_key"] = df["fund_key"].astype(int)
    df["date_key"] = df["date"].apply(date_key)
    out = df[["transaction_id", "fund_key", "date_key", "investor_id", "transaction_type",
              "amount", "state", "city", "city_tier", "age_group", "gender",
              "annual_income_lakh", "payment_mode", "kyc_status"]]
    out.to_sql("fact_transactions", engine, if_exists="append", index=False)
    log.info("fact_transactions loaded — %d / %d rows (orphan amfi_code: %d)", len(out), raw_len, orphans)
    return out, raw_len


def load_fact_performance(fk_map: dict):
    df = pd.read_excel(PROC_DIR / "07_scheme_performance_clean.xlsx")
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    raw_len = len(df)
    df["fund_key"] = df["amfi_code"].map(fk_map)
    orphans = df["fund_key"].isna().sum()
    df = df.dropna(subset=["fund_key"])
    df["fund_key"] = df["fund_key"].astype(int)
    df["date_key"] = df["as_of_date"].apply(date_key)
    out = df[["fund_key", "date_key", "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
              "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio", "sortino_ratio",
              "std_dev_ann_pct", "max_drawdown_pct", "aum_crore", "expense_ratio_pct",
              "morningstar_rating", "risk_grade", "is_outlier"]]
    out["is_outlier"] = out["is_outlier"].astype(int)
    out.to_sql("fact_performance", engine, if_exists="append", index=False)
    log.info("fact_performance loaded — %d / %d rows (orphan amfi_code: %d)", len(out), raw_len, orphans)
    return out, raw_len


def load_fact_aum():
    df = pd.read_excel(PROC_DIR / "03_aum_by_fund_house_clean.xlsx")
    df["date"] = pd.to_datetime(df["date"])
    raw_len = len(df)
    df["date_key"] = df["date"].apply(date_key)
    out = df[["fund_house", "date_key", "aum_crore", "num_schemes"]]
    out.to_sql("fact_aum", engine, if_exists="append", index=False)
    log.info("fact_aum loaded — %d / %d rows", len(out), raw_len)
    return out, raw_len


def verify_row_counts(loaded: dict, raw_counts: dict, clean_counts: dict):
    print("\n" + "═" * 80)
    print("  ROW COUNT VERIFICATION — raw XLSX → cleaned XLSX → loaded into SQLite")
    print("═" * 80)
    print(f"  {'Table':<20} {'Raw':>10} {'Cleaned':>12} {'Loaded':>12}  {'Note'}")
    print("  " + "-" * 76)
    for table, n_loaded in loaded.items():
        raw = raw_counts.get(table, "—")
        clean = clean_counts.get(table, "—")
        note = ""
        if isinstance(raw, int) and isinstance(clean, int) and raw != clean:
            note = "cleaning changed row count (see day2_cleaning_log.txt)"
        if isinstance(clean, int) and clean != n_loaded:
            note += (" | " if note else "") + "FK orphans dropped at load"
        print(f"  {table:<20} {raw!s:>10} {clean!s:>12} {n_loaded:>12}  {note}")
    print("═" * 80)


def main():
    print("═" * 68)
    print("  DAY 2 — LOAD CLEANED EXCEL DATA INTO SQLITE (bluestock_mf.db)")
    print(f"  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 68)

    if DB_PATH.exists():
        DB_PATH.unlink()
        log.info("Removed existing %s for a clean rebuild", DB_PATH)

    build_schema()

    raw_counts = {
        "dim_fund":          len(pd.read_excel(RAW_DIR / "01_fund_master.xlsx")),
        "fact_nav":          len(pd.read_excel(RAW_DIR / "02_nav_history.xlsx")),
        "fact_transactions": len(pd.read_excel(RAW_DIR / "08_investor_transactions.xlsx")),
        "fact_performance":  len(pd.read_excel(RAW_DIR / "07_scheme_performance.xlsx")),
        "fact_aum":          len(pd.read_excel(RAW_DIR / "03_aum_by_fund_house.xlsx")),
    }
    clean_counts = {
        "dim_fund":          len(pd.read_excel(PROC_DIR / "01_fund_master_clean.xlsx")),
        "fact_nav":          len(pd.read_excel(PROC_DIR / "02_nav_history_clean.xlsx")),
        "fact_transactions": len(pd.read_excel(PROC_DIR / "08_investor_transactions_clean.xlsx")),
        "fact_performance":  len(pd.read_excel(PROC_DIR / "07_scheme_performance_clean.xlsx")),
        "fact_aum":          len(pd.read_excel(PROC_DIR / "03_aum_by_fund_house_clean.xlsx")),
    }

    dim_fund_df = load_dim_fund()
    fk_map = fund_key_lookup()

    nav_dates = pd.read_excel(PROC_DIR / "02_nav_history_clean.xlsx")["date"]
    txn_dates = pd.read_excel(PROC_DIR / "08_investor_transactions_clean.xlsx")["date"]
    perf_dates = pd.read_excel(PROC_DIR / "07_scheme_performance_clean.xlsx")["as_of_date"]
    aum_dates = pd.read_excel(PROC_DIR / "03_aum_by_fund_house_clean.xlsx")["date"]
    all_dates = pd.to_datetime(pd.concat([nav_dates, txn_dates, perf_dates, aum_dates], ignore_index=True))
    build_dim_date(all_dates)

    _, nav_raw  = load_fact_nav(fk_map)
    _, txn_raw  = load_fact_transactions(fk_map)
    _, perf_raw = load_fact_performance(fk_map)
    _, aum_raw  = load_fact_aum()

    with engine.connect() as conn:
        loaded = {
            "dim_fund":          conn.execute(text("SELECT COUNT(*) FROM dim_fund")).scalar(),
            "fact_nav":          conn.execute(text("SELECT COUNT(*) FROM fact_nav")).scalar(),
            "fact_transactions": conn.execute(text("SELECT COUNT(*) FROM fact_transactions")).scalar(),
            "fact_performance":  conn.execute(text("SELECT COUNT(*) FROM fact_performance")).scalar(),
            "fact_aum":          conn.execute(text("SELECT COUNT(*) FROM fact_aum")).scalar(),
            "dim_date":          conn.execute(text("SELECT COUNT(*) FROM dim_date")).scalar(),
        }

    verify_row_counts({k: v for k, v in loaded.items() if k != "dim_date"}, raw_counts, clean_counts)
    print(f"\n  dim_date (calendar, generated): {loaded['dim_date']:,} days")
    print(f"\n  ✅ {DB_PATH.name} built — {sum(loaded.values()):,} total rows across 6 tables")


if __name__ == "__main__":
    main()