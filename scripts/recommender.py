#!/usr/bin/env python3
"""
recommender.py — Standalone Fund Recommender
─────────────────────────────────────────────
Usage:
    python3 recommender.py --risk Low
    python3 recommender.py --risk Moderate
    python3 recommender.py --risk High
    python3 recommender.py --risk High --top 5
    python3 recommender.py   (interactive mode)

Risk Appetite → Risk Grade Mapping
    Low       → Low
    Moderate  → Moderate, Moderately High
    High      → High, Very High

Ranks funds by Sharpe Ratio (highest = best risk-adjusted return).
Excludes statistical outliers flagged during data cleaning.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


# ─── Paths ────────────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent
PROC      = BASE / "data" / "processed"
PERF_FILE = PROC / "07_scheme_performance_clean.xlsx"
FUND_FILE = PROC / "01_fund_master_clean.xlsx"

# ─── Risk mapping ─────────────────────────────────────────────────────────────
RISK_MAP = {
    "Low"      : ["Low"],
    "Moderate" : ["Moderate", "Moderately High"],
    "High"     : ["High", "Very High"],
}

VALID_PROFILES = list(RISK_MAP.keys())

DIVIDER = "─" * 72


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and return (perf_df, funds_df)."""
    if not PERF_FILE.exists():
        sys.exit(f"ERROR: Cannot find {PERF_FILE}\n"
                 f"       Make sure you run this from the mf_analysis/ root directory.")
    perf  = pd.read_excel(PERF_FILE)
    funds = pd.read_excel(FUND_FILE)
    return perf, funds


def recommend(risk_appetite: str,
              perf_df: pd.DataFrame,
              funds_df: pd.DataFrame,
              top_n: int = 3) -> pd.DataFrame:
    """
    Return top N funds ranked by Sharpe ratio for the given risk appetite.

    Parameters
    ----------
    risk_appetite : str    'Low', 'Moderate', or 'High'
    perf_df       : DataFrame from 07_scheme_performance_clean.xlsx
    funds_df      : DataFrame from 01_fund_master_clean.xlsx
    top_n         : int    Number of results

    Returns
    -------
    DataFrame with recommendations and metrics
    """
    profile = risk_appetite.strip().title()
    if profile not in RISK_MAP:
        raise ValueError(f"risk_appetite must be one of {VALID_PROFILES}. Got: '{risk_appetite}'")

    grades = RISK_MAP[profile]
    subset = (
        perf_df[
            perf_df["risk_grade"].isin(grades) &
            (~perf_df["is_outlier"])
        ]
        .dropna(subset=["sharpe_ratio", "return_3yr_pct"])
        .sort_values("sharpe_ratio", ascending=False)
        .head(top_n)
        .copy()
    )

    if subset.empty:
        return pd.DataFrame(columns=["rank", "scheme_name", "fund_house", "category",
                                     "plan", "risk_grade", "sharpe_ratio",
                                     "return_3yr_pct", "expense_ratio_pct", "aum_crore"])

    subset["rank"] = range(1, len(subset) + 1)

    return subset[[
        "rank", "scheme_name", "fund_house", "category", "plan",
        "risk_grade", "sharpe_ratio", "return_3yr_pct",
        "expense_ratio_pct", "aum_crore",
    ]].reset_index(drop=True)


def print_table(rec_df: pd.DataFrame, risk_appetite: str, grades: list[str]) -> None:
    """Pretty-print recommendation table to stdout."""
    print(f"\n{DIVIDER}")
    print(f"  FUND RECOMMENDATIONS  —  Risk Appetite: {risk_appetite.upper()}")
    print(f"  Risk Grades Matched : {grades}")
    print(DIVIDER)

    if rec_df.empty:
        print("  No matching funds found for the given profile.")
        print(DIVIDER)
        return

    for _, row in rec_df.iterrows():
        print(f"\n  #{int(row['rank'])}.  {row['scheme_name']}")
        print(f"       Fund House       : {row['fund_house']}")
        print(f"       Category         : {row['category']}  [{row['plan']}]")
        print(f"       Risk Grade       : {row['risk_grade']}")
        print(f"       Sharpe Ratio     : {row['sharpe_ratio']:.2f}")
        print(f"       3-Year Return    : {row['return_3yr_pct']:.2f}%")
        print(f"       Expense Ratio    : {row['expense_ratio_pct']:.2f}%")
        print(f"       AUM              : ₹{row['aum_crore']:,.0f} Crore")

    print(f"\n{DIVIDER}")
    print("  💡 Tip: Sharpe Ratio measures return per unit of risk. Higher is better.")
    print("  ⚠  This is not financial advice. Consult a SEBI-registered advisor.")
    print(DIVIDER)


def interactive_mode(perf_df: pd.DataFrame, funds_df: pd.DataFrame) -> None:
    """Run interactive CLI recommender loop."""
    print("\n" + "═" * 72)
    print("  BLUESTOCK — MUTUAL FUND RECOMMENDER  (Interactive Mode)")
    print("═" * 72)
    print(f"  Valid risk profiles: {VALID_PROFILES}")
    print("  Type 'quit' to exit.\n")

    while True:
        try:
            user_input = input("  Enter risk appetite [Low / Moderate / High]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Exiting.")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("  Goodbye.")
            break

        try:
            top_n   = int(input("  Number of funds to recommend [default 3]: ") or 3)
        except (ValueError, EOFError):
            top_n = 3

        try:
            rec = recommend(user_input, perf_df, funds_df, top_n)
            print_table(rec, user_input, RISK_MAP[user_input.title()])
        except ValueError as e:
            print(f"  ✗ {e}")
        except KeyboardInterrupt:
            break


# ─── CLI Entry Point ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Bluestock Mutual Fund Recommender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--risk",
        choices=VALID_PROFILES,
        default=None,
        help="Investor risk appetite: Low, Moderate, or High",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        metavar="N",
        help="Number of fund recommendations to return (default: 3)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Print recommendations for all three risk profiles",
    )
    args = parser.parse_args()

    perf_df, funds_df = load_data()
    print(f"  Loaded {len(perf_df)} schemes from {PERF_FILE.name}")

    if args.all:
        for profile in VALID_PROFILES:
            rec = recommend(profile, perf_df, funds_df, args.top)
            print_table(rec, profile, RISK_MAP[profile])
    elif args.risk:
        rec = recommend(args.risk, perf_df, funds_df, args.top)
        print_table(rec, args.risk, RISK_MAP[args.risk])
    else:
        # No flags → interactive mode
        interactive_mode(perf_df, funds_df)


if __name__ == "__main__":
    main()
