"""
B1_etl_cron.py
---------------------------------------------------------------
BONUS CHALLENGE 1 - Scheduled ETL: Live NAV Auto-Fetch
---------------------------------------------------------------
Fetches live NAV for all 40 schemes from mfapi.in every
weekday at 8:00 PM and upserts new records into bluestock_mf.db.

HOW TO RUN:
  python B1_etl_cron.py            # runs the scheduler (keeps running)
  python B1_etl_cron.py --now      # fetch immediately (useful for testing)

HOW TO SCHEDULE VIA CRON (Linux/Mac):
  crontab -e
  Add this line:
  0 20 * * 1-5 /usr/bin/python3 /path/to/B1_etl_cron.py --now >> /path/to/etl.log 2>&1

HOW TO SCHEDULE ON WINDOWS (Task Scheduler):
  - Action: python "C:\path\B1_etl_cron.py" --now
  - Trigger: Daily, 8:00 PM, Mon-Fri only
  - OR run: python B1_etl_cron.py  (keeps process alive with built-in scheduler)
---------------------------------------------------------------
"""

import sys
import time
import logging
import sqlite3
import argparse
import requests
import schedule
from datetime import datetime, date
from pathlib import Path

# -- Config ----------------------------------------------------------------
BASE    = Path(__file__).parent
DB_PATH = BASE / "bluestock_mf.db"
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

API_BASE   = "https://api.mfapi.in/mf"
TIMEOUT    = 15
RETRY      = 3
BACKOFF    = 2.0
RUN_TIME   = "20:00"   # 8:00 PM weekdays

# All 40 scheme codes in dim_fund
SCHEME_CODES: list[int] = []   # populated from DB at runtime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# -- Logging ---------------------------------------------------------------
log_file = LOG_DIR / f"etl_{date.today():%Y%m%d}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


# -- DB helpers ------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def load_scheme_codes() -> list[int]:
    """Read all amfi_codes from dim_fund."""
    conn = get_db_connection()
    rows = conn.execute("SELECT amfi_code FROM dim_fund ORDER BY amfi_code").fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_fund_key(conn: sqlite3.Connection, amfi_code: int) -> int | None:
    row = conn.execute(
        "SELECT fund_key FROM dim_fund WHERE amfi_code = ?", (amfi_code,)
    ).fetchone()
    return row[0] if row else None


def get_or_create_date_key(conn: sqlite3.Connection, dt: date) -> int:
    """Return existing date_key or insert a new dim_date row."""
    dk = int(dt.strftime("%Y%m%d"))
    exists = conn.execute("SELECT 1 FROM dim_date WHERE date_key=?", (dk,)).fetchone()
    if not exists:
        import calendar
        month_name = dt.strftime("%B")
        day_name   = dt.strftime("%A")
        is_weekend = 1 if dt.weekday() >= 5 else 0
        last_day   = calendar.monthrange(dt.year, dt.month)[1]
        is_month_end = 1 if dt.day == last_day else 0
        conn.execute("""
            INSERT OR IGNORE INTO dim_date
            (date_key,full_date,year,quarter,month,month_name,day,day_of_week,is_weekend,is_month_end)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (dk, dt.isoformat(), dt.year, (dt.month-1)//3+1,
              dt.month, month_name, dt.day, day_name, is_weekend, is_month_end))
    return dk


def upsert_nav(conn: sqlite3.Connection, fund_key: int,
               date_key: int, nav: float) -> str:
    """Insert if not exists. Returns 'inserted' or 'skipped'."""
    existing = conn.execute(
        "SELECT nav FROM fact_nav WHERE fund_key=? AND date_key=?",
        (fund_key, date_key)
    ).fetchone()
    if existing:
        return "skipped"
    conn.execute(
        "INSERT INTO fact_nav (fund_key, date_key, nav, is_filled) VALUES (?,?,?,0)",
        (fund_key, date_key, nav)
    )
    return "inserted"


# -- API fetch -------------------------------------------------------------
def fetch_latest_nav(amfi_code: int) -> dict | None:
    """
    Fetch the latest NAV from mfapi.in/mf/{code}.
    Returns {"date": date_obj, "nav": float} or None on failure.
    """
    url = f"{API_BASE}/{amfi_code}"
    for attempt in range(1, RETRY + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            nav_list = data.get("data", [])
            if not nav_list:
                log.warning("[%d] Empty data list", amfi_code)
                return None
            latest = nav_list[0]    # mfapi returns newest first
            nav_date = datetime.strptime(latest["date"], "%d-%m-%Y").date()
            nav_val  = float(latest["nav"])
            return {"date": nav_date, "nav": nav_val}
        except requests.exceptions.HTTPError as e:
            log.warning("[%d] HTTP %s (attempt %d/%d)", amfi_code,
                        e.response.status_code, attempt, RETRY)
            if e.response.status_code in (403, 404):
                return None
        except Exception as e:
            log.warning("[%d] Error (attempt %d/%d): %s", amfi_code, attempt, RETRY, e)
        if attempt < RETRY:
            time.sleep(BACKOFF * attempt)
    return None


# -- Core ETL --------------------------------------------------------------
def run_etl() -> None:
    today = datetime.today()
    if today.weekday() >= 5:   # Saturday=5, Sunday=6
        log.info("Weekend - skipping ETL run")
        return

    log.info("=" * 55)
    log.info("  ETL RUN STARTED  %s", today.strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 55)

    codes = load_scheme_codes()
    log.info("Schemes to fetch: %d", len(codes))

    inserted = skipped = failed = 0
    conn = get_db_connection()

    try:
        for code in codes:
            result = fetch_latest_nav(code)
            if result is None:
                failed += 1
                log.error("[%d] Fetch failed - skipping", code)
                continue

            fund_key = get_fund_key(conn, code)
            if fund_key is None:
                log.warning("[%d] Not in dim_fund - skipping", code)
                continue

            date_key = get_or_create_date_key(conn, result["date"])
            status   = upsert_nav(conn, fund_key, date_key, result["nav"])

            if status == "inserted":
                inserted += 1
                log.info("[%d]  [OK] NAV %.4f on %s - inserted",
                         code, result["nav"], result["date"])
            else:
                skipped += 1
                log.debug("[%d]  [SKIP] Already exists - skipped", code)

            time.sleep(0.3)   # polite rate limit

        conn.commit()

    except Exception as e:
        conn.rollback()
        log.exception("Unexpected error during ETL: %s", e)
    finally:
        conn.close()

    log.info("-" * 55)
    log.info("  Inserted: %d  |  Skipped: %d  |  Failed: %d",
             inserted, skipped, failed)
    log.info("  ETL RUN COMPLETE")
    log.info("-" * 55)


# -- Scheduler -------------------------------------------------------------
def start_scheduler() -> None:
    """Run ETL every weekday at 8 PM (keeps the process alive)."""
    log.info("Scheduler started - will run ETL at %s on weekdays", RUN_TIME)
    schedule.every().monday.at(RUN_TIME).do(run_etl)
    schedule.every().tuesday.at(RUN_TIME).do(run_etl)
    schedule.every().wednesday.at(RUN_TIME).do(run_etl)
    schedule.every().thursday.at(RUN_TIME).do(run_etl)
    schedule.every().friday.at(RUN_TIME).do(run_etl)

    while True:
        schedule.run_pending()
        time.sleep(30)


# -- Entry point -----------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bluestock NAV ETL Scheduler")
    parser.add_argument("--now", action="store_true",
                        help="Run ETL immediately instead of scheduling")
    args = parser.parse_args()

    if args.now:
        run_etl()
    else:
        start_scheduler()