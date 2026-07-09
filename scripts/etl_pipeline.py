"""
data_ingestion.py
─────────────────────────────────────────────────────────────────────────────
Day 1 · Mutual Fund Analysis Pipeline — Bluestock Fintech Datasets
Datasets :
  01_fund_master.xlsx          — Scheme metadata (code, fund_house, category…)
  02_nav_history.xlsx          — Daily NAV time-series per scheme
  03_aum_by_fund_house.xlsx    — AUM aggregated by fund house
  04_monthly_sip_inflows.xlsx  — Monthly SIP inflow data
  05_category_inflows.xlsx     — Inflows by SEBI category
  06_industry_folio_count.xlsx — Folio count by industry/sector
  07_scheme_performance.xlsx   — Returns (1M, 3M, 1Y, 3Y, 5Y) per scheme
  08_investor_transactions.xlsx— Buy/Sell/Switch transaction records
  09_portfolio_holdings.xlsx   — Stock-level holdings per scheme
  10_benchmark_indices.xlsx    — Daily index values (Nifty 50, Sensex…)

Usage  : python data_ingestion.py
Output : data/processed/data_quality_report.txt
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent
RAW_DIR  = BASE / "data" / "raw"
PROC_DIR = BASE / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ── File Manifest  (EXACT filenames from Bluestock Fintech drive) ───────────
FILE_MANIFEST = {
    "01_fund_master":           RAW_DIR / "01_fund_master.xlsx",
    "02_nav_history":           RAW_DIR / "02_nav_history.xlsx",
    "03_aum_by_fund_house":     RAW_DIR / "03_aum_by_fund_house.xlsx",
    "04_monthly_sip_inflows":   RAW_DIR / "04_monthly_sip_inflows.xlsx",
    "05_category_inflows":      RAW_DIR / "05_category_inflows.xlsx",
    "06_industry_folio_count":  RAW_DIR / "06_industry_folio_count.xlsx",
    "07_scheme_performance":    RAW_DIR / "07_scheme_performance.xlsx",
    "08_investor_transactions": RAW_DIR / "08_investor_transactions.xlsx",
    "09_portfolio_holdings":    RAW_DIR / "09_portfolio_holdings.xlsx",
    "10_benchmark_indices":     RAW_DIR / "10_benchmark_indices.xlsx",
}

# ── Expected columns per file (for validation) ─────────────────────────────
EXPECTED_COLS = {
    "01_fund_master": [
        "amfi_code", "fund_house", "scheme_name", "category", "sub_category",
        "plan", "launch_date", "benchmark", "expense_ratio_pct",
        "exit_load_pct", "min_sip_amount", "min_lumpsum_amount",
        "fund_manager", "risk_category", "sebi_category_code"
    ],
    "02_nav_history":          ["scheme_code", "date", "nav"],
    "03_aum_by_fund_house":    ["fund_house", "aum_cr"],
    "04_monthly_sip_inflows":  ["month", "sip_inflow_cr"],
    "05_category_inflows":     ["category", "inflow_cr"],
    "06_industry_folio_count": ["industry", "folio_count"],
    "07_scheme_performance":   ["scheme_code", "return_1m", "return_3m",
                                 "return_1y", "return_3y", "return_5y"],
    "08_investor_transactions":["transaction_id", "scheme_code", "date",
                                 "amount", "transaction_type"],
    "09_portfolio_holdings":   ["scheme_code", "stock_name", "weight_pct"],
    "10_benchmark_indices":    ["date", "index_name", "value"],
}

# ── Helpers ────────────────────────────────────────────────────────────────
def sep(char="═", width=68): return char * width

def load_csv(name, path):
    if not path.exists():
        log.warning("FILE NOT FOUND: %s", path)
        log.warning("  → Download from Google Drive and place in: %s", RAW_DIR)
        return None

    try:
        df = pd.read_excel(path, engine="openpyxl")

        log.info(
            "Loaded %-30s  %d rows × %d cols",
            name,
            df.shape[0],
            df.shape[1]
        )

        return df

    except Exception as e:
        log.error("Failed to read %s: %s", name, e)
        return None

# ── Per-dataset profile ─────────────────────────────────────────────────────
def print_profile(name, df):
    print(f"\n{sep()}")
    print(f"  📄  {name}")
    print(sep())
    print(f"\nShape    : {df.shape[0]:,} rows  ×  {df.shape[1]} columns")

    # dtypes table
    print(f"\n  {'Column':<30} {'Dtype':<14} {'Non-Null %':>10}  {'Sample Value'}")
    print("  " + "─" * 72)
    for col in df.columns:
        dtype    = str(df[col].dtype)
        non_null = 100 * df[col].notna().sum() / len(df)
        sample   = str(df[col].dropna().iloc[0]) if df[col].notna().any() else "—"
        sample   = sample[:30] if len(sample) > 30 else sample
        print(f"  {col:<30} {dtype:<14} {non_null:>9.1f}%  {sample}")

    # head(3)
    print(f"\n--- head(3) ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 120)
    pd.set_option("display.max_colwidth", 20)
    print(df.head(3).to_string(index=False))

    return detect_anomalies(name, df)

# ── Anomaly detection ───────────────────────────────────────────────────────
def detect_anomalies(name, df):
    issues = []

    # 1 — Missing columns
    expected = EXPECTED_COLS.get(name, [])
    missing_cols = [c for c in expected if c not in df.columns]
    if missing_cols:
        issues.append(f"MISSING COLS: {missing_cols}")

    # 2 — Null values
    for col, cnt in df.isnull().sum().items():
        if cnt > 0:
            pct = 100 * cnt / len(df)
            issues.append(f"NULL  '{col}': {cnt:,} missing ({pct:.1f}%)")

    # 3 — Duplicates
    dup = df.duplicated().sum()
    if dup:
        issues.append(f"DUPE  {dup:,} fully duplicate rows")

    # 4 — Negative values in financial columns
    fin_cols = {"nav", "aum_cr", "expense_ratio_pct", "exit_load_pct",
                "amount", "weight_pct", "sip_inflow_cr", "inflow_cr", "value"}
    for col in df.select_dtypes(include=[np.number]).columns:
        if col.lower() in fin_cols:
            neg = (df[col] < 0).sum()
            if neg:
                issues.append(f"NEG   '{col}': {neg:,} negative values")

    # 5 — Date parsing
    date_cols = [c for c in df.columns if "date" in c.lower() or c == "month"]
    for dc in date_cols:
        bad = pd.to_datetime(df[dc], errors="coerce").isnull().sum()
        if bad:
            issues.append(f"DATE  '{dc}': {bad:,} unparseable values")

    # 6 — NAV zero check
    if "nav" in df.columns:
        zeros = (df["nav"] == 0).sum()
        if zeros:
            issues.append(f"NAV   {zeros:,} zero-NAV records")

    # 7 — Portfolio weights sum check
    if name == "09_portfolio_holdings" and "weight_pct" in df.columns:
        if "scheme_code" in df.columns:
            for code, grp in df.groupby("scheme_code"):
                total = grp["weight_pct"].sum()
                if not (90 <= total <= 110):
                    issues.append(f"WGHT  scheme {code}: sum={total:.1f}% (expected ~100)")

    # 8 — Expense ratio sanity (01_fund_master)
    if name == "01_fund_master" and "expense_ratio_pct" in df.columns:
        extreme = (df["expense_ratio_pct"] > 3.0).sum()
        if extreme:
            issues.append(f"EXP   {extreme} expense ratios > 3% (unusually high)")

    if issues:
        print(f"\n  ⚠️  ANOMALIES ({len(issues)}):")
        for iss in issues:
            print(f"    • {iss}")
    else:
        print(f"\n  ✅  No anomalies detected")

    return issues

# ── Task 6: Fund Master Exploration ────────────────────────────────────────
def explore_fund_master(df):
    print(f"\n{sep()}")
    print("  FUND MASTER — DEEP EXPLORATION (Task 6)")
    print(sep())

    # Unique fund houses
    print(f"\n📌  Unique Fund Houses ({df['fund_house'].nunique()}):")
    for fh, grp in df.groupby("fund_house"):
        print(f"   {fh:<30}  {len(grp):>3} schemes")

    # Categories
    print(f"\n📌  Categories × Sub-Categories:")
    for cat, grp in df.groupby("category"):
        subcats = sorted(grp["sub_category"].dropna().unique())
        print(f"   [{cat}]  sub-cats: {', '.join(subcats)}")

    # Risk grades
    print(f"\n📌  Risk Category Distribution:")
    for rc, cnt in df["risk_category"].value_counts().items():
        bar = "█" * int(cnt / max(df["risk_category"].value_counts()) * 20)
        print(f"   {rc:<15}  {cnt:>4}  {bar}")

    # Plans
    print(f"\n📌  Direct vs Regular Plans:")
    print(df["plan"].value_counts().to_string())

    # SEBI category codes
    print(f"\n📌  SEBI Category Codes:")
    for code, cnt in df["sebi_category_code"].value_counts().items():
        print(f"   {code}  →  {cnt} schemes")

    # AMFI code structure dynamically catching column names
    code_col = "amfi_code" if "amfi_code" in df.columns else "code"
    
    if code_col in df.columns:
        codes = sorted(df[code_col].dropna().astype(int).tolist())
        print(f"\n📌  AMFI Scheme Code Structure:")
        print(f"   Format   : 6-digit integer")
        print(f"   Range    : {min(codes):,} → {max(codes):,}")
        print(f"   Count    : {len(codes)} unique scheme codes")
        print(f"   Pattern  : Each plan (Direct/Regular) has a SEPARATE AMFI code")
    else:
        print(f"\n📌  AMFI Scheme Code Structure: Missing required columns")

    # Expense ratio stats
    if "expense_ratio_pct" in df.columns:
        print(f"\n📌  Expense Ratio Stats:")
        er = df.groupby("plan")["expense_ratio_pct"].describe().round(3)
        print(er.to_string())

# ── Task 7: AMFI Code Validation ───────────────────────────────────────────
def validate_amfi_codes(fm, nh):
    if fm is None or nh is None:
        log.warning("Skipping AMFI validation — one or both datasets missing")
        return {}

    nh_code_col = (
        "amfi_code" if "amfi_code" in nh.columns else
        "scheme_code" if "scheme_code" in nh.columns else
        "code" if "code" in nh.columns else
        None
    )
    
    fm_code_col = (
        "amfi_code" if "amfi_code" in fm.columns else
        "code" if "code" in fm.columns else
        "scheme_code" if "scheme_code" in fm.columns else
        None
    )

    if not nh_code_col or not fm_code_col:
        log.warning("Cannot find scheme code columns for validation")
        return {}

    master_codes  = set(fm[fm_code_col].dropna().astype(int).unique())
    history_codes = set(nh[nh_code_col].dropna().astype(int).unique())

    matched               = master_codes & history_codes
    in_master_not_history = master_codes - history_codes
    in_history_not_master = history_codes - master_codes

    print(f"\n{sep()}")
    print("  AMFI CODE VALIDATION (Task 7)")
    print(sep())
    print(f"\n  Schemes in fund_master   : {len(master_codes):>5}")
    print(f"  Schemes in nav_history   : {len(history_codes):>5}")
    print(f"  ─────────────────────────────────")
    print(f"  Matched (both tables)    : {len(matched):>5}  ✅")
    print(f"  In master, no NAV data   : {len(in_master_not_history):>5}  {'⚠️' if in_master_not_history else '✅'}")
    print(f"  NAV exists, no metadata  : {len(in_history_not_master):>5}  {'⚠️' if in_history_not_master else '✅'}")

    if in_master_not_history:
        print(f"\n  ⚠️  {len(in_master_not_history)} schemes in fund_master have no NAV history:")
        for code in sorted(list(in_master_not_history))[:10]:
            row = fm[fm[fm_code_col] == code]
            name = row["scheme_name"].values[0] if len(row) else "—"
            print(f"     [{code}] {name}")
        if len(in_master_not_history) > 10:
            print(f"     … and {len(in_master_not_history)-10} more")
        print(f"\n     Remediation: GET https://api.mfapi.in/mf/<code>")

    if in_history_not_master:
        print(f"\n  ⚠️  {len(in_history_not_master)} NAV codes not in fund_master (orphans):")
        for code in sorted(list(in_history_not_master))[:5]:
            print(f"     [{code}]")

    # NAV date range
    if "date" in nh.columns:
        dates = pd.to_datetime(nh["date"], errors="coerce")
        print(f"\n  NAV history date range   : {dates.min().date()} → {dates.max().date()}")
        print(f"  Total NAV records        : {len(nh):,}")

    coverage = round(100 * len(matched) / len(master_codes), 1) if master_codes else 0
    return {
        "master_count":    len(master_codes),
        "history_count":   len(history_codes),
        "matched":         len(matched),
        "missing_nav":     len(in_master_not_history),
        "orphan_nav":      len(in_history_not_master),
        "coverage_pct":    coverage,
    }

# ── Write Quality Report ────────────────────────────────────────────────────
def write_quality_report(all_anomalies, validation, datasets):
    path = PROC_DIR / "data_quality_report.txt"
    lines = [
        "═" * 68,
        "  MUTUAL FUND DATA PIPELINE — DATA QUALITY REPORT",
        f"  Source   : Bluestock Fintech Google Drive",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "═" * 68,
        "",
        "SECTION 1 — DATASET OVERVIEW",
        "─" * 50,
        f"  {'File':<35} {'Shape':<18} {'Status'}",
        "─" * 50,
    ]
    for name, df in datasets.items():
        if df is not None:
            cnt = len(all_anomalies.get(name, []))
            status = f"✅ Clean" if cnt == 0 else f"⚠️  {cnt} issue(s)"
            lines.append(f"  {name:<35} {str(df.shape):<18} {status}")
        else:
            lines.append(f"  {name:<35} {'FILE MISSING':<18} ❌")
    lines += [
        "",
        "SECTION 2 — ANOMALY DETAILS",
        "─" * 50,
    ]
    for name, issues in all_anomalies.items():
        if issues:
            lines.append(f"\n  {name}:")
            for iss in issues:
                lines.append(f"    └─ {iss}")
    if not any(all_anomalies.values()):
        lines.append("  All datasets clean — no anomalies detected.")

    if validation:
        lines += [
            "",
            "SECTION 3 — AMFI CODE VALIDATION",
            "─" * 50,
            f"  fund_master codes   : {validation.get('master_count','N/A')}",
            f"  nav_history codes   : {validation.get('history_count','N/A')}",
            f"  Coverage            : {validation.get('coverage_pct','N/A')}%",
            f"  Missing NAV backfill: {validation.get('missing_nav','N/A')} schemes",
            f"  Orphan NAV records  : {validation.get('orphan_nav','N/A')}",
        ]
    lines += [
        "",
        "SECTION 4 — DAY 2 ACTION ITEMS",
        "─" * 50,
        "  1. Backfill NAV history for schemes missing from nav_history",
        "  2. Merge fund_master ↔ nav_history on scheme code",
        "  3. Compute 1Y / 3Y / 5Y CAGR for all schemes",
        "  4. Build processed/nav_wide.xlsx (pivot: date × scheme_code)",
        "  5. EDA notebook: rolling returns, Sharpe ratio, drawdown",
        "  6. SQLite schema: schemes, nav, sip, portfolio tables",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Report saved → %s", path)

# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print(sep("═"))
    print("  MUTUAL FUND DATA PIPELINE — DAY 1: DATA INGESTION")
    print(f"  Bluestock Fintech Datasets | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep("═"))

    datasets     = {}
    all_anomalies = {}

    for name, path in FILE_MANIFEST.items():
        df = load_csv(name, path)
        datasets[name] = df
        if df is not None:
            issues = print_profile(name, df)
            all_anomalies[name] = issues

    loaded = sum(1 for v in datasets.values() if v is not None)
    missing = [k for k, v in datasets.items() if v is None]

    if missing:
        print(f"\n{sep('─')}")
        print(f"  ⚠️  {len(missing)} FILE(S) NOT FOUND IN data/raw/:")
        for m in missing:
            print(f"     • {m}.xlsx  →  download from Bluestock Fintech Google Drive")
        print(sep("─"))

    # Task 6
    if datasets.get("01_fund_master") is not None:
        explore_fund_master(datasets["01_fund_master"])

    # Task 7
    validation = validate_amfi_codes(
        datasets.get("01_fund_master"),
        datasets.get("02_nav_history")
    )

    # Write report
    write_quality_report(all_anomalies, validation, datasets)

    # Final summary
    print(f"\n{sep()}")
    print("  FINAL SUMMARY")
    print(sep())
    total_issues = sum(len(v) for v in all_anomalies.values())
    print(f"\n  Datasets loaded    : {loaded} / {len(FILE_MANIFEST)}")
    if missing:
        print(f"  Missing files      : {len(missing)}")
    print(f"  Total anomalies    : {total_issues}")
    if validation:
        print(f"  NAV coverage       : {validation.get('coverage_pct','N/A')}%")
    print(f"  Report written to  : data/processed/data_quality_report.txt")
    print(f"\n{'─'*68}")
    print(f"  ✅  Day 1 data ingestion complete")
    print(f"{'─'*68}\n")


if __name__ == "__main__":
    main()