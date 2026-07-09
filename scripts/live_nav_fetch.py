"""
live_nav_fetch.py
─────────────────────────────────────────────────────────────────────────────
Day 1 · Mutual Fund Analysis Pipeline
Tasks  : Fetch live + historical NAV from mfapi.in for 6 key schemes.
         Save raw JSON + clean CSV per scheme; print latest NAV snapshot.

Schemes :
  125497 — HDFC Top 100 Direct
  119551 — SBI Bluechip Direct
  120503 — ICICI Bluechip Direct
  118632 — Nippon Large Cap Direct
  119092 — Axis Bluechip Direct
  120841 — Kotak Bluechip Direct

Usage   : python live_nav_fetch.py [--schemes 125497 119551 ...]
          python live_nav_fetch.py --latest-only      # skip full history
Output  : data/raw/nav_{code}_{name}.json
          data/raw/nav_{code}_{name}.csv
          data/raw/nav_snapshot_live.csv              # merged latest NAVs
─────────────────────────────────────────────────────────────────────────────
"""

import csv
import json
import logging
import argparse
import time
from datetime import datetime
from pathlib import Path

import requests
import pandas as pd

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent
RAW_DIR = BASE / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Scheme Registry ───────────────────────────────────────────────────────────
SCHEME_REGISTRY: dict[int, str] = {
    125497: "HDFC_Top100_Direct",
    119551: "SBI_Bluechip",
    120503: "ICICI_Bluechip",
    118632: "Nippon_LargeCap",
    119092: "Axis_Bluechip",
    120841: "Kotak_Bluechip",
}

# ── API Config ────────────────────────────────────────────────────────────────
BASE_URL       = "https://api.mfapi.in/mf"
REQUEST_TIMEOUT = 15          # seconds
RETRY_LIMIT     = 3
RETRY_BACKOFF   = 2.0         # seconds between retries
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ── Core Fetch ────────────────────────────────────────────────────────────────

def fetch_with_retry(url: str) -> dict | None:
    """GET url with exponential-backoff retry.  Returns parsed JSON or None."""
    for attempt in range(1, RETRY_LIMIT + 1):
        try:
            resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            log.warning("HTTP %s on attempt %d/%d — %s",
                        e.response.status_code, attempt, RETRY_LIMIT, url)
            if e.response.status_code in (401, 403, 404):
                break                       # non-retryable
        except requests.exceptions.ConnectionError:
            log.warning("Connection error on attempt %d/%d", attempt, RETRY_LIMIT)
        except requests.exceptions.Timeout:
            log.warning("Timeout on attempt %d/%d", attempt, RETRY_LIMIT)
        except Exception as exc:
            log.error("Unexpected error: %s", exc)
            break
        if attempt < RETRY_LIMIT:
            time.sleep(RETRY_BACKOFF * attempt)
    return None


def fetch_scheme(scheme_code: int, scheme_tag: str) -> dict | None:
    """
    Fetch full NAV history for one scheme from mfapi.in.
    Returns structured result dict or None on failure.
    """
    url  = f"{BASE_URL}/{scheme_code}"
    log.info("Fetching scheme [%d] %s  →  %s", scheme_code, scheme_tag, url)
    data = fetch_with_retry(url)

    if data is None:
        log.error("Failed to fetch scheme %d after %d attempts", scheme_code, RETRY_LIMIT)
        return None

    # Validate response shape
    meta     = data.get("meta", {})
    nav_list = data.get("data", [])
    if not meta or not nav_list:
        log.error("Empty or malformed response for scheme %d", scheme_code)
        return None

    return {
        "scheme_code": scheme_code,
        "tag":         scheme_tag,
        "meta":        meta,
        "nav_list":    nav_list,
        "fetched_at":  datetime.utcnow().isoformat() + "Z",
        "record_count": len(nav_list),
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def save_raw_json(result: dict) -> Path:
    """Persist the raw API response as JSON."""
    code    = result["scheme_code"]
    tag     = result["tag"]
    path    = RAW_DIR / f"nav_{code}_{tag}.json"
    payload = {
        "fetched_at":    result["fetched_at"],
        "meta":          result["meta"],
        "data":          result["nav_list"],
    }
    path.write_text(json.dumps(payload, indent=2))
    log.info("Raw JSON → %s  (%d bytes)", path, path.stat().st_size)
    return path


def save_nav_csv(result: dict, latest_only: bool = False) -> Path:
    """
    Save NAV data as a flat CSV.
    Columns: scheme_code, fund_house, scheme_name, scheme_category,
             scheme_type, date, nav, fetched_at
    """
    code     = result["scheme_code"]
    tag      = result["tag"]
    meta     = result["meta"]
    nav_list = result["nav_list"][:1] if latest_only else result["nav_list"]
    path     = RAW_DIR / f"nav_{code}_{tag}.csv"

    fieldnames = [
        "scheme_code", "fund_house", "scheme_name", "scheme_category",
        "scheme_type", "date", "nav", "fetched_at",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in nav_list:
            writer.writerow({
                "scheme_code":     meta.get("scheme_code", code),
                "fund_house":      meta.get("fund_house", ""),
                "scheme_name":     meta.get("scheme_name", ""),
                "scheme_category": meta.get("scheme_category", ""),
                "scheme_type":     meta.get("scheme_type", ""),
                "date":            entry.get("date", ""),
                "nav":             entry.get("nav", ""),
                "fetched_at":      result["fetched_at"],
            })

    log.info("NAV CSV   → %s  (%d records)", path, len(nav_list))
    return path


def build_snapshot(results: list[dict]) -> pd.DataFrame:
    """Merge latest NAV from all schemes into a single snapshot DataFrame."""
    rows = []
    for r in results:
        if not r["nav_list"]:
            continue
        latest = r["nav_list"][0]       # mfapi returns newest first
        rows.append({
            "scheme_code":     r["scheme_code"],
            "scheme_tag":      r["tag"],
            "fund_house":      r["meta"].get("fund_house", ""),
            "scheme_name":     r["meta"].get("scheme_name", ""),
            "scheme_category": r["meta"].get("scheme_category", ""),
            "latest_nav":      float(latest.get("nav", 0)),
            "latest_date":     latest.get("date", ""),
            "total_records":   r["record_count"],
            "fetched_at":      r["fetched_at"],
        })
    return pd.DataFrame(rows)


def print_nav_snapshot(df: pd.DataFrame) -> None:
    """Pretty-print the live NAV snapshot to stdout."""
    w = 70
    print("=" * w)
    print("  LIVE NAV SNAPSHOT — mfapi.in")
    print(f"  Fetched : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * w)
    print(f"  {'Code':<8} {'Tag':<24} {'NAV':>10}  {'Date':<12} {'Records':>8}")
    print("  " + "-" * 66)
    for _, row in df.iterrows():
        print(f"  {row['scheme_code']:<8} {row['scheme_tag']:<24} "
              f"₹{row['latest_nav']:>9.4f}  {row['latest_date']:<12} "
              f"{row['total_records']:>8,}")
    print("=" * w)
    print(f"  Schemes fetched : {len(df)}")
    print(f"  Data points     : {df['total_records'].sum():,}")
    print("=" * w)


# ── Parse Args ────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch live NAV data from mfapi.in for key MF schemes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  python live_nav_fetch.py                          # fetch all 6 schemes
  python live_nav_fetch.py --schemes 125497 119551  # specific schemes
  python live_nav_fetch.py --latest-only            # skip full history
        """,
    )
    parser.add_argument(
        "--schemes", nargs="+", type=int,
        default=list(SCHEME_REGISTRY.keys()),
        help="Scheme codes to fetch (default: all 6 key schemes)",
    )
    parser.add_argument(
        "--latest-only", action="store_true",
        help="Save only the latest NAV row per scheme (skips full history CSV)",
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args    = parse_args()
    targets = {
        code: SCHEME_REGISTRY.get(code, f"Scheme_{code}")
        for code in args.schemes
    }

    log.info("Starting live NAV fetch for %d scheme(s)", len(targets))

    results: list[dict] = []
    failed:  list[int]  = []

    for code, tag in targets.items():
        result = fetch_scheme(code, tag)
        if result is None:
            failed.append(code)
            continue

        save_raw_json(result)
        save_nav_csv(result, latest_only=args.latest_only)
        results.append(result)

        # Polite rate-limit spacing
        time.sleep(0.5)

    # Build & save live snapshot
    if results:
        snapshot = build_snapshot(results)
        snap_path = RAW_DIR / "nav_snapshot_live.csv"
        snapshot.to_csv(snap_path, index=False)
        log.info("Snapshot CSV → %s", snap_path)
        print_nav_snapshot(snapshot)
    else:
        log.error("No schemes fetched successfully.")

    # Report failures
    if failed:
        log.warning(
            "%d scheme(s) failed: %s",
            len(failed), failed
        )
        log.warning(
            "Likely cause: API domain blocked by network egress policy. "
            "Run locally: python live_nav_fetch.py"
        )

    # Summary
    log.info(
        "Done. Success: %d / %d  |  Failed: %d",
        len(results), len(targets), len(failed)
    )


if __name__ == "__main__":
    main()
