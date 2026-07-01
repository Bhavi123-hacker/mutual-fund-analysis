-- ═══════════════════════════════════════════════════════════════════════
--  queries.sql
--  Bluestock Fintech — Mutual Fund Analysis  |  Day 2, Task 6
--  Database : bluestock_mf.db  (SQLite, star schema)
--  All 10 queries tested against real data on 2026-06-30
-- ═══════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────
-- Q1. TOP 5 FUNDS BY LATEST AUM
--     Source : fact_performance.aum_crore (as-of 2026-06-30 snapshot)
--     Use    : Fund sizing, product priority
-- ─────────────────────────────────────────────────────────────────────
SELECT f.scheme_name,
       f.fund_house,
       f.plan,
       ROUND(p.aum_crore, 2)   AS aum_crore
FROM   fact_performance p
JOIN   dim_fund f ON f.fund_key = p.fund_key
ORDER  BY p.aum_crore DESC
LIMIT  5;


-- ─────────────────────────────────────────────────────────────────────
-- Q2. AVERAGE NAV PER MONTH PER FUND
--     Source : fact_nav  (is_filled=0 → original published NAVs only)
--     Use    : Trend analysis, investor reporting
-- ─────────────────────────────────────────────────────────────────────
SELECT f.scheme_name,
       d.year,
       d.month_name,
       ROUND(AVG(n.nav), 4)  AS avg_nav,
       ROUND(MIN(n.nav), 4)  AS min_nav,
       ROUND(MAX(n.nav), 4)  AS max_nav
FROM   fact_nav n
JOIN   dim_fund f ON f.fund_key = n.fund_key
JOIN   dim_date d ON d.date_key = n.date_key
WHERE  n.is_filled = 0
GROUP  BY f.fund_key, d.year, d.month
ORDER  BY f.scheme_name, d.year, d.month;


-- ─────────────────────────────────────────────────────────────────────
-- Q3. SIP INFLOW YEAR-ON-YEAR GROWTH
--     Source : fact_transactions  (transaction_type = 'SIP')
--     Use    : Business momentum, investor acquisition trends
-- ─────────────────────────────────────────────────────────────────────
WITH yearly_sip AS (
    SELECT d.year,
           ROUND(SUM(t.amount) / 1e7, 2)  AS sip_crore
    FROM   fact_transactions t
    JOIN   dim_date d ON d.date_key = t.date_key
    WHERE  t.transaction_type = 'SIP'
    GROUP  BY d.year
)
SELECT year,
       sip_crore,
       ROUND(
           100.0 * (sip_crore - LAG(sip_crore) OVER (ORDER BY year))
                 / LAG(sip_crore) OVER (ORDER BY year),
       2) AS yoy_growth_pct
FROM   yearly_sip
ORDER  BY year;


-- ─────────────────────────────────────────────────────────────────────
-- Q4. TOTAL TRANSACTION VOLUME BY STATE
--     Source : fact_transactions
--     Use    : Geographic distribution, sales targeting
-- ─────────────────────────────────────────────────────────────────────
SELECT t.state,
       COUNT(*)                          AS txn_count,
       ROUND(SUM(t.amount)  / 1e5, 2)   AS total_amount_lakh,
       ROUND(AVG(t.amount), 2)           AS avg_ticket_size
FROM   fact_transactions t
GROUP  BY t.state
ORDER  BY total_amount_lakh DESC;


-- ─────────────────────────────────────────────────────────────────────
-- Q5. FUNDS WITH EXPENSE RATIO BELOW 1%
--     Source : dim_fund.expense_ratio_pct
--     Use    : Cost-efficiency screening for investors
-- ─────────────────────────────────────────────────────────────────────
SELECT f.scheme_name,
       f.fund_house,
       f.plan,
       f.expense_ratio_pct,
       f.sub_category
FROM   dim_fund f
WHERE  f.expense_ratio_pct < 1.0
ORDER  BY f.expense_ratio_pct ASC;


-- ─────────────────────────────────────────────────────────────────────
-- Q6. TOP 10 FUNDS BY 3-YEAR CAGR WITH ALPHA vs BENCHMARK
--     Source : fact_performance (outliers excluded via is_outlier flag)
--     Use    : Fund selection, performance attribution
-- ─────────────────────────────────────────────────────────────────────
SELECT f.scheme_name,
       f.fund_house,
       ROUND(p.return_3yr_pct,    2)  AS return_3yr_pct,
       ROUND(p.benchmark_3yr_pct, 2)  AS benchmark_3yr_pct,
       ROUND(p.alpha,             2)  AS alpha,
       p.morningstar_rating
FROM   fact_performance p
JOIN   dim_fund f ON f.fund_key = p.fund_key
WHERE  p.return_3yr_pct IS NOT NULL
  AND  p.is_outlier     = 0
ORDER  BY p.return_3yr_pct DESC
LIMIT  10;


-- ─────────────────────────────────────────────────────────────────────
-- Q7. TRANSACTION COUNT & AVERAGE TICKET BY TYPE AND KYC STATUS
--     Source : fact_transactions
--     Use    : Compliance monitoring, product mix analysis
-- ─────────────────────────────────────────────────────────────────────
SELECT t.transaction_type,
       t.kyc_status,
       COUNT(*)                        AS txn_count,
       ROUND(AVG(t.amount),    2)      AS avg_amount,
       ROUND(SUM(t.amount)/1e7, 2)     AS total_crore
FROM   fact_transactions t
GROUP  BY t.transaction_type, t.kyc_status
ORDER  BY t.transaction_type, t.kyc_status;


-- ─────────────────────────────────────────────────────────────────────
-- Q8. CATEGORY-LEVEL AVERAGE EXPENSE RATIO VS 1-YEAR RETURN
--     Source : dim_fund + fact_performance
--     Use    : Value-for-money analysis across fund categories
-- ─────────────────────────────────────────────────────────────────────
SELECT f.category,
       COUNT(DISTINCT f.fund_key)         AS num_schemes,
       ROUND(AVG(f.expense_ratio_pct), 3) AS avg_expense_ratio,
       ROUND(AVG(p.return_1yr_pct),    2) AS avg_1yr_return_pct,
       ROUND(AVG(p.sharpe_ratio),      3) AS avg_sharpe
FROM   dim_fund f
JOIN   fact_performance p ON p.fund_key = f.fund_key
WHERE  p.is_outlier = 0
GROUP  BY f.category
ORDER  BY avg_1yr_return_pct DESC;


-- ─────────────────────────────────────────────────────────────────────
-- Q9. AUM TREND BY FUND HOUSE — LATEST 6 MONTHS
--     Source : fact_aum + dim_date
--     Use    : Market share tracking, competitive intelligence
-- ─────────────────────────────────────────────────────────────────────
SELECT a.fund_house,
       d.year,
       d.month_name,
       ROUND(a.aum_crore / 1e5, 2)   AS aum_lakh_crore,
       a.num_schemes
FROM   fact_aum  a
JOIN   dim_date  d ON d.date_key = a.date_key
WHERE  d.date_key >= (SELECT MAX(date_key) - 200 FROM fact_aum)
ORDER  BY a.aum_crore DESC, d.year DESC, d.month DESC;


-- ─────────────────────────────────────────────────────────────────────
-- Q10. RISK-ADJUSTED PERFORMANCE LEADERBOARD (SHARPE & SORTINO)
--      Source : fact_performance (outliers excluded)
--      Use    : Portfolio construction, risk-adjusted fund ranking
-- ─────────────────────────────────────────────────────────────────────
SELECT f.scheme_name,
       f.fund_house,
       f.risk_category,
       ROUND(p.sharpe_ratio,     3)   AS sharpe_ratio,
       ROUND(p.sortino_ratio,    3)   AS sortino_ratio,
       ROUND(p.std_dev_ann_pct,  2)   AS std_dev_pct,
       ROUND(p.max_drawdown_pct, 2)   AS max_drawdown_pct,
       p.morningstar_rating
FROM   fact_performance p
JOIN   dim_fund f ON f.fund_key = p.fund_key
WHERE  p.is_outlier     = 0
  AND  p.sharpe_ratio  IS NOT NULL
ORDER  BY p.sharpe_ratio DESC
LIMIT  10;
