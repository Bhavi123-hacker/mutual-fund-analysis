"""
B3_monte_carlo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BONUS CHALLENGE 3 — Monte Carlo NAV Simulation (5-Year Projection)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Method  : Geometric Brownian Motion (GBM)
          S_t = S_{t-1} × exp((μ - 0.5σ²)dt + σ√dt × Z)
          where Z ~ N(0,1)
Inputs  : Daily NAV history from bluestock_mf.db (fact_nav table)
Outputs : B3_monte_carlo.png       — 6-panel chart (5 funds + summary)
          B3_monte_carlo_data.csv  — percentile projections per fund

HOW TO RUN:
  pip install pandas numpy matplotlib scipy sqlalchemy
  python B3_monte_carlo.py

  # Change number of simulations or projection years:
  python B3_monte_carlo.py --simulations 5000 --years 10

  # Run for specific fund codes only:
  python B3_monte_carlo.py --codes 119551 125497 120503
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

warnings.filterwarnings("ignore")

# ── Config ────────────────────────────────────────────────────────────────
BASE         = Path(__file__).parent
DB_PATH      = BASE / "bluestock_mf.db"
OUT_PNG      = BASE / "B3_monte_carlo.png"
OUT_CSV      = BASE / "B3_monte_carlo_data.csv"
TRADING_DAYS = 252

# ── Bluestock colour palette ──────────────────────────────────────────────
BG   = "#0F1629"
CARD = "#1A2540"
GRID = "#1E2D4A"
TXT  = "#F1F5F9"
TXT2 = "#94A3B8"
PAL  = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]


# ── Data loading ──────────────────────────────────────────────────────────
def load_nav(db_path: Path, codes: list[int] | None = None) -> pd.DataFrame:
    """Load daily NAV from bluestock_mf.db for selected scheme codes."""
    conn = sqlite3.connect(db_path)
    where = f"AND f.amfi_code IN ({','.join(map(str, codes))})" if codes else ""
    df = pd.read_sql(f"""
        SELECT f.amfi_code, f.scheme_name, d.full_date AS date, n.nav
        FROM fact_nav n
        JOIN dim_fund f ON f.fund_key = n.fund_key
        JOIN dim_date d ON d.date_key = n.date_key
        WHERE n.is_filled = 0 {where}
        ORDER BY f.amfi_code, d.full_date
    """, conn, parse_dates=["date"])
    conn.close()
    return df


def load_top5_equity(db_path: Path) -> list[int]:
    """Return amfi_codes for top 5 equity Direct-plan funds by AUM."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("""
        SELECT f.amfi_code FROM dim_fund f
        JOIN fact_performance p ON p.fund_key = f.fund_key
        WHERE f.category = 'Equity' AND f.plan = 'Direct'
          AND p.is_outlier = 0 AND p.aum_crore IS NOT NULL
        ORDER BY p.aum_crore DESC LIMIT 5
    """, conn)
    conn.close()
    return df["amfi_code"].tolist()


# ── GBM Monte Carlo ────────────────────────────────────────────────────────
def run_monte_carlo(
    nav_series: pd.Series,
    simulations: int,
    years: int,
    seed: int = 42,
) -> dict:
    """
    Run GBM simulation on a single fund NAV series.

    Returns dict with:
        paths        — (steps+1, simulations) array of simulated NAVs
        percentiles  — dict of {5,25,50,75,95} percentile arrays
        mu_annual    — annualised daily mean return
        sigma_annual — annualised daily std deviation
        S0           — starting NAV (last known)
    """
    r       = nav_series.pct_change().dropna()
    mu      = r.mean()
    sigma   = r.std()
    S0      = nav_series.iloc[-1]
    steps   = TRADING_DAYS * years

    np.random.seed(seed)
    Z       = np.random.normal(0, 1, (steps, simulations))
    daily_r = np.exp((mu - 0.5 * sigma ** 2) + sigma * Z)

    paths      = np.zeros((steps + 1, simulations))
    paths[0]   = S0
    for t in range(1, steps + 1):
        paths[t] = paths[t - 1] * daily_r[t - 1]

    pct = {p: np.percentile(paths, p, axis=1)
           for p in [5, 25, 50, 75, 95]}

    return dict(
        paths=paths,
        percentiles=pct,
        mu_annual=mu * TRADING_DAYS,
        sigma_annual=sigma * np.sqrt(TRADING_DAYS),
        S0=S0,
        steps=steps,
    )


# ── Plotting ──────────────────────────────────────────────────────────────
def plot_all(results: dict, years: int, out_path: Path) -> None:
    codes  = list(results.keys())
    n_cols = 3
    n_rows = 2   # 5 fund panels + 1 summary panel

    fig = plt.figure(figsize=(18, 11), facecolor=BG)
    fig.suptitle(
        f"B3 — Monte Carlo NAV Projection  |  {years}-Year Horizon  |  "
        f"{results[codes[0]]['simulations']:,} Simulated Paths per Fund",
        color=TXT, fontsize=13, fontweight="bold", y=0.98,
    )

    axes = []
    for i in range(5):
        row, col = divmod(i, n_cols)
        ax = fig.add_subplot(n_rows, n_cols, i + 1)
        axes.append(ax)
    ax_summary = fig.add_subplot(n_rows, n_cols, 6)

    # Individual fund panels
    for idx, (code, res) in enumerate(list(results.items())[:5]):
        ax    = axes[idx]
        color = PAL[idx]
        pct   = res["percentiles"]
        x     = np.arange(res["steps"] + 1)
        ax.set_facecolor(CARD)

        # Sample paths (faint background)
        sample = min(res["simulations"], 60)
        for i in range(sample):
            ax.plot(x, res["paths"][:, i],
                    color=color, alpha=0.03, linewidth=0.4)

        # Uncertainty bands
        ax.fill_between(x, pct[5],  pct[95], alpha=0.10, color=color)
        ax.fill_between(x, pct[25], pct[75], alpha=0.22, color=color)

        # Median line
        ax.plot(x, pct[50], color=color, linewidth=2.2,
                label=f"Median  ₹{pct[50][-1]:,.0f}")
        ax.plot(x, pct[95], color=color, linewidth=0.8,
                linestyle="--", alpha=0.55)
        ax.plot(x, pct[5],  color=color, linewidth=0.8,
                linestyle="--", alpha=0.55)

        # Starting NAV reference
        ax.axhline(res["S0"], color=TXT2, linewidth=0.7,
                   linestyle=":", alpha=0.5, label=f"Start  ₹{res['S0']:,.0f}")

        # X-axis year labels
        ticks = [TRADING_DAYS * y for y in range(years + 1)]
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"Y{y}" for y in range(years + 1)],
                           color=TXT2, fontsize=8)
        ax.set_title(res["name"][:32], color=TXT, fontsize=9, pad=6)
        ax.set_ylabel("NAV (₹)", color=TXT2, fontsize=8)
        ax.tick_params(colors=TXT2, labelsize=7.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.grid(color=GRID, linewidth=0.4, linestyle="--", alpha=0.5)
        ax.legend(fontsize=7.5, loc="upper left",
                  facecolor=CARD, edgecolor=GRID, labelcolor=TXT)

        # Stats annotation
        cagr = ((pct[50][-1] / res["S0"]) ** (1 / years) - 1) * 100
        ax.annotate(
            f"μ={res['mu_annual']*100:.1f}%/yr  σ={res['sigma_annual']*100:.1f}%  "
            f"CAGR(med)={cagr:.1f}%",
            xy=(0.02, 0.04), xycoords="axes fraction",
            color=TXT2, fontsize=7,
        )

    # Summary panel — median NAV + 90% CI bar chart
    ax_s = ax_summary
    ax_s.set_facecolor(CARD)
    names   = [results[c]["name"][:22] for c in list(results.keys())[:5]]
    medians = [results[c]["percentiles"][50][-1] for c in list(results.keys())[:5]]
    lo      = [results[c]["percentiles"][5][-1]  for c in list(results.keys())[:5]]
    hi      = [results[c]["percentiles"][95][-1] for c in list(results.keys())[:5]]
    err     = [[m - l for m, l in zip(medians, lo)],
               [h - m for m, h in zip(medians, hi)]]

    bars = ax_s.barh(names, medians, color=PAL[:5], alpha=0.85, height=0.52)
    ax_s.errorbar(medians, range(len(names)), xerr=err,
                  fmt="none", color=TXT2, capsize=4, linewidth=1.2)
    for bar, v in zip(bars, medians):
        ax_s.text(v + max(medians) * 0.02,
                  bar.get_y() + bar.get_height() / 2,
                  f"₹{v:,.0f}", va="center", color=TXT, fontsize=8)
    ax_s.set_xlabel(f"Projected NAV after {years} years (₹)", color=TXT2, fontsize=9)
    ax_s.set_title("Median ± 90% confidence range", color=TXT, fontsize=9)
    ax_s.tick_params(colors=TXT2, labelsize=8)
    for sp in ax_s.spines.values():
        sp.set_edgecolor(GRID)
    ax_s.grid(color=GRID, linewidth=0.4, linestyle="--", axis="x", alpha=0.5)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"✅  Chart saved → {out_path}")


# ── CSV export ─────────────────────────────────────────────────────────────
def export_csv(results: dict, years: int, out_path: Path) -> None:
    rows = []
    for code, res in results.items():
        pct  = res["percentiles"]
        cagr = ((pct[50][-1] / res["S0"]) ** (1 / years) - 1) * 100
        rows.append({
            "amfi_code":         code,
            "scheme_name":       res["name"],
            "start_nav":         round(res["S0"], 4),
            "mu_annual_pct":     round(res["mu_annual"] * 100, 4),
            "sigma_annual_pct":  round(res["sigma_annual"] * 100, 4),
            f"p5_{years}yr_nav": round(pct[5][-1], 2),
            f"p25_{years}yr_nav":round(pct[25][-1], 2),
            f"p50_{years}yr_nav":round(pct[50][-1], 2),
            f"p75_{years}yr_nav":round(pct[75][-1], 2),
            f"p95_{years}yr_nav":round(pct[95][-1], 2),
            f"cagr_median_pct":  round(cagr, 3),
            "simulations":       res["simulations"],
            "projection_years":  years,
        })
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"✅  Data CSV saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Monte Carlo NAV simulation for top equity funds"
    )
    parser.add_argument("--simulations", type=int, default=1000,
                        help="Number of GBM paths per fund (default 1000)")
    parser.add_argument("--years",       type=int, default=5,
                        help="Projection horizon in years (default 5)")
    parser.add_argument("--codes",       type=int, nargs="+", default=None,
                        help="AMFI scheme codes to simulate (default: top 5 equity)")
    parser.add_argument("--seed",        type=int, default=42,
                        help="Random seed for reproducibility (default 42)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"bluestock_mf.db not found at {DB_PATH}\n"
            "Place the database in the same folder as this script."
        )

    # Resolve which funds to simulate
    codes = args.codes if args.codes else load_top5_equity(DB_PATH)
    print(f"Schemes   : {codes}")
    print(f"Simulations: {args.simulations:,}  |  Years: {args.years}  |  Seed: {args.seed}")

    # Load NAV
    nav_df   = load_nav(DB_PATH, codes)
    nav_wide = nav_df.pivot(index="date", columns="amfi_code", values="nav").sort_index()
    name_map = (nav_df[["amfi_code", "scheme_name"]]
                .drop_duplicates()
                .set_index("amfi_code")["scheme_name"]
                .to_dict())

    # Run simulations
    results = {}
    for code in codes:
        if code not in nav_wide.columns:
            print(f"  ⚠ code {code} not found in NAV data — skipping")
            continue
        series = nav_wide[code].dropna()
        print(f"  Simulating [{code}] {name_map.get(code,'')[:40]} …", end=" ")
        res = run_monte_carlo(series, args.simulations, args.years, args.seed)
        res["name"]        = name_map.get(code, str(code))
        res["simulations"] = args.simulations
        results[code]      = res

        med_end = res["percentiles"][50][-1]
        cagr    = ((med_end / res["S0"]) ** (1 / args.years) - 1) * 100
        print(f"S0=₹{res['S0']:,.1f}  →  median ₹{med_end:,.1f}  CAGR {cagr:.1f}%")

    # Output
    plot_all(results, args.years, OUT_PNG)
    export_csv(results, args.years, OUT_CSV)

    print("\n── Summary ──────────────────────────────────────────────────────")
    print(f"{'Fund':<35} {'Start':>8} {'P5':>8} {'Median':>10} {'P95':>10} {'CAGR%':>7}")
    print("─" * 78)
    for code, res in results.items():
        p   = res["percentiles"]
        med = p[50][-1]
        cagr = ((med / res["S0"]) ** (1 / args.years) - 1) * 100
        print(f"  {res['name'][:33]:<33} {res['S0']:>8.1f} "
              f"{p[5][-1]:>8.1f} {med:>10.1f} {p[95][-1]:>10.1f} {cagr:>6.1f}%")


if __name__ == "__main__":
    main()
