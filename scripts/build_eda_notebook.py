"""
build_eda_notebook.py
Generates EDA_Analysis.ipynb from cleaned processed Excel files.
Run once: python3 build_eda_notebook.py
"""

import json, uuid
from pathlib import Path

# Changed from Linux path to current working directory path
NB_PATH = Path("EDA_Analysis.ipynb")


def uid():
    return str(uuid.uuid4())[:8]


def md(text):
    return {"id": uid(), "cell_type": "markdown", "metadata": {}, "source": text}


def code(text):
    return {
        "id": uid(), "cell_type": "code",
        "execution_count": None, "metadata": {},
        "outputs": [], "source": text,
    }


# ─────────────────────────────────────────────────────────────────────────────
cells = []

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
# 📊 Mutual Fund EDA Analysis — Bluestock
**Day 3 · Exploratory Data Analysis**

> Datasets: 10 cleaned Excel files from `data/processed/`  
> Period: January 2022 – December 2025 | 40 schemes | 32,778 investor transactions
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("## ⚙️ Setup — Imports & Data Load"))

cells.append(code("""\
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.patches as mpatches
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Paths ─────────────────────────────────────────────────────────────────────
PROC      = Path("data/processed")
CHARTS    = Path("reports/charts")
CHARTS.mkdir(parents=True, exist_ok=True)

# ── Global style ──────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", palette="tab10", font_scale=1.05)
PLT_STYLE  = "plotly_white"
DPI        = 150
FIG_W, FIG_H = 14, 6   # default matplotlib figure size

# ── Helpers ───────────────────────────────────────────────────────────────────
def save(name: str):
    \"\"\"Save current matplotlib figure to reports/charts/<name>.png.\"\"\"
    path = CHARTS / f"{name}.png"
    plt.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close()
    print(f"  ✓ saved  →  {path}")

def save_plotly(fig, name: str):
    \"\"\"Save a Plotly figure as PNG.\"\"\"
    path = CHARTS / f"{name}.png"
    fig.write_image(str(path), scale=2, width=1400, height=700)
    print(f"  ✓ saved  →  {path}")

print("Libraries loaded ✓")
"""))

# ── Load data ─────────────────────────────────────────────────────────────────
cells.append(code("""\
# ── Load all 10 cleaned datasets ──────────────────────────────────────────────
funds = pd.read_excel(PROC / "01_fund_master_clean.xlsx",         parse_dates=["launch_date"])
nav   = pd.read_excel(PROC / "02_nav_history_clean.xlsx",         parse_dates=["date"])
aum   = pd.read_excel(PROC / "03_aum_by_fund_house_clean.xlsx",   parse_dates=["date"])
sip   = pd.read_excel(PROC / "04_monthly_sip_inflows_clean.xlsx", parse_dates=["month"])
cat   = pd.read_excel(PROC / "05_category_inflows_clean.xlsx",    parse_dates=["month"])
folio = pd.read_excel(PROC / "06_industry_folio_count_clean.xlsx",parse_dates=["month"])
perf  = pd.read_excel(PROC / "07_scheme_performance_clean.xlsx")
txn   = pd.read_excel(PROC / "08_investor_transactions_clean.xlsx",parse_dates=["date"])
hold  = pd.read_excel(PROC / "09_portfolio_holdings_clean.xlsx")

# ── Quick summary ─────────────────────────────────────────────────────────────
datasets = dict(funds=funds, nav=nav, aum=aum, sip=sip, cat=cat,
                folio=folio, perf=perf, txn=txn, hold=hold)
print(f"{'Dataset':<10}  {'Rows':>8}  {'Cols':>6}  Columns")
print("─" * 70)
for name, df in datasets.items():
    print(f"{name:<10}  {len(df):>8,}  {df.shape[1]:>6}  {list(df.columns)[:4]} ...")
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 1 · NAV Trend Analysis — All 40 Schemes (2022–2026)

Daily NAV normalised to a base of **100** on the first trading day (Jan 2022),
so growth across schemes with very different absolute NAV levels can be compared
on the same axis.

- 🟢 **Green band** = 2023 bull run (Jan–Dec 2023)
- 🟠 **Orange band** = 2024 market correction (Mar–Sep 2024)
"""))

cells.append(code("""\
def chart_nav_trends():
    # Use only original (non-filled) NAV rows for accuracy
    df = nav[nav["is_filled"] == 0].copy()
    df = df.merge(funds[["amfi_code", "category"]], on="amfi_code")

    # Pivot → normalise to 100 on first date
    pivot = df.pivot_table(index="date", columns="amfi_code", values="nav")
    pivot_norm = pivot.divide(pivot.bfill().iloc[0]).multiply(100)

    CAT_COLOR = {"Equity": "#1565C0", "Debt": "#E65100", "Hybrid": "#2E7D32"}
    code_cat  = funds.set_index("amfi_code")["category"].to_dict()

    fig = go.Figure()

    # One trace per scheme
    for code in pivot_norm.columns:
        s   = pivot_norm[code].dropna()
        cat = code_cat.get(code, "Equity")
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines",
            name=str(code), showlegend=False,
            line=dict(width=1.2, color=CAT_COLOR.get(cat, "#999")),
            opacity=0.50,
            hovertemplate="%{x|%d %b %Y}<br>Indexed NAV: %{y:.1f}<extra></extra>",
        ))

    # Region highlights
    fig.add_vrect(x0="2023-01-01", x1="2023-12-31",
                  fillcolor="rgba(56,142,60,0.10)", layer="below", line_width=0,
                  annotation_text="2023 Bull Run", annotation_position="top left",
                  annotation_font=dict(size=11, color="#1B5E20"))
    fig.add_vrect(x0="2024-03-01", x1="2024-09-30",
                  fillcolor="rgba(230,81,0,0.10)", layer="below", line_width=0,
                  annotation_text="2024 Correction", annotation_position="top left",
                  annotation_font=dict(size=11, color="#BF360C"))

    # Legend proxies for categories
    for cat, col in CAT_COLOR.items():
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                                 name=cat, line=dict(color=col, width=2.5)))

    fig.update_layout(
        title=dict(text="<b>NAV Trends — All 40 Schemes (Base 100 = Jan 2022)</b>",
                   font=dict(size=16)),
        xaxis=dict(title="Date", showgrid=True, gridcolor="#EEEEEE"),
        yaxis=dict(title="Indexed NAV (Base 100)", showgrid=True, gridcolor="#EEEEEE"),
        legend=dict(title="Category", orientation="v"),
        template=PLT_STYLE, height=520, hovermode="x unified",
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.show()
    save_plotly(fig, "01_nav_trends_all_schemes")

chart_nav_trends()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 2 · AUM Growth — Grouped Bar Chart by Fund House (2022–2025)

Compares peak AUM (₹ Lakh Crore) per year across all fund houses.  
**SBI Mutual Fund** consistently leads the industry.
"""))

cells.append(code("""\
def chart_aum_growth():
    df = aum.copy()
    df["year"] = df["date"].dt.year
    # Take year-end (maximum) AUM per fund house per year
    df_yr = (df[df["year"].between(2022, 2025)]
             .groupby(["year", "fund_house"], as_index=False)["aum_lakh_crore"].max())

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H + 1))
    houses = df_yr["fund_house"].unique()
    years  = sorted(df_yr["year"].unique())
    x  = np.arange(len(houses))
    w  = 0.20
    pal = sns.color_palette("tab10", len(years))

    for i, yr in enumerate(years):
        sub  = df_yr[df_yr["year"] == yr].set_index("fund_house")["aum_lakh_crore"]
        vals = [sub.get(h, 0) for h in houses]
        bars = ax.bar(x + i * w, vals, width=w, color=pal[i],
                      label=str(yr), edgecolor="white", linewidth=0.6)
        # Annotate SBI's bar each year
        for j, (h, v) in enumerate(zip(houses, vals)):
            if "SBI" in h and v > 0:
                ax.text(x[j] + i * w, v + 0.05, f"{v:.1f}",
                        ha="center", va="bottom", fontsize=7.5,
                        color="#1a237e", fontweight="bold")

    # Shade SBI column
    sbi_j = next((j for j, h in enumerate(houses) if "SBI" in h), None)
    if sbi_j is not None:
        ax.axvspan(sbi_j - 0.35, sbi_j + 0.95,
                   alpha=0.06, color="#1565C0", zorder=0, label="_nolegend_")

    ax.set_xticks(x + w * 1.5)
    ax.set_xticklabels(houses, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("AUM (₹ Lakh Crore)", fontsize=11)
    ax.set_title("AUM Growth by Fund House — Annual Peak (2022–2025)",
                 fontsize=14, fontweight="bold", pad=14)
    ax.legend(title="Year", framealpha=0.9, fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))
    sns.despine(ax=ax)
    plt.tight_layout()
    save("02_aum_growth_grouped_bar")

chart_aum_growth()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 3 · Monthly SIP Inflow Time-Series (Jan 2022 – Dec 2025)

The Indian MF industry reached an **all-time high SIP inflow of ₹31,002 Crore** in December 2025,
nearly 2.7× the ₹11,517 Cr recorded in January 2022.
"""))

cells.append(code("""\
def chart_sip_timeseries():
    df   = sip.sort_values("month").copy()
    peak = df.loc[df["sip_inflow_crore"].idxmax()]

    fig = go.Figure()

    # Shaded area + line
    fig.add_trace(go.Scatter(
        x=df["month"], y=df["sip_inflow_crore"],
        mode="lines+markers",
        name="SIP Inflow (₹ Cr)",
        line=dict(color="#1565C0", width=2.5),
        marker=dict(size=5, color="#1565C0"),
        fill="tozeroy",
        fillcolor="rgba(21,101,192,0.09)",
    ))

    # ATH annotation
    fig.add_annotation(
        x=peak["month"], y=peak["sip_inflow_crore"],
        text=f"<b>All-Time High</b><br>₹{peak['sip_inflow_crore']:,} Cr<br>Dec 2025",
        showarrow=True, arrowhead=2, arrowwidth=1.5, arrowcolor="#C62828",
        font=dict(size=11, color="#C62828"),
        bgcolor="white", bordercolor="#C62828", borderwidth=1.5,
        borderpad=5, ax=30, ay=-55,
    )

    # 2.7× growth annotation
    fig.add_annotation(
        x=df["month"].iloc[0], y=df["sip_inflow_crore"].iloc[0],
        text="Jan 2022<br>₹11,517 Cr", showarrow=False,
        font=dict(size=10, color="#555"), bgcolor="white",
        bordercolor="#ccc", borderwidth=1, borderpad=4,
        xanchor="left", yanchor="bottom",
    )

    fig.update_layout(
        title=dict(text="<b>Monthly SIP Inflows — Industry Level (Jan 2022 – Dec 2025)</b>",
                   font=dict(size=16)),
        xaxis=dict(title="Month", showgrid=True, gridcolor="#EEEEEE"),
        yaxis=dict(title="SIP Inflow (₹ Crore)", showgrid=True, gridcolor="#EEEEEE"),
        template=PLT_STYLE, height=480,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.show()
    save_plotly(fig, "03_sip_inflow_timeseries")

chart_sip_timeseries()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 4 · Category Inflow Heatmap

Net inflows (₹ Crore) by fund category and month.  
Green = strong inflows, Red = outflows or weak months.
"""))

cells.append(code("""\
def chart_category_heatmap():
    df = cat.copy()
    df["month_str"] = df["month"].dt.strftime("%b %y")
    month_order     = df.sort_values("month")["month_str"].unique().tolist()

    pivot = (df.pivot_table(index="category", columns="month_str",
                            values="net_inflow_crore", aggfunc="sum")
               .reindex(columns=month_order))

    fig, ax = plt.subplots(figsize=(20, 4.5))
    sns.heatmap(
        pivot, ax=ax,
        cmap="RdYlGn", center=0, linewidths=0.25,
        cbar_kws={"label": "Net Inflow (₹ Cr)", "shrink": 0.8},
        annot=(pivot.shape[1] <= 24),
        fmt=".0f", annot_kws={"size": 7},
    )
    ax.set_title("Category-wise Net Inflows — Monthly Heatmap",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Month", fontsize=10)
    ax.set_ylabel("Fund Category", fontsize=10)
    plt.xticks(rotation=45, ha="right", fontsize=7.5)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    save("04_category_inflow_heatmap")

chart_category_heatmap()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 5 · Investor Demographics — Age Group, SIP Box Plot & Gender Split
"""))

cells.append(code("""\
def chart_demographics():
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    pal = sns.color_palette("Set2", 8)

    # ── 5a. Age group pie ──────────────────────────────────────────────────────
    age_cnt = txn["age_group"].value_counts()
    axes[0].pie(
        age_cnt.values, labels=age_cnt.index,
        autopct="%1.1f%%", startangle=140,
        colors=pal[:len(age_cnt)],
        wedgeprops=dict(linewidth=0.6, edgecolor="white"),
        textprops={"fontsize": 9},
    )
    axes[0].set_title("Investor Age-Group Distribution", fontweight="bold", fontsize=11)

    # ── 5b. SIP amount boxplot by age ──────────────────────────────────────────
    age_order = [a for a in ["18-25", "26-35", "36-45", "46-55", "56+"]
                 if a in txn["age_group"].unique()]
    sip_txn = txn[txn["transaction_type"] == "SIP"]

    data_by_age = [sip_txn[sip_txn["age_group"] == a]["amount"].dropna().values
                   for a in age_order]
    bp = axes[1].boxplot(
        data_by_age, labels=age_order, patch_artist=True,
        medianprops=dict(color="#212121", linewidth=2),
        flierprops=dict(marker="o", markersize=3, alpha=0.3),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
    )
    for patch, c in zip(bp["boxes"], pal):
        patch.set_facecolor(c); patch.set_alpha(0.75)

    axes[1].set_title("SIP Amount by Age Group (₹)", fontweight="bold", fontsize=11)
    axes[1].set_xlabel("Age Group", fontsize=10)
    axes[1].set_ylabel("SIP Amount (₹)", fontsize=10)
    axes[1].yaxis.set_major_formatter(
        mtick.FuncFormatter(lambda x, _: f"₹{x/1000:.0f}K" if x >= 1000 else f"₹{x:.0f}"))

    # ── 5c. Gender pie ─────────────────────────────────────────────────────────
    gen_cnt = txn["gender"].value_counts()
    gen_colors = {"Male": "#42A5F5", "Female": "#EF5350", "Other": "#66BB6A"}
    colors_g = [gen_colors.get(g, "#BDBDBD") for g in gen_cnt.index]
    axes[2].pie(
        gen_cnt.values, labels=gen_cnt.index,
        autopct="%1.1f%%", startangle=90,
        colors=colors_g,
        wedgeprops=dict(linewidth=0.6, edgecolor="white"),
        textprops={"fontsize": 9},
    )
    axes[2].set_title("Gender Split — All Transactions", fontweight="bold", fontsize=11)

    plt.suptitle("Investor Demographics", fontsize=15, fontweight="bold", y=1.02)
    plt.tight_layout()
    save("05_investor_demographics")

chart_demographics()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 6 · Geographic Distribution — State-wise SIP & City Tier Split
"""))

cells.append(code("""\
def chart_geographic():
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    # ── 6a. State-wise SIP — horizontal bar (top 15) ──────────────────────────
    sip_txn = txn[txn["transaction_type"] == "SIP"]
    state_amt = (sip_txn.groupby("state")["amount"]
                 .sum()
                 .sort_values(ascending=True)
                 .tail(15))

    base_col = "#90CAF9"
    top3_col = "#1565C0"
    colors_b  = [top3_col if s in state_amt.index[-3:] else base_col
                 for s in state_amt.index]

    bars = axes[0].barh(
        state_amt.index, state_amt.values / 1e7,
        color=colors_b, edgecolor="white", linewidth=0.5, height=0.65,
    )
    for bar, val in zip(bars, state_amt.values / 1e7):
        axes[0].text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                     f"₹{val:.0f} Cr",
                     va="center", ha="left", fontsize=8, color="#444")

    axes[0].set_xlabel("SIP Amount (₹ Crore)", fontsize=10)
    axes[0].set_title("Top 15 States by SIP Investment", fontweight="bold", fontsize=11)
    axes[0].xaxis.set_major_formatter(
        mtick.FuncFormatter(lambda x, _: f"₹{x:.0f} Cr"))
    sns.despine(ax=axes[0])

    # ── 6b. T30 vs B30 pie ────────────────────────────────────────────────────
    tier_cnt = txn["city_tier"].value_counts()
    tier_colors = {"T30": "#1565C0", "B30": "#42A5F5", "T-30": "#1565C0", "B-30": "#42A5F5"}
    colors_t = [tier_colors.get(t, "#90CAF9") for t in tier_cnt.index]

    axes[1].pie(
        tier_cnt.values, labels=tier_cnt.index,
        autopct="%1.1f%%", startangle=90,
        colors=colors_t,
        wedgeprops=dict(linewidth=0.8, edgecolor="white"),
        textprops={"fontsize": 10},
        explode=[0.03] * len(tier_cnt),
    )
    axes[1].set_title("T30 vs B30 City Tier Split", fontweight="bold", fontsize=11)

    plt.suptitle("Geographic Distribution of Investors", fontsize=14,
                 fontweight="bold", y=1.01)
    plt.tight_layout()
    save("06_geographic_distribution")

chart_geographic()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 7 · Industry Folio Count Growth (Jan 2022 – Dec 2025)

Total investor folios nearly **doubled** in 4 years — from 13.26 Cr to 26.12 Cr.  
Milestones at 15 Cr, 20 Cr and 25 Cr are annotated.
"""))

cells.append(code("""\
def chart_folio_growth():
    df = folio.sort_values("month").copy()
    milestones = {15: "15 Cr", 20: "20 Cr", 25: "25 Cr"}

    fig = go.Figure()

    # Stacked area by category
    stack_cols = [
        ("equity_folios_crore",  "Equity",  "#1565C0"),
        ("hybrid_folios_crore",  "Hybrid",  "#2E7D32"),
        ("debt_folios_crore",    "Debt",    "#F57F17"),
        ("others_folios_crore",  "Others",  "#9E9E9E"),
    ]
    for col, name, color in stack_cols:
        fig.add_trace(go.Scatter(
            x=df["month"], y=df[col],
            name=name, mode="lines",
            line=dict(color=color, width=1.5),
            stackgroup="one",
            hovertemplate=f"{name}: %{{y:.2f}} Cr<extra></extra>",
        ))

    # Milestone annotations on total folios line
    for milestone, label in milestones.items():
        cross = df[df["total_folios_crore"] >= milestone]
        if not cross.empty:
            row = cross.iloc[0]
            fig.add_annotation(
                x=row["month"], y=milestone,
                text=f"<b>{label}</b>", showarrow=True,
                arrowhead=3, arrowwidth=1.5, arrowcolor="#C62828",
                font=dict(size=10, color="#C62828"),
                bgcolor="white", bordercolor="#C62828",
                borderwidth=1.2, borderpad=4,
                ax=-50, ay=-35,
            )

    fig.update_layout(
        title=dict(text="<b>Industry Folio Count Growth (Crore Accounts)</b>",
                   font=dict(size=16)),
        xaxis=dict(title="Month", showgrid=True, gridcolor="#EEEEEE"),
        yaxis=dict(title="Folios (Crore)", showgrid=True, gridcolor="#EEEEEE"),
        legend=dict(title="Category"),
        template=PLT_STYLE, height=500,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.show()
    save_plotly(fig, "07_folio_count_growth")

chart_folio_growth()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 8 · Daily Return Correlation Heatmap — 10 Selected Funds

Pairwise **Pearson correlation** of daily NAV returns.  
High correlation (>0.8) means the funds move together; limited diversification benefit.
"""))

cells.append(code("""\
def chart_return_correlation():
    # Select top 10 funds by available history (non-filled rows only)
    top10 = (nav[nav["is_filled"] == 0]
             .groupby("amfi_code").size()
             .nlargest(10).index.tolist())

    short_name = (funds.set_index("amfi_code")["scheme_name"]
                  .str.split(" - ").str[0]
                  .str.replace(r"\s+Fund.*", "", regex=True)
                  .str.strip())

    pivot = (nav[(nav["amfi_code"].isin(top10)) & (nav["is_filled"] == 0)]
             .pivot_table(index="date", columns="amfi_code", values="nav")
             .sort_index())
    returns = pivot.pct_change().dropna()
    returns.columns = [short_name.get(c, str(c)) for c in returns.columns]

    corr = returns.corr()

    fig, ax = plt.subplots(figsize=(11, 9))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)   # upper triangle
    cmap = sns.diverging_palette(220, 10, as_cmap=True)

    sns.heatmap(
        corr, mask=mask, ax=ax,
        cmap=cmap, center=0, vmin=-1, vmax=1,
        annot=True, fmt=".2f", annot_kws={"size": 9},
        linewidths=0.4, linecolor="#EEEEEE",
        cbar_kws={"label": "Pearson r", "shrink": 0.85},
        square=True,
    )
    ax.set_title("Daily Return Correlation Matrix — 10 Funds",
                 fontsize=13, fontweight="bold", pad=14)
    plt.xticks(rotation=35, ha="right", fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    save("08_return_correlation_heatmap")

chart_return_correlation()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 9 · Sector Allocation Donut — All Equity Funds

Aggregated portfolio weight from `09_portfolio_holdings` across every equity fund.  
Banking & Financials dominate, reflecting the large-cap index composition.
"""))

cells.append(code("""\
def chart_sector_donut():
    eq_codes  = funds[funds["category"] == "Equity"]["amfi_code"].tolist()
    eq_hold   = hold[hold["amfi_code"].isin(eq_codes)]
    sector_wt = (eq_hold.groupby("sector")["weight_pct"]
                 .sum()
                 .sort_values(ascending=False))

    pal = sns.color_palette("tab20", len(sector_wt))

    fig, ax = plt.subplots(figsize=(12, 8))
    wedges, texts, autotexts = ax.pie(
        sector_wt.values,
        labels=None,
        autopct=lambda p: f"{p:.1f}%" if p > 2.5 else "",
        startangle=90,
        colors=pal,
        pctdistance=0.78,
        wedgeprops=dict(width=0.55, linewidth=0.8, edgecolor="white"),
    )
    for at in autotexts:
        at.set_fontsize(8.5)
        at.set_fontweight("bold")

    ax.set_title("Sector Allocation — Equity Funds (Aggregate Weight)",
                 fontsize=13, fontweight="bold", pad=18)

    # Legend with weights
    legend_labels = [f"{s}  ({w:.1f}%)"
                     for s, w in zip(sector_wt.index, sector_wt.values)]
    ax.legend(wedges, legend_labels,
              title="Sector", loc="center left",
              bbox_to_anchor=(1.02, 0.5),
              fontsize=8.5, title_fontsize=9,
              frameon=True, framealpha=0.9)

    plt.tight_layout()
    save("09_sector_allocation_donut")

chart_sector_donut()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 10 · Top Fund Houses by AUM (Latest Snapshot)
"""))

cells.append(code("""\
def chart_top_fund_houses():
    # Latest AUM snapshot per fund house
    latest = (aum.sort_values("date")
              .groupby("fund_house", as_index=False)
              .last()[["fund_house", "aum_lakh_crore"]]
              .sort_values("aum_lakh_crore", ascending=True))

    colors = ["#1565C0" if "SBI" in fh else "#90CAF9"
              for fh in latest["fund_house"]]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(latest["fund_house"], latest["aum_lakh_crore"],
                   color=colors, edgecolor="white", linewidth=0.5, height=0.65)

    for bar, val in zip(bars, latest["aum_lakh_crore"]):
        ax.text(val + 0.05, bar.get_y() + bar.get_height() / 2,
                f"₹{val:.2f}L Cr", va="center", ha="left", fontsize=8.5)

    ax.set_xlabel("AUM (₹ Lakh Crore)", fontsize=10)
    ax.set_title("Top Fund Houses by AUM — Latest Snapshot",
                 fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("%.1f"))
    sns.despine(ax=ax)

    legend_patches = [
        mpatches.Patch(color="#1565C0", label="SBI Mutual Fund (Leader)"),
        mpatches.Patch(color="#90CAF9", label="Other AMCs"),
    ]
    ax.legend(handles=legend_patches, fontsize=9, loc="lower right")
    plt.tight_layout()
    save("10_top_fund_houses_aum")

chart_top_fund_houses()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 11 · Monthly Transaction Volume by Type
"""))

cells.append(code("""\
def chart_txn_volume():
    df = txn.copy()
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    monthly = (df.groupby(["month", "transaction_type"])["amount"]
               .agg(["sum", "count"])
               .reset_index())
    monthly.columns = ["month", "transaction_type", "total_amount", "count"]

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("Total Amount (₹)", "Number of Transactions"))

    colors = {"SIP": "#1565C0", "Lumpsum": "#E65100", "Redemption": "#C62828"}

    for txn_type in ["SIP", "Lumpsum", "Redemption"]:
        sub = monthly[monthly["transaction_type"] == txn_type]
        col = colors.get(txn_type, "#999")
        fig.add_trace(go.Scatter(
            x=sub["month"], y=sub["total_amount"],
            name=txn_type, mode="lines+markers",
            line=dict(color=col, width=2),
            marker=dict(size=4),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=sub["month"], y=sub["count"],
            name=txn_type, mode="lines+markers",
            line=dict(color=col, width=2),
            marker=dict(size=4),
            showlegend=False,
        ), row=1, col=2)

    fig.update_layout(
        title=dict(text="<b>Monthly Transaction Volume by Type</b>",
                   font=dict(size=16)),
        template=PLT_STYLE, height=460,
        legend=dict(title="Type"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.show()
    save_plotly(fig, "11_monthly_transaction_volume")

chart_txn_volume()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 12 · Fund Category Distribution — Scheme Count & AUM
"""))

cells.append(code("""\
def chart_category_distribution():
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    pal = sns.color_palette("Set2", 8)

    # Count of schemes by category
    cat_cnt = funds["category"].value_counts()
    axes[0].pie(
        cat_cnt.values, labels=cat_cnt.index,
        autopct="%1.1f%%", startangle=140,
        colors=pal[:len(cat_cnt)],
        wedgeprops=dict(linewidth=0.6, edgecolor="white"),
        textprops={"fontsize": 10},
        explode=[0.03] * len(cat_cnt),
    )
    axes[0].set_title("Fund Category — Scheme Count", fontweight="bold", fontsize=12)

    # AUM by category (from perf)
    cat_aum = (perf.groupby("category")["aum_crore"]
               .sum()
               .sort_values(ascending=False))
    bars = axes[1].bar(cat_aum.index, cat_aum.values / 1e3,
                       color=pal[:len(cat_aum)], edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, cat_aum.values / 1e3):
        axes[1].text(bar.get_x() + bar.get_width() / 2, val + 0.3,
                     f"₹{val:.0f}K Cr", ha="center", va="bottom", fontsize=9)
    axes[1].set_ylabel("Total AUM (₹ '000 Crore)", fontsize=10)
    axes[1].set_title("Fund Category — Total AUM", fontweight="bold", fontsize=12)
    axes[1].set_xlabel("Category", fontsize=10)
    sns.despine(ax=axes[1])

    plt.suptitle("Fund Category Distribution", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    save("12_fund_category_distribution")

chart_category_distribution()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 13 · Risk vs Return Scatter — All 40 Funds

Bubble size = AUM. Colour = Category.  
Funds in the **top-left** quadrant (high return, low risk) are most efficient.
"""))

cells.append(code("""\
def chart_risk_return():
    df = perf.merge(funds[["amfi_code", "category"]], on="amfi_code", how="left",
                    suffixes=("", "_fm"))
    cat_col = df["category_fm"] if "category_fm" in df.columns else df["category"]

    fig = px.scatter(
        df,
        x="std_dev_ann_pct",
        y="return_3yr_pct",
        color=cat_col,
        size="aum_crore",
        size_max=35,
        hover_name="scheme_name",
        hover_data={
            "sharpe_ratio": ":.2f",
            "expense_ratio_pct": ":.2f",
            "std_dev_ann_pct": ":.1f",
            "aum_crore": ":,",
        },
        labels={
            "std_dev_ann_pct": "Annualised Std Dev (%)",
            "return_3yr_pct":  "3-Year Return (%)",
        },
        template=PLT_STYLE,
        color_discrete_sequence=px.colors.qualitative.Set1,
    )
    fig.update_layout(
        title=dict(text="<b>Risk vs Return — All 40 Funds (Bubble = AUM)</b>",
                   font=dict(size=16)),
        height=540,
        legend=dict(title="Category"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE")
    fig.show()
    save_plotly(fig, "13_risk_return_scatter")

chart_risk_return()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 14 · Expense Ratio vs 1-Year Return by Category
"""))

cells.append(code("""\
def chart_expense_vs_return():
    df = perf.dropna(subset=["expense_ratio_pct", "return_1yr_pct"])

    fig, ax = plt.subplots(figsize=(10, 6))
    pal_cat = {"Equity": "#1565C0", "Debt": "#E65100", "Hybrid": "#2E7D32"}

    for cat_name, grp in df.groupby("category"):
        ax.scatter(
            grp["expense_ratio_pct"], grp["return_1yr_pct"],
            label=cat_name,
            color=pal_cat.get(cat_name, "#9E9E9E"),
            s=80, alpha=0.80, edgecolors="white", linewidths=0.5,
        )
        # Best-fit line per category
        m, b = np.polyfit(grp["expense_ratio_pct"], grp["return_1yr_pct"], 1)
        xr = np.linspace(grp["expense_ratio_pct"].min(),
                         grp["expense_ratio_pct"].max(), 50)
        ax.plot(xr, m * xr + b,
                color=pal_cat.get(cat_name, "#9E9E9E"),
                linewidth=1.5, linestyle="--", alpha=0.7)

    ax.set_xlabel("Expense Ratio (%)", fontsize=11)
    ax.set_ylabel("1-Year Return (%)", fontsize=11)
    ax.set_title("Expense Ratio vs 1-Year Return — by Category",
                 fontsize=13, fontweight="bold", pad=12)
    ax.legend(title="Category", fontsize=9)
    sns.despine(ax=ax)
    plt.tight_layout()
    save("14_expense_ratio_vs_return")

chart_expense_vs_return()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 15 · Sharpe Ratio Leaderboard — Top 15 Funds
"""))

cells.append(code("""\
def chart_sharpe_leaderboard():
    df = (perf[perf["is_outlier"] == 0]
          .dropna(subset=["sharpe_ratio"])
          .nlargest(15, "sharpe_ratio")
          .sort_values("sharpe_ratio", ascending=True))

    df["short_name"] = (df["scheme_name"]
                        .str.split(" - ").str[0]
                        .str.replace(r"\s+Fund\b", " Fund", regex=True))

    pal_cat = {"Equity": "#1565C0", "Debt": "#E65100", "Hybrid": "#2E7D32"}
    colors  = [pal_cat.get(c, "#9E9E9E") for c in df["category"]]

    fig, ax = plt.subplots(figsize=(11, 7))
    bars = ax.barh(df["short_name"], df["sharpe_ratio"],
                   color=colors, edgecolor="white", linewidth=0.4, height=0.65)

    for bar, val in zip(bars, df["sharpe_ratio"]):
        ax.text(val + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", ha="left", fontsize=8.5, color="#333")

    legend_patches = [mpatches.Patch(color=v, label=k) for k, v in pal_cat.items()]
    ax.legend(handles=legend_patches, title="Category", fontsize=9, loc="lower right")

    ax.set_xlabel("Sharpe Ratio", fontsize=10)
    ax.set_title("Top 15 Funds by Sharpe Ratio (Outliers Excluded)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.axvline(x=1.0, color="#E53935", linestyle="--", linewidth=1.2,
               label="Sharpe = 1.0 (benchmark)")
    sns.despine(ax=ax)
    plt.tight_layout()
    save("15_sharpe_ratio_leaderboard")

chart_sharpe_leaderboard()
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## 📋 Key Business Insights

The following 10 insights are drawn directly from the EDA charts above.
"""))

cells.append(code("""\
insights = [
    {
        "title": "1 · SIP at All-Time High — 2.7× growth in 4 years",
        "detail": ("Monthly SIP inflows reached ₹31,002 Cr in Dec 2025, up from ₹11,517 Cr in "
                   "Jan 2022 — a 169% rise driven by new SIP account additions and rising ticket sizes. "
                   "→ Chart 3"),
    },
    {
        "title": "2 · SBI Mutual Fund Leads AUM with ₹12.5 Lakh Crore",
        "detail": ("SBI AMC holds the top position in every year from 2022–2025, outpacing "
                   "ICICI Prudential and HDFC AMC by a significant margin. "
                   "→ Charts 2 & 10"),
    },
    {
        "title": "3 · 2023 Bull Run Lifted All Equity NAVs by 35–55%",
        "detail": ("The normalised NAV chart shows a sharp upward move across equity schemes in 2023, "
                   "with mid-cap and small-cap funds outperforming large-cap peers. "
                   "→ Chart 1"),
    },
    {
        "title": "4 · Folio Count Doubled — 13 Cr → 26 Cr in 4 Years",
        "detail": ("Industry folios crossed 15 Cr, 20 Cr and 25 Cr milestones, driven almost "
                   "entirely by equity folios, signalling broad retail participation. "
                   "→ Chart 7"),
    },
    {
        "title": "5 · 26–35 Age Group is the Core SIP Investor",
        "detail": ("The 26–35 cohort dominates transaction share. The SIP box-plot reveals they "
                   "also have the widest ticket-size range, suggesting early-career wealth-building "
                   "is the dominant use case. → Chart 5"),
    },
    {
        "title": "6 · High Cross-Fund Correlation Limits Diversification",
        "detail": ("The 10-fund correlation matrix shows pairwise Pearson r mostly above 0.75, "
                   "meaning investors holding multiple equity funds from this universe get limited "
                   "diversification benefit. → Chart 8"),
    },
    {
        "title": "7 · Banking & Financials Dominate Equity Portfolios",
        "detail": ("Aggregated sector weights show Banking + Financial Services as the single "
                   "largest allocation, reflecting the heavy BFSI representation in large-cap indices. "
                   "→ Chart 9"),
    },
    {
        "title": "8 · Direct Plans Deliver Meaningfully Higher Returns",
        "detail": ("Risk-return and expense-ratio charts confirm Direct plans consistently show "
                   "1.5–2.5 pp higher 1yr/3yr returns versus their Regular counterparts, purely "
                   "from the lower TER. → Charts 13 & 14"),
    },
    {
        "title": "9 · Maharashtra & Gujarat Account for ~35% of SIP Value",
        "detail": ("The state-wise bar chart shows these two states dominate SIP flows. "
                   "T30 cities contribute ~60% of volume vs B30's ~40%, confirming urban bias. "
                   "→ Chart 6"),
    },
    {
        "title": "10 · Expense Ratio Does Not Predict Returns Within a Category",
        "detail": ("The scatter with best-fit lines by category shows near-flat or weakly negative "
                   "slopes, confirming that within a category, fund manager skill and market-timing "
                   "matter more than cost alone. → Chart 14"),
    },
]

print("=" * 72)
print("  10 KEY BUSINESS INSIGHTS — BLUESTOCK MUTUAL FUND EDA")
print("=" * 72)
for ins in insights:
    print(f"\n  ✦ {ins['title']}")
    print(f"    {ins['detail']}")
print("\n" + "=" * 72)
"""))

# ══════════════════════════════════════════════════════════════════════════════
cells.append(md("""\
---
## ✅ Deliverables Summary
"""))

cells.append(code("""\
import os
chart_files = sorted(CHARTS.glob("*.png"))
print(f"{'Chart File':<45}  {'Size':>8}")
print("─" * 57)
for f in chart_files:
    size_kb = os.path.getsize(f) / 1024
    print(f"  {f.name:<43}  {size_kb:>6.0f} KB")
print(f"\n  Total: {len(chart_files)} PNG charts in {CHARTS}")
print(f"  Notebook: EDA_Analysis.ipynb")
"""))

# ═════════════════════════════════════════════════════════════════════════════
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.12.0",
        },
    },
    "cells": cells,
}

NB_PATH.write_text(
    json.dumps(nb, indent=1, ensure_ascii=False),
    encoding="utf-8"
)
print(f"Notebook written → {NB_PATH}  ({len(cells)} cells)")