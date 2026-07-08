"""
B2_streamlit_app.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BONUS CHALLENGE 2 — Streamlit Web App (Power BI Alternative)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO RUN:
  pip install streamlit plotly pandas sqlalchemy
  streamlit run B2_streamlit_app.py

Then open: http://localhost:8501
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bluestock MF Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bluestock theme CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0F1629; color: #F1F5F9; }
    .main .block-container { padding-top: 1rem; }
    [data-testid="stSidebar"] { background-color: #1A2540; }
    h1,h2,h3 { color: #F1F5F9; }
    .metric-card {
        background: #1A2540; border-radius: 10px; padding: 18px 22px;
        border-left: 4px solid #3B82F6; margin-bottom: 12px;
    }
    .metric-val  { font-size: 28px; font-weight: 700; color: #3B82F6; }
    .metric-lbl  { font-size: 12px; color: #94A3B8; margin-bottom: 4px; }
    .metric-sub  { font-size: 11px; color: #10B981; }
    div[data-testid="stMetric"] { background:#1A2540; border-radius:8px; padding:12px; }
    div[data-testid="stMetric"] label { color:#94A3B8 !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color:#3B82F6 !important; }
</style>
""", unsafe_allow_html=True)

# ── Database connection ────────────────────────────────────────────────────
BASE    = Path(__file__).parent
DB_PATH = BASE / "bluestock_mf.db"
PROC    = BASE / "data" / "processed"


@st.cache_resource
def get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=300)
def load_table(query: str) -> pd.DataFrame:
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql(query, conn)
    conn.close()
    return df


@st.cache_data(ttl=300)
def load_excel(filename: str) -> pd.DataFrame:
    return pd.read_excel(PROC / filename)


# ── PLOTLY template ────────────────────────────────────────────────────────
TEMPLATE = dict(
    layout=go.Layout(
        paper_bgcolor="#1A2540",
        plot_bgcolor="#0F1629",
        font=dict(color="#F1F5F9", size=11),
        xaxis=dict(gridcolor="#1E2D4A", linecolor="#1E2D4A"),
        yaxis=dict(gridcolor="#1E2D4A", linecolor="#1E2D4A"),
        colorway=["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6",
                  "#06B6D4","#F97316","#EC4899"],
    )
)

# ── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 Bluestock Fintech")
    st.markdown("*Mutual Fund Analysis Platform*")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["🏭 Industry Overview",
         "📈 Fund Performance",
         "👥 Investor Analytics",
         "📉 SIP & Market Trends"],
    )
    st.markdown("---")
    st.markdown("**Data Source**")
    st.caption("bluestock_mf.db | 40 schemes | 64K+ NAV rows")

# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 — INDUSTRY OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
if page == "🏭 Industry Overview":
    st.markdown("# 🏭 Industry Overview")

    # KPI data
    aum_df = load_table("""
        SELECT fund_house, SUM(aum_crore) AS aum_crore,
               SUM(num_schemes) AS schemes, date_key
        FROM fact_aum
        WHERE date_key = (SELECT MAX(date_key) FROM fact_aum)
        GROUP BY fund_house
    """)
    total_aum   = aum_df.aum_crore.sum() / 1e5
    n_schemes   = load_table("SELECT COUNT(*) AS n FROM dim_fund").iloc[0,0]
    sip_data    = load_excel("04_monthly_sip_inflows_clean.xlsx")
    latest_sip  = sip_data["sip_inflow_crore"].iloc[-1] / 100

    # ── KPI Cards ──────────────────────────────────────────────────────────
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("💰 Total AUM",      f"₹{total_aum:.1f}L Cr",   "+12.3% YoY")
    c2.metric("📥 SIP Inflows",    f"₹{latest_sip:.0f}K Cr",  "+18.5% YoY")
    c3.metric("📁 Active Folios",  "26.12 Cr",                "+9.2% YoY")
    c4.metric("🏷 Total Schemes",  str(n_schemes),            "Active")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    # ── AUM Trend ──────────────────────────────────────────────────────────
    with col_left:
        st.markdown("### Industry AUM Trend")
        aum_trend = load_table("""
            SELECT d.year||'-'||printf('%02d',d.month) AS ym,
                   ROUND(SUM(a.aum_crore)/1e5,2) AS aum_lakh_cr
            FROM fact_aum a JOIN dim_date d ON d.date_key=a.date_key
            GROUP BY d.year,d.month ORDER BY d.year,d.month
        """)
        fig = px.area(aum_trend, x="ym", y="aum_lakh_cr",
                      labels={"ym":"Month","aum_lakh_cr":"AUM (₹ L Cr)"},
                      color_discrete_sequence=["#3B82F6"])
        fig.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                          height=300, showlegend=False)
        fig.update_traces(fillcolor="rgba(59,130,246,0.15)")
        st.plotly_chart(fig, width="stretch")

    # ── AUM by AMC ─────────────────────────────────────────────────────────
    with col_right:
        st.markdown("### AUM by AMC")
        aum_by_amc = load_table("""
            SELECT fund_house, ROUND(SUM(aum_crore)/1e3,1) AS aum_k_cr
            FROM fact_aum WHERE date_key=(SELECT MAX(date_key) FROM fact_aum)
            GROUP BY fund_house ORDER BY aum_k_cr DESC
        """)
        short_names = [n.replace(" Mutual Fund","").replace(" MF","")
                         .replace(" Prudential","")[:18]
                       for n in aum_by_amc.fund_house]
        fig2 = px.bar(aum_by_amc, x="aum_k_cr", y=short_names,
                      orientation="h",
                      labels={"x":"AUM (₹ '000 Cr)","y":"AMC"},
                      color="aum_k_cr", color_continuous_scale="Blues")
        fig2.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=300, showlegend=False,
                           coloraxis_showscale=False, yaxis={"autorange":"reversed"})
        st.plotly_chart(fig2, width="stretch")

    st.markdown("---")
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("### AUM by Category")
        perf = load_table("""SELECT f.sub_category, SUM(p.aum_crore) AS aum
            FROM fact_performance p JOIN dim_fund f ON f.fund_key=p.fund_key
            WHERE p.is_outlier=0 GROUP BY f.sub_category""")
        fig3 = px.pie(perf, names="sub_category", values="aum", hole=0.5,
                      color_discrete_sequence=px.colors.qualitative.Bold)
        fig3.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=300, legend=dict(font=dict(size=10)))
        st.plotly_chart(fig3, width="stretch")

    with col4:
        st.markdown("### Risk Category Distribution")
        risk = load_table("""SELECT risk_category, COUNT(*) AS count
            FROM dim_fund GROUP BY risk_category ORDER BY count DESC""")
        fig4 = px.bar(risk, x="risk_category", y="count",
                      color="risk_category",
                      color_discrete_sequence=["#10B981","#3B82F6","#F59E0B","#EF4444"])
        fig4.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=300, showlegend=False)
        st.plotly_chart(fig4, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# PAGE 2 — FUND PERFORMANCE
# ════════════════════════════════════════════════════════════════════════════
elif page == "📈 Fund Performance":
    st.markdown("# 📈 Fund Performance")

    # ── Slicers ────────────────────────────────────────────────────────────
    fund_houses = load_table("SELECT DISTINCT fund_house FROM dim_fund ORDER BY fund_house")
    categories  = load_table("SELECT DISTINCT sub_category FROM dim_fund ORDER BY sub_category")
    plans       = ["All","Direct","Regular"]

    s1, s2, s3 = st.columns(3)
    sel_house = s1.selectbox("Fund House", ["All"] + fund_houses.fund_house.tolist())
    sel_cat   = s2.selectbox("Sub-Category", ["All"] + categories.sub_category.tolist())
    sel_plan  = s3.selectbox("Plan", plans)

    # ── Performance data ───────────────────────────────────────────────────
    perf = load_table("""
        SELECT f.scheme_name, f.fund_house, f.sub_category, f.plan,
               f.expense_ratio_pct, p.return_1yr_pct, p.return_3yr_pct,
               p.return_5yr_pct, p.sharpe_ratio, p.sortino_ratio,
               p.alpha, p.beta, p.std_dev_ann_pct,
               p.max_drawdown_pct, p.aum_crore, p.morningstar_rating
        FROM fact_performance p JOIN dim_fund f ON f.fund_key=p.fund_key
        WHERE p.is_outlier=0
    """)

    # Apply filters
    if sel_house != "All": perf = perf[perf.fund_house == sel_house]
    if sel_cat   != "All": perf = perf[perf.sub_category == sel_cat]
    if sel_plan  != "All": perf = perf[perf.plan == sel_plan]

    # ── KPI row ────────────────────────────────────────────────────────────
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Avg 3yr Return", f"{perf.return_3yr_pct.mean():.1f}%")
    k2.metric("Avg Sharpe",     f"{perf.sharpe_ratio.mean():.2f}")
    k3.metric("Avg Alpha",      f"{perf.alpha.mean():.2f}%")
    k4.metric("Avg Max DD",     f"{perf.max_drawdown_pct.mean():.1f}%")

    st.markdown("---")
    col1, col2 = st.columns([3, 2])

    # ── Risk vs Return Scatter ──────────────────────────────────────────────
    with col1:
        st.markdown("### Risk vs Return (Scatter)")
        fig = px.scatter(
            perf.dropna(subset=["std_dev_ann_pct","return_3yr_pct","aum_crore"]),
            x="return_3yr_pct", y="std_dev_ann_pct",
            size="aum_crore", color="sub_category",
            hover_name="scheme_name",
            hover_data={"sharpe_ratio":":.2f","alpha":":.2f",
                        "expense_ratio_pct":":.2f"},
            labels={"return_3yr_pct":"3-Year Return (%)",
                    "std_dev_ann_pct":"Annual Std Dev (%)"},
            size_max=40,
        )
        fig.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                          height=380)
        st.plotly_chart(fig, width="stretch")

    # ── Sharpe Ranking ─────────────────────────────────────────────────────
    with col2:
        st.markdown("### Sharpe Ratio Ranking")
        top_sh = perf.nlargest(12,"sharpe_ratio")[["scheme_name","sharpe_ratio","sub_category"]]
        top_sh["name"] = top_sh.scheme_name.str[:28]
        fig2 = px.bar(top_sh.sort_values("sharpe_ratio"), x="sharpe_ratio", y="name",
                      orientation="h", color="sub_category",
                      labels={"sharpe_ratio":"Sharpe Ratio","name":""})
        fig2.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=380, showlegend=False)
        st.plotly_chart(fig2, width="stretch")

    # ── Sortable Fund Scorecard Table ──────────────────────────────────────
    st.markdown("### 📋 Fund Scorecard Table")
    show_cols = ["scheme_name","fund_house","sub_category","plan",
                 "return_1yr_pct","return_3yr_pct","sharpe_ratio",
                 "alpha","expense_ratio_pct","max_drawdown_pct","morningstar_rating"]
    display_df = perf[show_cols].rename(columns={
        "scheme_name":"Scheme","fund_house":"AMC","sub_category":"Category",
        "plan":"Plan","return_1yr_pct":"1Y Ret%","return_3yr_pct":"3Y Ret%",
        "sharpe_ratio":"Sharpe","alpha":"Alpha%",
        "expense_ratio_pct":"TER%","max_drawdown_pct":"Max DD%",
        "morningstar_rating":"⭐ Rating"
    }).sort_values("3Y Ret%", ascending=False).round(2)

    st.dataframe(
        display_df.style
            .background_gradient(subset=["3Y Ret%"], cmap="RdYlGn")
            .background_gradient(subset=["Sharpe"],  cmap="Blues")
            .background_gradient(subset=["Max DD%"], cmap="RdYlGn_r"),
        height=400, use_container_width=True
    )

    # ── NAV Line Chart ─────────────────────────────────────────────────────
    st.markdown("### 📈 NAV History — Large Cap Direct Funds")
    nav = load_table("""
        SELECT f.scheme_name, d.full_date AS date, n.nav
        FROM fact_nav n JOIN dim_fund f ON f.fund_key=n.fund_key
        JOIN dim_date d ON d.date_key=n.date_key
        WHERE f.sub_category='Large Cap' AND f.plan='Direct'
          AND n.is_filled=0 AND d.full_date >= '2023-01-01'
        ORDER BY f.scheme_name, d.full_date
    """)
    if not nav.empty:
        fig_nav = px.line(nav, x="date", y="nav", color="scheme_name",
                          labels={"nav":"NAV (₹)","date":"Date","scheme_name":"Fund"},
                          color_discrete_sequence=["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6"])
        fig_nav.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                              height=350, legend=dict(font=dict(size=9)))
        st.plotly_chart(fig_nav, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# PAGE 3 — INVESTOR ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
elif page == "👥 Investor Analytics":
    st.markdown("# 👥 Investor Analytics")

    # ── Slicers ────────────────────────────────────────────────────────────
    states     = load_table("SELECT DISTINCT state FROM fact_transactions WHERE state IS NOT NULL ORDER BY state")
    age_groups = load_table("SELECT DISTINCT age_group FROM fact_transactions WHERE age_group IS NOT NULL ORDER BY age_group")
    city_tiers = load_table("SELECT DISTINCT city_tier FROM fact_transactions WHERE city_tier IS NOT NULL ORDER BY city_tier")

    s1,s2,s3 = st.columns(3)
    sel_state = s1.selectbox("State", ["All"] + states.state.tolist())
    sel_age   = s2.selectbox("Age Group", ["All"] + age_groups.age_group.tolist())
    sel_tier  = s3.selectbox("City Tier", ["All"] + city_tiers.city_tier.tolist())

    # Build WHERE clause
    filters = []
    if sel_state != "All": filters.append(f"state='{sel_state}'")
    if sel_age   != "All": filters.append(f"age_group='{sel_age}'")
    if sel_tier  != "All": filters.append(f"city_tier='{sel_tier}'")
    where = "WHERE " + " AND ".join(filters) if filters else ""

    # ── KPIs ───────────────────────────────────────────────────────────────
    txn_kpi = load_table(f"""
        SELECT transaction_type, COUNT(*) as cnt, SUM(amount)/1e7 as crore
        FROM fact_transactions {where} GROUP BY transaction_type
    """)
    total_txn  = txn_kpi.cnt.sum()
    total_cr   = txn_kpi.crore.sum()
    sip_share  = txn_kpi[txn_kpi.transaction_type=="SIP"]["crore"].sum() / total_cr * 100 if total_cr else 0
    kyc_pct = load_table(f"""
        SELECT ROUND(100.0*SUM(CASE WHEN kyc_status='Verified' THEN 1 ELSE 0 END)/COUNT(*),1) AS pct
        FROM fact_transactions {where}
    """).iloc[0,0]

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Total Transactions", f"{int(total_txn):,}")
    k2.metric("Total Inflow",       f"₹{total_cr:.1f} Cr")
    k3.metric("SIP Share",          f"{sip_share:.1f}%")
    k4.metric("KYC Verified",       f"{kyc_pct:.1f}%")

    st.markdown("---")
    col1, col2 = st.columns([2,1])

    # ── Transactions by State ──────────────────────────────────────────────
    with col1:
        st.markdown("### Transaction Amount by State (₹ Crore)")
        state_txn = load_table(f"""
            SELECT state, ROUND(SUM(amount)/1e7,2) as crore, COUNT(*) as cnt
            FROM fact_transactions {where}
            GROUP BY state ORDER BY crore DESC
        """)
        fig = px.bar(state_txn, x="crore", y="state", orientation="h",
                     color="crore", color_continuous_scale="Blues",
                     labels={"crore":"Amount (₹ Cr)","state":"State"},
                     hover_data={"cnt":True})
        fig.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                          height=400, coloraxis_showscale=False,
                          yaxis={"autorange":"reversed"})
        st.plotly_chart(fig, width="stretch")

    # ── Transaction Type Donut ──────────────────────────────────────────────
    with col2:
        st.markdown("### SIP / Lumpsum / Redemption Split")
        fig2 = px.pie(txn_kpi, names="transaction_type", values="crore",
                      hole=0.5,
                      color_discrete_map={"SIP":"#3B82F6",
                                          "Lumpsum":"#10B981",
                                          "Redemption":"#EF4444"})
        fig2.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=300)
        st.plotly_chart(fig2, width="stretch")

    st.markdown("---")
    col3, col4 = st.columns(2)

    # ── Age Group vs Avg SIP ───────────────────────────────────────────────
    with col3:
        st.markdown("### Avg SIP Amount by Age Group")
        age_sip = load_table(f"""
            SELECT age_group, ROUND(AVG(amount),0) as avg_amt, COUNT(*) as cnt
            FROM fact_transactions
            WHERE transaction_type='SIP' AND age_group IS NOT NULL
            {'AND ' + ' AND '.join(filters) if filters else ''}
            GROUP BY age_group ORDER BY age_group
        """)
        fig3 = px.bar(age_sip, x="age_group", y="avg_amt",
                      color="avg_amt", color_continuous_scale="Teal",
                      labels={"age_group":"Age Group","avg_amt":"Avg SIP (₹)"},
                      text="avg_amt")
        fig3.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside")
        fig3.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=300, coloraxis_showscale=False)
        st.plotly_chart(fig3, width="stretch")

    # ── Monthly Transaction Volume ─────────────────────────────────────────
    with col4:
        st.markdown("### Monthly Transaction Volume")
        monthly = load_table(f"""
            SELECT d.year||'-'||printf('%02d',d.month) AS ym,
                   t.transaction_type, COUNT(*) as cnt
            FROM fact_transactions t JOIN dim_date d ON d.date_key=t.date_key
            {where.replace('WHERE','WHERE') if where else 'WHERE 1=1'}
            {'AND ' + ' AND '.join(filters) if filters else ''}
            GROUP BY ym, t.transaction_type ORDER BY ym
        """)
        if not monthly.empty:
            fig4 = px.line(monthly, x="ym", y="cnt", color="transaction_type",
                           color_discrete_map={"SIP":"#3B82F6","Lumpsum":"#10B981","Redemption":"#EF4444"},
                           labels={"ym":"Month","cnt":"Transactions","transaction_type":"Type"})
            fig4.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                               height=300, legend=dict(font=dict(size=9)))
            st.plotly_chart(fig4, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SIP & Market Trends
# ════════════════════════════════════════════════════════════════════════════
elif page == "📉 SIP & Market Trends":
    st.markdown("# 📉 SIP & Market Trends")

    sip_m   = load_excel("04_monthly_sip_inflows_clean.xlsx")
    cat_i   = load_excel("05_category_inflows_clean.xlsx")
    bench   = load_excel("10_benchmark_indices_clean.xlsx")
    if "date" in bench.columns:
        bench["date"] = pd.to_datetime(bench["date"])
    
    # Corrected schema for benchmark index and values
    n50 = bench[bench["index_name"]=="NIFTY50"][["date","close_value"]].set_index("date")["close_value"]

    # Align SIP months with Nifty dates (safely handling pre-parsed datetime columns)
    sip_m["month"] = pd.to_datetime(sip_m["month"])

    # ── KPIs ───────────────────────────────────────────────────────────────
    # Corrected schema for SIP and category inflows
    total_sip = sip_m.sip_inflow_crore.sum()
    best_cat  = cat_i.groupby("category")["net_inflow_crore"].sum().idxmax()
    top_cat_cr = cat_i.groupby("category")["net_inflow_crore"].sum().max()

    k1,k2,k3 = st.columns(3)
    k1.metric("Total SIP Inflow",    f"₹{total_sip/100:.0f}K Cr")
    k2.metric("Best Category",       best_cat)
    k3.metric("Top Category Inflow", f"₹{top_cat_cr:.0f} Cr")

    st.markdown("---")

    # ── Dual-Axis: SIP + Nifty 50 ─────────────────────────────────────────
    st.markdown("### SIP Inflows (₹ Cr) vs Nifty 50 — Monthly")
    n50_monthly = n50.resample("MS").last().reset_index()
    n50_monthly.columns = ["month","nifty"]
    merged = sip_m.merge(n50_monthly, on="month", how="inner")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # Corrected column reference inside the chart
    fig.add_trace(go.Bar(x=merged.month, y=merged.sip_inflow_crore,
                         name="SIP Inflow (₹ Cr)", marker_color="#3B82F6",
                         opacity=0.8), secondary_y=False)
    fig.add_trace(go.Scatter(x=merged.month, y=merged.nifty,
                             name="Nifty 50", line=dict(color="#F59E0B", width=2)),
                  secondary_y=True)
    fig.update_layout(
        paper_bgcolor="#1A2540", plot_bgcolor="#0F1629",
        font=dict(color="#F1F5F9"), height=380,
        legend=dict(orientation="h", y=1.1),
        yaxis=dict(title="SIP Inflow (₹ Cr)", gridcolor="#1E2D4A"),
        yaxis2=dict(title="Nifty 50", gridcolor="#1E2D4A"),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    col1, col2 = st.columns(2)

    # ── Category Inflow Heatmap ────────────────────────────────────────────
    with col1:
        st.markdown("### Category Net Inflow Heatmap (₹ Cr)")
        heat = cat_i.copy()
        heat["ym"] = heat["month"].astype(str).str[:7]
        # Corrected column reference
        pivot = heat.pivot_table(index="category", columns="ym",
                                 values="net_inflow_crore", aggfunc="sum").fillna(0)
        fig2 = px.imshow(pivot, color_continuous_scale="RdYlGn",
                         labels=dict(color="Net Inflow (₹ Cr)"),
                         aspect="auto")
        fig2.update_layout(paper_bgcolor="#1A2540", plot_bgcolor="#1A2540",
                           font=dict(color="#F1F5F9", size=9), height=350)
        st.plotly_chart(fig2, width="stretch")

    # ── Top 5 Categories by Net Inflow ────────────────────────────────────
    with col2:
        st.markdown("### Top Categories by Net Inflow (All-Time)")
        # Corrected column reference
        cat_sum = cat_i.groupby("category")["net_inflow_crore"].sum().nlargest(7).reset_index()
        fig3 = px.bar(cat_sum, x="net_inflow_crore", y="category",
                      orientation="h", color="net_inflow_crore",
                      color_continuous_scale="Greens",
                      labels={"net_inflow_crore":"Net Inflow (₹ Cr)","category":"Category"})
        fig3.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]),
                           height=350, coloraxis_showscale=False,
                           yaxis={"autorange":"reversed"})
        st.plotly_chart(fig3, width="stretch")

    # ── SIP accounts trend ────────────────────────────────────────────────
    st.markdown("### SIP Account Base Growth")
    fig4 = px.area(sip_m, x="month", y="active_sip_accounts_crore",
                   labels={"month":"Month","active_sip_accounts_crore":"Active SIP Accounts (Cr)"},
                   color_discrete_sequence=["#10B981"])
    fig4.update_traces(fillcolor="rgba(16,185,129,0.15)")
    fig4.update_layout(template=go.layout.Template(layout=TEMPLATE["layout"]), height=280)
    st.plotly_chart(fig4, width="stretch")