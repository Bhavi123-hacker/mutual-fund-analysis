"""
data_cleaning.py
─────────────────────────────────────────────────────────────────────────────
Day 2 · Mutual Fund Analysis Pipeline — Cleaning Stage (EXCEL I/O)

Inputs  : data/raw/*.xlsx        (10 source workbooks)
Outputs : data/processed/*.xlsx  (10 cleaned workbooks)
          data/processed/day2_cleaning_log.txt
─────────────────────────────────────────────────────────────────────────────
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="Could not infer format")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                     datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)

BASE     = Path(__file__).parent
RAW_DIR  = BASE / "data" / "raw"
PROC_DIR = BASE / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

REPORT_LINES: list[str] = []


def log_section(title: str) -> None:
    line = f"\n{'═'*68}\n  {title}\n{'═'*68}"
    print(line)
    REPORT_LINES.append(line)


def log_line(msg: str) -> None:
    print(msg)
    REPORT_LINES.append(msg)


def read_xlsx(name: str) -> pd.DataFrame:
    return pd.read_excel(RAW_DIR / f"{name}.xlsx")


def write_xlsx(df: pd.DataFrame, name: str) -> Path:
    out_path = PROC_DIR / f"{name}_clean.xlsx"
    df.to_excel(out_path, index=False)
    return out_path


def safe_sorted_uniques(series: pd.Series) -> list:
    return sorted(series.dropna().astype(str).unique().tolist()) + \
           (["<NaN/blank>"] if series.isna().any() else [])


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """Parse YYYY-MM-DD / DD-MM-YYYY / DD/MM/YYYY mixed columns. Excel
    often already gives datetime64 — pass those straight through."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    s = series.astype(str).str.strip()
    parsed = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")

    remaining = parsed.isna() & s.ne("") & s.ne("nan")
    if remaining.any():
        attempt2 = pd.to_datetime(s[remaining], format="%d-%m-%Y", errors="coerce")
        parsed.loc[remaining] = attempt2

    remaining = parsed.isna() & s.ne("") & s.ne("nan")
    if remaining.any():
        attempt3 = pd.to_datetime(s[remaining], format="%d/%m/%Y", errors="coerce")
        parsed.loc[remaining] = attempt3

    remaining = parsed.isna() & s.ne("") & s.ne("nan")
    if remaining.any():
        attempt4 = pd.to_datetime(s[remaining], errors="coerce")
        parsed.loc[remaining] = attempt4

    return parsed


# ─────────────────────────────────────────────────────────────────────────
# TASK 1 — Clean 02_nav_history
# ─────────────────────────────────────────────────────────────────────────
def clean_nav_history() -> pd.DataFrame:
    log_section("TASK 1 — CLEANING 02_nav_history.xlsx")
    df = read_xlsx("02_nav_history")
    raw_rows = len(df)
    log_line(f"  Raw rows loaded            : {raw_rows:,}")

    df["date"] = parse_mixed_dates(df["date"])
    bad_dates = df["date"].isna().sum()
    if bad_dates:
        log_line(f"  ⚠ Unparseable dates dropped: {bad_dates:,}")
        df = df.dropna(subset=["date"])

    bad_nav = (df["nav"] <= 0).sum()
    df.loc[df["nav"] <= 0, "nav"] = np.nan
    log_line(f"  ⚠ Invalid NAV (<=0) flagged : {bad_nav:,}  → set to NaN for ffill")

    df = df.sort_values(["amfi_code", "date"])
    dup_mask = df.duplicated(subset=["amfi_code", "date"], keep="first")
    n_dupes = dup_mask.sum()
    df = df[~dup_mask]
    log_line(f"  ⚠ Duplicate (code,date) rows removed: {n_dupes:,}")

    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)
    log_line(f"  ✓ Sorted by amfi_code + date")

    filled_frames = []
    total_added = 0
    for code, grp in df.groupby("amfi_code"):
        grp = grp.set_index("date").sort_index()
        full_range = pd.date_range(grp.index.min(), grp.index.max(), freq="D")
        reindexed = grp.reindex(full_range)
        reindexed["amfi_code"] = code
        reindexed["is_filled"] = reindexed["nav"].isna().astype(int)
        reindexed["nav"] = reindexed["nav"].ffill()
        total_added += (len(reindexed) - len(grp))
        filled_frames.append(reindexed.reset_index().rename(columns={"index": "date"}))

    clean = pd.concat(filled_frames, ignore_index=True)
    clean = clean.dropna(subset=["nav"])
    clean = clean[["amfi_code", "date", "nav", "is_filled"]]
    clean = clean.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    log_line(f"  ✓ Forward-filled rows added (weekends/holidays): {total_added:,}")
    log_line(f"  ✓ Final validation — NAV > 0 everywhere: {(clean['nav'] > 0).all()}")

    out_path = write_xlsx(clean, "02_nav_history")
    log_line(f"\n  Raw rows   → {raw_rows:,}")
    log_line(f"  Clean rows → {len(clean):,}  (dedup -{n_dupes:,}, bad-date -{bad_dates:,}, ffill +{total_added:,})")
    log_line(f"  Saved → {out_path}")
    return clean


# ─────────────────────────────────────────────────────────────────────────
# TASK 2 — Clean 08_investor_transactions
# ─────────────────────────────────────────────────────────────────────────
TXN_TYPE_MAP = {
    "sip": "SIP",
    "lumpsum": "Lumpsum", "lump sum": "Lumpsum",
    "redemption": "Redemption", "redeem": "Redemption",
}
KYC_MAP = {
    "verified": "Verified",
    "pending": "Pending",
    "rejected": "Rejected",
}


def clean_investor_transactions() -> pd.DataFrame:
    log_section("TASK 2 — CLEANING 08_investor_transactions.xlsx")
    df = read_xlsx("08_investor_transactions")
    raw_rows = len(df)
    log_line(f"  Raw rows loaded            : {raw_rows:,}")

    norm = df["transaction_type"].astype(str).str.strip().str.lower()
    mapped = norm.map(TXN_TYPE_MAP)
    unmapped_type = mapped.isna().sum()
    log_line(f"  ⚠ Unmappable transaction_type values dropped: {unmapped_type:,}"
              f"  {safe_sorted_uniques(df.loc[mapped.isna(),'transaction_type'])}")
    df["transaction_type"] = mapped
    df = df.dropna(subset=["transaction_type"])

    bad_amt = (df["amount_inr"] <= 0).sum()
    df = df[df["amount_inr"] > 0]
    log_line(f"  ⚠ Rows dropped — amount <= 0: {bad_amt:,}")

    df["transaction_date"] = parse_mixed_dates(df["transaction_date"])
    bad_dates = df["transaction_date"].isna().sum()
    df = df.dropna(subset=["transaction_date"])
    log_line(f"  ⚠ Rows dropped — unparseable date: {bad_dates:,}")

    kyc_norm = df["kyc_status"].astype(str).str.strip().str.lower()
    kyc_mapped = kyc_norm.map(KYC_MAP)
    invalid_kyc = kyc_mapped.isna().sum()
    if invalid_kyc:
        bad_vals = safe_sorted_uniques(df.loc[kyc_mapped.isna(), "kyc_status"])
        log_line(f"  ⚠ Invalid kyc_status values flagged & dropped: {invalid_kyc:,}  {bad_vals}")
        log_line(f"     (ambiguous codes like 'Y'/'N' are NOT guessed onto the 3-value"
                  f" enum — flagged for manual compliance review instead)")
    df["kyc_status"] = kyc_mapped
    df = df.dropna(subset=["kyc_status"])

    df = df.rename(columns={"transaction_date": "date", "amount_inr": "amount"})
    df.insert(0, "transaction_id", [f"TXN{100000+i}" for i in range(len(df))])

    df = df.sort_values(["date", "transaction_id"]).reset_index(drop=True)
    out_path = write_xlsx(df, "08_investor_transactions")

    log_line(f"\n  Raw rows   → {raw_rows:,}")
    log_line(f"  Clean rows → {len(df):,}")
    log_line(f"  transaction_type distribution:\n{df['transaction_type'].value_counts().to_string()}")
    log_line(f"  kyc_status distribution:\n{df['kyc_status'].value_counts().to_string()}")
    log_line(f"  Saved → {out_path}")
    return df


# ─────────────────────────────────────────────────────────────────────────
# TASK 3 — Clean 07_scheme_performance
# ─────────────────────────────────────────────────────────────────────────
RETURN_COLS = ["return_1yr_pct", "return_3yr_pct", "return_5yr_pct"]
EXP_RATIO_MIN, EXP_RATIO_MAX = 0.1, 2.5


def flag_outliers_iqr(series: pd.Series, k: float = 3.0) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    lower, upper = q1 - k * iqr, q3 + k * iqr
    return (series < lower) | (series > upper)


def clean_scheme_performance() -> pd.DataFrame:
    log_section("TASK 3 — CLEANING 07_scheme_performance.xlsx")
    df = read_xlsx("07_scheme_performance")
    raw_rows = len(df)
    log_line(f"  Raw rows loaded            : {raw_rows:,}")

    for col in RETURN_COLS:
        before_na = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_na = df[col].isna().sum()
        new_bad = after_na - before_na
        if new_bad > 0:
            log_line(f"  ⚠ '{col}': {new_bad} non-numeric values coerced → NaN")

    df["is_outlier"] = False
    for col in RETURN_COLS:
        mask = flag_outliers_iqr(df[col].dropna())
        flagged_idx = df[col].dropna()[mask].index
        if len(flagged_idx):
            log_line(f"  ⚠ '{col}': {len(flagged_idx)} statistical outlier(s) flagged "
                     f"→ amfi_codes {list(df.loc[flagged_idx,'amfi_code'])}")
            df.loc[flagged_idx, "is_outlier"] = True

    out_of_band = ~df["expense_ratio_pct"].between(EXP_RATIO_MIN, EXP_RATIO_MAX)
    n_bad_exp = out_of_band.sum()
    if n_bad_exp:
        log_line(f"  ⚠ expense_ratio_pct outside SEBI band [{EXP_RATIO_MIN}–{EXP_RATIO_MAX}%]: "
                 f"{n_bad_exp} row(s) → values nulled: "
                 f"{df.loc[out_of_band,'expense_ratio_pct'].tolist()}")
        df.loc[out_of_band, "expense_ratio_pct"] = np.nan

    df["as_of_date"] = pd.Timestamp.today().normalize()

    out_path = write_xlsx(df, "07_scheme_performance")
    log_line(f"\n  Raw rows   → {raw_rows:,}")
    log_line(f"  Clean rows → {len(df):,}  (no rows dropped — invalid cells nulled & flagged, not deleted)")
    log_line(f"  Outlier-flagged rows → {df['is_outlier'].sum()}")
    log_line(f"  Saved → {out_path}")
    return df


# ─────────────────────────────────────────────────────────────────────────
# LIGHT CLEAN — datasets 01, 03, 04, 05, 06, 09, 10
# ─────────────────────────────────────────────────────────────────────────
LIGHT_CLEAN_FILES = [
    "01_fund_master", "03_aum_by_fund_house", "04_monthly_sip_inflows",
    "05_category_inflows", "06_industry_folio_count",
    "09_portfolio_holdings", "10_benchmark_indices",
]
FINANCIAL_COLS = {
    "aum_cr", "aum_crore", "aum_lakh_crore", "sip_inflow_crore", "net_inflow_crore",
    "sip_aum_lakh_crore", "min_sip_amount", "min_lumpsum_amount", "weight_pct",
    "market_value_cr", "close_value", "expense_ratio_pct", "exit_load_pct",
}


def light_clean(name: str) -> pd.DataFrame | None:
    path = RAW_DIR / f"{name}.xlsx"
    if not path.exists():
        log_line(f"  ⚠ {name}.xlsx not found — skipped")
        return None
    df = pd.read_excel(path)
    raw_rows = len(df)

    date_cols = [c for c in df.columns if "date" in c.lower()]
    for dc in date_cols:
        df[dc] = parse_mixed_dates(df[dc])

    dupes = df.duplicated().sum()
    df = df.drop_duplicates()

    neg_flags = []
    for col in df.columns:
        if col in FINANCIAL_COLS and pd.api.types.is_numeric_dtype(df[col]):
            neg = (df[col] < 0).sum()
            if neg:
                neg_flags.append(f"{col}:{neg}")

    out_path = write_xlsx(df, name)
    flag_str = f"  ⚠ negative values: {', '.join(neg_flags)}" if neg_flags else ""
    log_line(f"  {name:<28} {raw_rows:>6,} → {len(df):>6,} rows"
              f"  (dupes removed: {dupes}){flag_str}")
    return df


def light_clean_all():
    log_section("LIGHT CLEAN — datasets 01, 03, 04, 05, 06, 09, 10")
    log_line("  (standard pass: date parsing, dedup, negative-value flagging)\n")
    for name in LIGHT_CLEAN_FILES:
        light_clean(name)


# ─────────────────────────────────────────────────────────────────────────
def main():
    print("═" * 68)
    print("  DAY 2 — DATA CLEANING PIPELINE (Excel I/O)")
    print(f"  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 68)

    nav_clean  = clean_nav_history()
    txn_clean  = clean_investor_transactions()
    perf_clean = clean_scheme_performance()
    light_clean_all()

    log_section("SUMMARY")
    log_line(f"  02_nav_history_clean.xlsx          : {nav_clean.shape}")
    log_line(f"  08_investor_transactions_clean.xlsx: {txn_clean.shape}")
    log_line(f"  07_scheme_performance_clean.xlsx   : {perf_clean.shape}")
    log_line(f"  + 7 lightly-cleaned passthrough datasets (see above)")
    log_line(f"  = 10 / 10 cleaned XLSX files in data/processed/")

    report_path = PROC_DIR / "day2_cleaning_log.txt"
    report_path.write_text("\n".join(REPORT_LINES), encoding="utf-8")
    print(f"\n✅ Full cleaning log written → {report_path}")


if __name__ == "__main__":
    main()