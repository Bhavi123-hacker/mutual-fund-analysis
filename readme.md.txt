# 📈 Bluestock Mutual Fund Analytics Capstone Project

## Project Overview

This project is a complete end-to-end Mutual Fund Analytics platform developed as part of the Bluestock Data Analytics Capstone.

The project covers the complete analytics pipeline, including:

- Data ingestion
- Data cleaning
- SQLite database creation
- Exploratory Data Analysis (EDA)
- Performance analytics
- Advanced financial analytics
- Interactive Power BI dashboard
- Streamlit dashboard
- Automated ETL scheduling
- Monte Carlo simulation
- Portfolio optimization
- Automated weekly HTML email reports

---

# Project Objectives

- Analyze Indian Mutual Fund industry data
- Build an automated ETL pipeline
- Store processed data in SQLite
- Perform advanced financial analytics
- Develop interactive dashboards
- Generate business insights for investors

---

# Project Structure

```
bluestock_mf_capstone/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── db/
│       └── bluestock_mf.db
│
├── notebooks/
│   ├── 01_data_ingestion.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_eda_analysis.ipynb
│   ├── 04_performance_analytics.ipynb
│   └── 05_advanced_analytics.ipynb
│
├── scripts/
│   ├── etl_pipeline.py
│   ├── live_nav_fetch.py
│   ├── compute_metrics.py
│   └── recommender.py
│
├── sql/
│   ├── schema.sql
│   └── queries.sql
│
├── dashboard/
│   └── bluestock_mf.pbix
│
├── reports/
│   ├── Final_Report.pdf
│   ├── Presentation.pptx
│   ├── Dashboard.pdf
│   └── PNG Screenshots
│
├── README.md
└── requirements.txt
```

---

# Technologies Used

- Python 3.12
- Pandas
- NumPy
- Matplotlib
- Plotly
- SQLite
- SQLAlchemy
- Power BI
- Streamlit
- Jupyter Notebook
- Git
- GitHub

---

# Dataset

The project uses multiple Mutual Fund datasets including:

- Fund Master
- NAV History
- AUM Data
- SIP Inflows
- Category Inflows
- Industry Folios
- Scheme Performance
- Investor Transactions
- Expense Ratio
- Benchmark Data

---

# Features

## ETL Pipeline

- Automated data ingestion
- Data validation
- Missing value handling
- Weekend NAV forward filling
- Clean processed datasets

---

## Database

SQLite database containing cleaned Mutual Fund datasets with relational schema.

---

## Exploratory Data Analysis

Includes:

- Fund category analysis
- AUM analysis
- NAV trends
- Investor behaviour
- Category inflows
- Performance distribution

---

## Performance Analytics

Implemented metrics:

- CAGR
- Annualized Return
- Volatility
- Sharpe Ratio
- Sortino Ratio
- Alpha
- Beta
- Maximum Drawdown
- Historical VaR
- Conditional VaR (CVaR)

---

## Advanced Analytics

- Historical VaR Analysis
- Rolling Sharpe Ratio
- Investor Cohort Analysis
- SIP Continuity Analysis
- Risk-based Fund Recommendation System
- Sector HHI Concentration Analysis

---

# Interactive Dashboard (Power BI)

The dashboard contains four pages.

### Page 1

Industry Overview

- KPI Cards
- Industry AUM Trend
- AUM by AMC
- Interactive slicers

---

### Page 2

Fund Performance

- Risk vs Return Scatter Plot
- Fund Scorecard
- NAV Trend
- Performance Filters

---

### Page 3

Investor Analytics

- Transaction by State
- SIP/Lumpsum Distribution
- Average SIP by Age Group
- Monthly Transaction Trends

---

### Page 4

SIP & Market Trends

- SIP Inflow Trends
- Category Inflow Heatmap
- Top Categories
- Market Trend Analysis

---

# Bonus Challenges

## B1

Automated ETL Scheduler

- Fetches NAV from mfapi.in
- Runs every weekday

---

## B2

Streamlit Dashboard

Alternative interactive dashboard built using Streamlit.

Run using:

```bash
streamlit run B2_streamlit_app.py
```

---

## B3

Monte Carlo Simulation

Projects NAV growth over 5 years using stochastic simulation.

Output:

- Monte Carlo Chart
- Simulation CSV

---

## B4

Markowitz Portfolio Optimization

Generates:

- Efficient Frontier
- Maximum Sharpe Portfolio
- Minimum Variance Portfolio

---

## B5

Automated HTML Email Report

Generates weekly investment summary reports.

Supports:

- HTML Preview
- Email Delivery
- Scheduled Reports

---

# Installation

Clone repository

```bash
git clone <repository-url>
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running the Project

## ETL Pipeline

```bash
python etl_pipeline.py
```

---

## Live NAV Fetch

```bash
python live_nav_fetch.py
```

---

## Performance Metrics

```bash
python compute_metrics.py
```

---

## Fund Recommender

```bash
python recommender.py
```

---

## Streamlit Dashboard

```bash
streamlit run B2_streamlit_app.py
```

---

# Deliverables

- ETL Pipeline
- SQLite Database
- EDA Notebook
- Performance Analytics
- Power BI Dashboard
- Advanced Analytics
- Final Report
- Presentation
- Streamlit Dashboard
- Bonus Challenges

---

# Key Insights

- Industry AUM growth trends analyzed over multiple years.
- Fund performance evaluated using modern financial metrics.
- Investor behaviour analyzed across demographics and transaction patterns.
- Portfolio optimization performed using Markowitz Efficient Frontier.
- Risk quantified through VaR and Monte Carlo simulations.

---

# Author

**Bhavy Garg**

Bluestock Mutual Fund Analytics Capstone Project

2026