"""
B4_markowitz.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BONUS CHALLENGE 4 — Markowitz Efficient Frontier
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Method  : Modern Portfolio Theory (Markowitz, 1952)
          - 8,000 Monte Carlo random portfolios
          - scipy.optimize.minimize (SLSQP) for Max Sharpe and Min Variance
          - Efficient frontier curve traced by targeting each return level
Inputs  : Daily NAV from bluestock_mf.db
Outputs : B4_efficient_frontier.png  — frontier chart + allocation bars
          B4_portfolio_weights.csv    — weights for all optimised portfolios

HOW TO RUN:
  pip install pandas numpy matplotlib scipy sqlalchemy
  python B4_markowitz.py

  # Use specific fund codes (min 3, recommended 4-8):
  python B4_markowitz.py --codes 119551 125497 120503 118632 119092

  # Change number of random portfolios:
  python B4_markowitz.py --portfolios 15000
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

warnings.filterwarnings("ignore")

# ── Config ─────────────────────────────────────────────────────────────────
BASE         = Path(__file__).parent
DB_PATH      = BASE / "bluestock_mf.db"
OUT_PNG      = BASE / "B4_efficient_frontier.png"
OUT_CSV      = BASE / "B4_portfolio_weights.csv"
RF           = 0.065          # RBI repo rate proxy (annual risk-free rate)
TRADING_DAYS = 252

# ── Colour palette ──────────────────────────────────────────────────────────
BG   = "#0F1629";  CARD = "#1A2540"
GRID = "#1E2D4A";  TXT  = "#F1F5F9";  TXT2 = "#94A3B8"
ACC1 = "#3B82F6";  ACC2 = "#10B981"
ACC3 = "#F59E0B";  ACC4 = "#EF4444"
PAL  = [ACC1, ACC2, ACC3, ACC4, "#8B5CF6", "#06B6D4", "#F97316", "#EC4899"]
CAT_COLORS = {
    "Large Cap": ACC1, "Mid Cap": ACC3, "Small Cap": ACC4,
    "Flexi Cap": "#8B5CF6", "ELSS": ACC2,
    "Short Duration": TXT2, "Gilt": GRID, "Liquid": "#64748B",
}


# ── Data loading ─────────────────────────────────────────────────────────────
def load_returns(db_path: Path, codes: list[int]) -> tuple[pd.DataFrame, dict, dict]:
    """
    Returns:
        ret      — DataFrame of daily returns, cols = amfi_code
        name_map — {amfi_code: scheme_name}
        cat_map  — {amfi_code: sub_category}
    """
    conn = sqlite3.connect(db_path)
    nav = pd.read_sql(f"""
        SELECT f.amfi_code, f.scheme_name, f.sub_category,
               d.full_date AS date, n.nav
        FROM fact_nav n
        JOIN dim_fund f ON f.fund_key = n.fund_key
        JOIN dim_date d ON d.date_key = n.date_key
        WHERE n.is_filled = 0
          AND f.amfi_code IN ({','.join(map(str, codes))})
        ORDER BY f.amfi_code, d.full_date
    """, conn, parse_dates=["date"])
    conn.close()

    name_map = (nav[["amfi_code", "scheme_name"]]
                .drop_duplicates().set_index("amfi_code")["scheme_name"].to_dict())
    cat_map  = (nav[["amfi_code", "sub_category"]]
                .drop_duplicates().set_index("amfi_code")["sub_category"].to_dict())

    nav_wide = nav.pivot(index="date", columns="amfi_code", values="nav").sort_index()
    ret      = nav_wide.pct_change().dropna()
    return ret, name_map, cat_map


def load_default_codes(db_path: Path) -> list[int]:
    """Top 5 Direct-plan equity funds by AUM."""
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("""
        SELECT f.amfi_code FROM dim_fund f
        JOIN fact_performance p ON p.fund_key = f.fund_key
        WHERE f.category = 'Equity' AND f.plan = 'Direct'
          AND p.is_outlier = 0
        ORDER BY p.aum_crore DESC LIMIT 5
    """, conn)
    conn.close()
    return df["amfi_code"].tolist()


# ── Portfolio maths ────────────────────────────────────────────────────────
def portfolio_stats(weights: np.ndarray, mu: np.ndarray,
                    cov: np.ndarray) -> tuple[float, float, float]:
    """Return (annualised return, annualised std, Sharpe ratio)."""
    w   = np.array(weights)
    r   = float(mu @ w)
    std = float(np.sqrt(w @ cov @ w))
    sh  = (r - RF) / std if std > 0 else -np.inf
    return r, std, sh


# ── Optimisation ──────────────────────────────────────────────────────────
def optimise(mu: np.ndarray, cov: np.ndarray,
             n: int, target_return: float | None = None,
             maximise_sharpe: bool = True) -> np.ndarray:
    """
    Solve for:
      - Max Sharpe (maximise_sharpe=True, target_return=None)
      - Min Variance (maximise_sharpe=False, target_return=None)
      - Target return on the frontier (target_return != None)
    """
    w0           = np.ones(n) / n
    bounds       = [(0.0, 1.0)] * n
    constraints  = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

    if target_return is not None:
        constraints.append({
            "type": "eq",
            "fun": lambda w, tr=target_return: portfolio_stats(w, mu, cov)[0] - tr,
        })

    if maximise_sharpe and target_return is None:
        objective = lambda w: -portfolio_stats(w, mu, cov)[2]
    else:
        objective = lambda w:  portfolio_stats(w, mu, cov)[1]

    res = minimize(objective, w0, method="SLSQP",
                   bounds=bounds, constraints=constraints,
                   options={"maxiter": 1000, "ftol": 1e-12})
    return res.x if res.success else w0


# ── Plotting ──────────────────────────────────────────────────────────────
def plot_frontier(ret: pd.DataFrame, mu: np.ndarray, cov: np.ndarray,
                  mc_results: dict, optimised: dict,
                  name_map: dict, cat_map: dict,
                  out_path: Path) -> None:

    codes = list(ret.columns)
    n     = len(codes)

    mc_rets    = np.array(mc_results["returns"])
    mc_stds    = np.array(mc_results["stds"])
    mc_sharpes = np.array(mc_results["sharpes"])

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), facecolor=BG)
    fig.suptitle(
        "B4 — Markowitz Efficient Frontier  |  Modern Portfolio Theory",
        color=TXT, fontsize=14, fontweight="bold",
    )

    # ── Left: Frontier scatter ─────────────────────────────────────────────
    ax = axes[0]
    ax.set_facecolor(CARD)

    sc = ax.scatter(mc_stds * 100, mc_rets * 100, c=mc_sharpes,
                    cmap="RdYlGn", alpha=0.35, s=7, zorder=2)
    cbar = plt.colorbar(sc, ax=ax, shrink=0.75, pad=0.02)
    cbar.set_label("Sharpe Ratio", color=TXT2, fontsize=8)
    cbar.ax.yaxis.label.set_color(TXT2)
    cbar.ax.tick_params(colors=TXT2, labelsize=7)

    # Efficient frontier curve
    ef_x = np.array(mc_results["ef_stds"]) * 100
    ef_y = np.array(mc_results["ef_rets"]) * 100
    valid = ~np.isnan(ef_x)
    ax.plot(ef_x[valid], ef_y[valid], color=ACC1, linewidth=2.5,
            zorder=5, label="Efficient frontier")

    # Key portfolios
    for label, key, marker, color, size in [
        ("Max Sharpe",     "max_sharpe",  "*", ACC3, 250),
        ("Min Variance",   "min_variance","D", ACC2, 140),
        ("Equal Weight",   "equal",       "^", ACC4, 140),
    ]:
        p = optimised[key]
        sh_label = f"{label} (Sharpe {p['sharpe']:.2f})"
        ax.scatter(p["std"] * 100, p["ret"] * 100,
                   s=size, marker=marker, color=color,
                   zorder=10, label=sh_label, edgecolors="white",
                   linewidths=0.6)

    # Individual fund dots
    for i, code in enumerate(codes):
        fund_ret = float(mu[i])
        fund_std = float(np.sqrt(cov[i, i]))
        c = CAT_COLORS.get(cat_map.get(code, ""), TXT2)
        ax.scatter(fund_std * 100, fund_ret * 100,
                   s=90, color=c, marker="o", zorder=8,
                   edgecolors="white", linewidths=0.5)
        ax.annotate(
            name_map.get(code, str(code))[:18],
            (fund_std * 100, fund_ret * 100),
            textcoords="offset points", xytext=(6, 3),
            fontsize=6.5, color=c,
        )

    ax.set_xlabel("Annual Risk / Std Dev (%)", color=TXT2, fontsize=10)
    ax.set_ylabel("Annual Expected Return (%)", color=TXT2, fontsize=10)
    ax.set_title("Portfolio Space  (colour = Sharpe Ratio)", color=TXT, fontsize=10)
    ax.legend(fontsize=8, facecolor=CARD, edgecolor=GRID, labelcolor=TXT, loc="lower right")
    ax.tick_params(colors=TXT2, labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)
    ax.grid(color=GRID, linewidth=0.4, linestyle="--", alpha=0.5)

    # ── Right: Allocation bar chart ────────────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor(CARD)
    short = [name_map.get(c, str(c))[:22] for c in codes]
    x = np.arange(n)
    w = 0.25

    port_order = [
        ("max_sharpe",  f"Max Sharpe  ({optimised['max_sharpe']['sharpe']:.2f})",  ACC3),
        ("min_variance",f"Min Variance ({optimised['min_variance']['sharpe']:.2f})",ACC2),
        ("equal",       f"Equal Weight ({optimised['equal']['sharpe']:.2f})",       ACC1),
    ]
    for i, (key, label, color) in enumerate(port_order):
        weights = optimised[key]["weights"] * 100
        ax2.bar(x + (i - 1) * w, weights, w,
                label=label, color=color, alpha=0.88)

    ax2.set_xticks(x)
    ax2.set_xticklabels(short, rotation=38, ha="right",
                        color=TXT2, fontsize=8)
    ax2.set_ylabel("Portfolio Weight (%)", color=TXT2, fontsize=10)
    ax2.set_title("Optimal Portfolio Allocations", color=TXT, fontsize=10)
    ax2.set_ylim(0, 100)
    ax2.legend(fontsize=8, facecolor=CARD, edgecolor=GRID, labelcolor=TXT)
    ax2.tick_params(colors=TXT2, labelsize=8)
    for sp in ax2.spines.values(): sp.set_edgecolor(GRID)
    ax2.grid(color=GRID, linewidth=0.4, linestyle="--", axis="y", alpha=0.5)

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"✅  Chart saved → {out_path}")


# ── CSV export ───────────────────────────────────────────────────────────
def export_weights(optimised: dict, name_map: dict, codes: list[int],
                   out_path: Path) -> None:
    rows = []
    for port_name, res in optimised.items():
        row = {
            "portfolio":       port_name,
            "annual_return_%": round(res["ret"] * 100, 3),
            "annual_std_%":    round(res["std"] * 100, 3),
            "sharpe_ratio":    round(res["sharpe"], 4),
        }
        for code, w in zip(codes, res["weights"]):
            row[f"w_{name_map.get(code, str(code))[:20]}"] = round(w * 100, 2)
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"✅  Weights CSV saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Markowitz Efficient Frontier for selected MF schemes"
    )
    parser.add_argument("--codes",      type=int, nargs="+", default=None,
                        help="AMFI codes (default: top 5 equity Direct funds)")
    parser.add_argument("--portfolios", type=int, default=8000,
                        help="Number of Monte Carlo random portfolios (default 8000)")
    parser.add_argument("--seed",       type=int, default=7,
                        help="Random seed (default 7)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"bluestock_mf.db not found at {DB_PATH}\n"
            "Place the database in the same folder as this script."
        )

    # Resolve codes
    codes = args.codes if args.codes else load_default_codes(DB_PATH)
    print(f"Funds selected : {codes}")

    # Load returns
    ret, name_map, cat_map = load_returns(DB_PATH, codes)
    print(f"Daily returns  : {ret.shape[0]} days × {ret.shape[1]} funds")

    # Annualised stats
    mu  = ret.mean().values * TRADING_DAYS
    cov = ret.cov().values  * TRADING_DAYS
    n   = len(codes)

    # Monte Carlo random portfolios
    print(f"Simulating {args.portfolios:,} random portfolios …")
    np.random.seed(args.seed)
    mc_returns, mc_stds, mc_sharpes = [], [], []
    for _ in range(args.portfolios):
        w     = np.random.dirichlet(np.ones(n))
        r, s, sh = portfolio_stats(w, mu, cov)
        mc_returns.append(r); mc_stds.append(s); mc_sharpes.append(sh)

    # Efficient frontier curve
    print("Tracing efficient frontier …")
    ef_rets, ef_stds = [], []
    for tr in np.linspace(min(mc_returns) * 1.01, max(mc_returns) * 0.99, 50):
        w   = optimise(mu, cov, n, target_return=tr)
        r, s, _ = portfolio_stats(w, mu, cov)
        ef_rets.append(r); ef_stds.append(s)

    mc_results = dict(
        returns=mc_returns, stds=mc_stds, sharpes=mc_sharpes,
        ef_rets=ef_rets, ef_stds=ef_stds,
    )

    # Optimised portfolios
    print("Optimising Max Sharpe, Min Variance, Equal Weight …")
    w_ms = optimise(mu, cov, n, maximise_sharpe=True)
    w_mv = optimise(mu, cov, n, maximise_sharpe=False)
    w_eq = np.ones(n) / n

    optimised = {}
    for key, w in [("max_sharpe", w_ms), ("min_variance", w_mv), ("equal", w_eq)]:
        r, s, sh = portfolio_stats(w, mu, cov)
        optimised[key] = dict(weights=w, ret=r, std=s, sharpe=sh)

    # Print results
    print("\n── Optimised Portfolio Results ──────────────────────────────────────")
    print(f"{'Portfolio':<16} {'Return':>8} {'Std Dev':>8} {'Sharpe':>8}")
    print("─" * 44)
    for key, res in optimised.items():
        print(f"  {key:<14}  {res['ret']*100:>7.2f}%  "
              f"{res['std']*100:>7.2f}%  {res['sharpe']:>8.3f}")

    print(f"\n── Max Sharpe Weights ({'AMFI code: weight':}")
    for code, w in zip(codes, w_ms):
        print(f"   [{code}] {name_map.get(code,'')[:40]:<42}  {w*100:5.1f}%")

    # Plot and export
    plot_frontier(ret, mu, cov, mc_results, optimised,
                  name_map, cat_map, OUT_PNG)
    export_weights(optimised, name_map, codes, OUT_CSV)


if __name__ == "__main__":
    main()
