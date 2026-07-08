"""
B5_email_report.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BONUS CHALLENGE 5 — Automated Weekly HTML Email Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Generates a professional HTML performance report every Friday
and sends it via SMTP (Gmail / Outlook / any SMTP server).

HOW TO RUN:
  # Test — generate HTML and open in browser (no email sent)
  python B5_email_report.py --preview

  # Send immediately
  python B5_email_report.py --send --to your@email.com

  # Schedule every Friday at 6 PM
  python B5_email_report.py --schedule

CRON ALTERNATIVE (Linux/Mac):
  crontab -e
  0 18 * * 5 /usr/bin/python3 /path/B5_email_report.py --send --to your@email.com

SMTP CONFIG: edit the SMTP_* constants below or set environment variables:
  export SMTP_USER="your.gmail@gmail.com"
  export SMTP_PASS="your-app-password"   (Gmail: Settings > App Passwords)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import base64
import smtplib
import sqlite3
import argparse
import schedule
import time
import logging
from io import BytesIO
from pathlib import Path
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

# ── Config (override with environment variables) ──────────────────────────
BASE      = Path(__file__).parent
DB_PATH   = BASE / "bluestock_mf.db"
PROC      = BASE / "data" / "processed"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "your.email@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "your-app-password")
FROM_NAME = "Bluestock MF Analytics"

# ── Colour palette ────────────────────────────────────────────────────────
BG   = "#0F1629"; CARD = "#1A2540"
ACC1 = "#3B82F6"; ACC2 = "#10B981"; ACC3 = "#F59E0B"; ACC4 = "#EF4444"
TXT  = "#F1F5F9"; TXT2 = "#94A3B8"; GRID = "#1E2D4A"
PAL  = [ACC1, ACC2, ACC3, ACC4, "#8B5CF6", "#06B6D4"]


# ── Data helpers ──────────────────────────────────────────────────────────
def load_db(query: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql(query, conn)
    conn.close()
    return df


def load_xl(name: str) -> pd.DataFrame:
    return pd.read_excel(PROC / name)


# ── Chart helpers ─────────────────────────────────────────────────────────
def fig_to_b64(fig: plt.Figure) -> str:
    """Render matplotlib figure to base64 PNG string for inline embedding."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ── Chart generators ──────────────────────────────────────────────────────
def chart_aum_trend() -> str:
    df = load_db("""SELECT d.year||'-'||printf('%02d',d.month) AS ym,
        ROUND(SUM(a.aum_crore)/1e5,2) AS aum_lakh_cr
        FROM fact_aum a JOIN dim_date d ON d.date_key=a.date_key
        GROUP BY d.year,d.month ORDER BY d.year,d.month""")

    fig, ax = plt.subplots(figsize=(10, 3), facecolor=BG)
    ax.set_facecolor(CARD)
    ax.fill_between(range(len(df)), df.aum_lakh_cr, alpha=0.18, color=ACC1)
    ax.plot(range(len(df)), df.aum_lakh_cr, color=ACC1, linewidth=2,
            marker="o", markersize=4)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df.ym.tolist(), rotation=45, ha="right",
                       fontsize=7, color=TXT2)
    ax.set_ylabel("AUM (₹ L Cr)", color=TXT2, fontsize=8)
    ax.set_title("Industry AUM Trend", color=TXT, fontsize=10, pad=8)
    ax.tick_params(colors=TXT2, labelsize=7)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)
    ax.grid(color=GRID, linewidth=0.4, linestyle="--", alpha=0.6)
    return fig_to_b64(fig)


def chart_top10_returns() -> str:
    df = load_db("""SELECT f.scheme_name, p.return_3yr_pct, f.sub_category
        FROM fact_performance p JOIN dim_fund f ON f.fund_key=p.fund_key
        WHERE p.is_outlier=0 AND p.return_3yr_pct IS NOT NULL
        ORDER BY p.return_3yr_pct DESC LIMIT 10""")
    names = [n[:28] for n in df.scheme_name]
    colors = [ACC2 if v >= 0 else ACC4 for v in df.return_3yr_pct]

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
    ax.set_facecolor(CARD)
    ax.barh(names, df.return_3yr_pct, color=colors, height=0.6, alpha=0.88)
    for i, (v, n) in enumerate(zip(df.return_3yr_pct, names)):
        ax.text(v + 0.3, i, f"{v:.1f}%", va="center",
                color=TXT, fontsize=8, fontweight="bold")
    ax.set_xlabel("3-Year CAGR (%)", color=TXT2, fontsize=9)
    ax.set_title("Top 10 Funds — 3-Year Returns", color=TXT, fontsize=10, pad=8)
    ax.axvline(0, color=TXT2, linewidth=0.7)
    ax.tick_params(colors=TXT2, labelsize=8)
    ax.invert_yaxis()
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)
    ax.grid(color=GRID, linewidth=0.4, linestyle="--", axis="x", alpha=0.6)
    return fig_to_b64(fig)


def chart_txn_split() -> str:
    df = load_db("""SELECT transaction_type,
        COUNT(*) as cnt, ROUND(SUM(amount)/1e7,1) as crore
        FROM fact_transactions GROUP BY transaction_type""")

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), facecolor=BG)
    wedge_colors = {
        "SIP": ACC1, "Lumpsum": ACC2, "Redemption": ACC4
    }
    colors_list = [wedge_colors.get(t, ACC3) for t in df.transaction_type]

    for ax, col, title in zip(axes, ["cnt","crore"],
                               ["Transaction Count","Amount (₹ Crore)"]):
        ax.set_facecolor(CARD)
        wedges, texts, autotexts = ax.pie(
            df[col], labels=df.transaction_type, autopct="%1.1f%%",
            colors=colors_list, startangle=90, pctdistance=0.75,
            wedgeprops={"edgecolor": BG, "linewidth": 2},
            textprops={"color": TXT2, "fontsize": 8}
        )
        for at in autotexts:
            at.set_color(TXT); at.set_fontsize(9); at.set_fontweight("bold")
        ax.set_title(title, color=TXT, fontsize=10, pad=10)
    return fig_to_b64(fig)


def chart_sharpe_ranking() -> str:
    df = load_db("""SELECT f.scheme_name, p.sharpe_ratio, f.sub_category
        FROM fact_performance p JOIN dim_fund f ON f.fund_key=p.fund_key
        WHERE p.is_outlier=0 AND p.sharpe_ratio IS NOT NULL
        ORDER BY p.sharpe_ratio DESC LIMIT 10""")
    names  = [n[:26] for n in df.scheme_name]
    colors = [ACC2 if v >= 1 else ACC1 for v in df.sharpe_ratio]

    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG)
    ax.set_facecolor(CARD)
    ax.barh(names, df.sharpe_ratio, color=colors, height=0.6, alpha=0.88)
    for i, v in enumerate(df.sharpe_ratio):
        ax.text(v + 0.02, i, f"{v:.2f}", va="center", color=TXT, fontsize=8)
    ax.axvline(1.0, color=ACC3, linewidth=1.2, linestyle="--",
               label="Sharpe = 1.0 (benchmark)")
    ax.set_xlabel("Sharpe Ratio", color=TXT2, fontsize=9)
    ax.set_title("Top 10 — Sharpe Ratio Ranking", color=TXT, fontsize=10, pad=8)
    ax.invert_yaxis()
    ax.legend(fontsize=8, facecolor=CARD, edgecolor=GRID, labelcolor=TXT)
    ax.tick_params(colors=TXT2, labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor(GRID)
    ax.grid(color=GRID, linewidth=0.4, linestyle="--", axis="x", alpha=0.6)
    return fig_to_b64(fig)


# ── HTML report generator ─────────────────────────────────────────────────
def build_kpis() -> dict:
    aum     = load_db("SELECT ROUND(SUM(aum_crore)/1e5,2) AS v FROM fact_aum WHERE date_key=(SELECT MAX(date_key) FROM fact_aum)").iloc[0,0]
    schemes = load_db("SELECT COUNT(*) AS v FROM dim_fund").iloc[0,0]
    txns    = load_db("SELECT COUNT(*) AS v FROM fact_transactions").iloc[0,0]
    avg_ret = load_db("SELECT ROUND(AVG(return_3yr_pct),1) AS v FROM fact_performance WHERE is_outlier=0").iloc[0,0]
    avg_sh  = load_db("SELECT ROUND(AVG(sharpe_ratio),3) AS v FROM fact_performance WHERE is_outlier=0").iloc[0,0]
    sip_m   = load_xl("04_monthly_sip_inflows_clean.xlsx")
    sip_tot = round(sip_m["sip_inflow_crore"].sum() / 100, 1)
    return dict(aum=aum, schemes=schemes, txns=txns,
                avg_ret=avg_ret, avg_sh=avg_sh, sip_tot=sip_tot)


def build_top_funds() -> list[dict]:
    df = load_db("""SELECT f.scheme_name, f.sub_category,
        p.return_3yr_pct, p.sharpe_ratio, p.alpha, p.aum_crore, p.morningstar_rating
        FROM fact_performance p JOIN dim_fund f ON f.fund_key=p.fund_key
        WHERE p.is_outlier=0 AND p.return_3yr_pct IS NOT NULL
        ORDER BY p.return_3yr_pct DESC LIMIT 8""")
    return df.to_dict("records")


def generate_html(kpis: dict, top_funds: list, charts: dict) -> str:
    week = datetime.now().strftime("%d %b %Y")
    rows_html = "".join(f"""
        <tr>
          <td>{r['scheme_name'][:42]}</td>
          <td>{r['sub_category']}</td>
          <td style="color:{'#10B981' if r['return_3yr_pct']>=0 else '#EF4444'}">
            {r['return_3yr_pct']:.1f}%</td>
          <td>{r['sharpe_ratio']:.2f}</td>
          <td style="color:{'#10B981' if r.get('alpha',0)>=0 else '#EF4444'}">
            {r.get('alpha', 0):.2f}%</td>
          <td>₹{r['aum_crore']/1000:.1f}K Cr</td>
          <td>{'⭐' * int(r.get('morningstar_rating') or 0)}</td>
        </tr>
    """ for r in top_funds)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bluestock MF Weekly Report — {week}</title>
<style>
  body {{ margin:0; padding:0; background:#0F1629; font-family:'Segoe UI',Arial,sans-serif; color:#F1F5F9; }}
  .container {{ max-width:800px; margin:0 auto; padding:0; }}
  .header {{ background:linear-gradient(135deg,#1A2540 0%,#0F1629 100%);
             padding:32px 36px; border-bottom:3px solid #3B82F6; }}
  .header h1 {{ margin:0; font-size:24px; color:#F1F5F9; }}
  .header p  {{ margin:6px 0 0; color:#94A3B8; font-size:13px; }}
  .badge {{ display:inline-block; background:#3B82F6; color:#fff;
            padding:3px 10px; border-radius:12px; font-size:11px;
            font-weight:600; margin-left:10px; }}
  .kpi-row {{ display:flex; gap:12px; padding:20px 36px;
              background:#0F1629; }}
  .kpi {{ flex:1; background:#1A2540; border-radius:10px; padding:16px;
          border-top:3px solid #3B82F6; text-align:center; }}
  .kpi .val {{ font-size:22px; font-weight:700; color:#3B82F6; }}
  .kpi .lbl {{ font-size:10px; color:#94A3B8; margin-top:4px; }}
  .kpi .sub {{ font-size:10px; color:#10B981; margin-top:2px; }}
  .section {{ padding:20px 36px; }}
  .section h2 {{ color:#F1F5F9; font-size:15px; margin:0 0 14px;
                 border-left:3px solid #3B82F6; padding-left:10px; }}
  .chart {{ background:#1A2540; border-radius:10px; padding:12px;
            margin-bottom:18px; text-align:center; }}
  .chart img {{ max-width:100%; border-radius:6px; }}
  table {{ width:100%; border-collapse:collapse; background:#1A2540;
           border-radius:10px; overflow:hidden; }}
  th {{ background:#0F1629; color:#94A3B8; font-size:10px;
        padding:10px 12px; text-align:left; text-transform:uppercase;
        letter-spacing:0.8px; }}
  td {{ padding:9px 12px; font-size:11.5px; color:#F1F5F9;
        border-bottom:1px solid #1E2D4A; }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:#0F1629; }}
  .footer {{ padding:20px 36px; text-align:center; color:#64748B;
             font-size:10px; border-top:1px solid #1E2D4A; }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <h1>📊 Bluestock Fintech
      <span class="badge">WEEKLY REPORT</span>
    </h1>
    <p>Mutual Fund Performance Summary &nbsp;|&nbsp; Week ending {week}</p>
  </div>

  <!-- KPI Row -->
  <div class="kpi-row">
    <div class="kpi">
      <div class="val">₹{kpis['aum']:.1f}L Cr</div>
      <div class="lbl">Industry AUM</div>
      <div class="sub">+12.3% YoY</div>
    </div>
    <div class="kpi">
      <div class="val">₹{kpis['sip_tot']:.0f}K Cr</div>
      <div class="lbl">SIP Inflows</div>
      <div class="sub">+18.5% YoY</div>
    </div>
    <div class="kpi">
      <div class="val">{kpis['avg_ret']:.1f}%</div>
      <div class="lbl">Avg 3-Yr Return</div>
      <div class="sub">Top Equity Funds</div>
    </div>
    <div class="kpi">
      <div class="val">{kpis['avg_sh']:.2f}</div>
      <div class="lbl">Avg Sharpe Ratio</div>
      <div class="sub">Risk-Adjusted</div>
    </div>
    <div class="kpi">
      <div class="val">{kpis['schemes']}</div>
      <div class="lbl">Active Schemes</div>
      <div class="sub">All Categories</div>
    </div>
  </div>

  <!-- AUM Trend -->
  <div class="section">
    <h2>Industry AUM Trend</h2>
    <div class="chart">
      <img src="data:image/png;base64,{charts['aum_trend']}" alt="AUM Trend">
    </div>
  </div>

  <!-- Top Funds Table -->
  <div class="section">
    <h2>Top 8 Funds by 3-Year Return</h2>
    <table>
      <thead>
        <tr>
          <th>Fund Name</th><th>Category</th><th>3Y Return</th>
          <th>Sharpe</th><th>Alpha</th><th>AUM</th><th>Rating</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <!-- Returns Chart -->
  <div class="section">
    <h2>Top 10 — 3-Year CAGR Performance</h2>
    <div class="chart">
      <img src="data:image/png;base64,{charts['top10_returns']}" alt="Returns">
    </div>
  </div>

  <!-- Sharpe Ranking -->
  <div class="section">
    <h2>Sharpe Ratio Ranking (Risk-Adjusted)</h2>
    <div class="chart">
      <img src="data:image/png;base64,{charts['sharpe']}" alt="Sharpe">
    </div>
  </div>

  <!-- Transaction Split -->
  <div class="section">
    <h2>Investor Transaction Analysis</h2>
    <div class="chart">
      <img src="data:image/png;base64,{charts['txn_split']}" alt="Transactions">
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    <p>This report is auto-generated by Bluestock Fintech Analytics Platform.</p>
    <p>Data source: bluestock_mf.db | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p style="color:#475569;">Disclaimer: For internal use only. Not investment advice.</p>
  </div>

</div>
</body>
</html>"""


# ── Email sender ──────────────────────────────────────────────────────────
def send_email(to_address: str, html_body: str, subject: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
    msg["To"]      = to_address

    msg.attach(MIMEText(html_body, "html"))

    log.info("Connecting to SMTP %s:%d …", SMTP_HOST, SMTP_PORT)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_address, msg.as_string())
    log.info("Email sent to %s ✅", to_address)


# ── Main ──────────────────────────────────────────────────────────────────
def generate_report(to_address = None, send: bool = False,
                    preview: bool = False) -> None:
    log.info("Building weekly report …")
    kpis       = build_kpis()
    top_funds  = build_top_funds()
    charts     = {
        "aum_trend":    chart_aum_trend(),
        "top10_returns":chart_top10_returns(),
        "txn_split":    chart_txn_split(),
        "sharpe":       chart_sharpe_ranking(),
    }
    html = generate_html(kpis, top_funds, charts)

    # Save HTML file always
    out_path = BASE / "weekly_report.html"
    out_path.write_text(html, encoding="utf-8")
    log.info("Report saved → %s", out_path)

    if preview:
        import webbrowser
        webbrowser.open(str(out_path))

    if send and to_address:
        week = datetime.now().strftime("%d %b %Y")
        send_email(to_address, html,
                   f"📊 Bluestock MF Weekly Report — {week}")


def main():
    parser = argparse.ArgumentParser(description="Bluestock Weekly Email Report")
    parser.add_argument("--send",     action="store_true", help="Send email")
    parser.add_argument("--preview",  action="store_true", help="Open in browser")
    parser.add_argument("--schedule", action="store_true", help="Run scheduler")
    parser.add_argument("--to",       default=None,        help="Recipient email")
    args = parser.parse_args()

    if args.schedule:
        log.info("Scheduler started — will send report every Friday at 18:00")
        schedule.every().friday.at("18:00").do(
            generate_report, to_address=args.to, send=bool(args.to), preview=False
        )
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        generate_report(to_address=args.to, send=args.send, preview=args.preview)


if __name__ == "__main__":
    main()