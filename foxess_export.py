"""
FoxESS Open API -> CSV exporter
================================
Pulls historical inverter/battery data for a date range and saves it to CSV,
ready for analysis.

SETUP
-----
1. pip install requests python-dotenv
2. Get your API key: FoxESS Cloud portal -> personal center -> API management
3. Get your inverter's serial number (SN) from the same portal, or by calling
   the /op/v0/device/list endpoint (see get_device_list() below).
4. Create a file named .env in the same folder as this script, containing:
       FOXESS_API_KEY=your_actual_api_key
       FOXESS_DEVICE_SN=your_actual_device_sn
   (see .env.example for a template - copy it to .env and fill in your values)
   Never commit .env to version control - add it to .gitignore.

USAGE
-----
python foxess_export.py MM-YYYY

Example:
    python foxess_export.py 08-2026

Pulls every day in that calendar month. If the month is the current
(incomplete) month, it stops at yesterday instead of requesting future dates.
Output is written to foxess_history_YYYY-MM.csv.

Edit VARIABLES below to control which fields are pulled.
The API only returns up to 24 hours of history per call, so this script
loops day-by-day automatically.
"""

import argparse
import calendar
import hashlib
import os
import time
import csv
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# ----------------- CONFIG -----------------
load_dotenv()  # reads .env in the current directory, if present

API_KEY = os.environ.get("FOXESS_API_KEY")
DEVICE_SN = os.environ.get("FOXESS_DEVICE_SN")

if not API_KEY or not DEVICE_SN:
    raise SystemExit(
        "Missing credentials. Create a .env file in this folder with:\n"
        "    FOXESS_API_KEY=your_actual_api_key\n"
        "    FOXESS_DEVICE_SN=your_actual_device_sn\n"
        "See .env.example for a template."
    )

BASE_URL = "https://www.foxesscloud.com"
HISTORY_PATH = "/op/v0/device/history/query"
DEVICE_LIST_PATH = "/op/v0/device/list"

# Common variables: pvPower, batChargePower, batDischargePower, batPower,
# loadsPower, feedinPower, gridConsumptionPower, SoC
VARIABLES = ["pvPower", "loadsPower", "feedinPower", "gridConsumptionPower",
             "batChargePower", "batDischargePower", "SoC"]
# -------------------------------------------


def parse_month_arg(month_str: str):
    """Parse MM-YYYY into (start_date, end_date, output_filename)."""
    try:
        month, year = month_str.split("-")
        month, year = int(month), int(year)
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        raise SystemExit(f"Invalid month argument '{month_str}'. Expected format: MM-YYYY (e.g. 08-2026)")

    start = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day)

    # Don't request days that haven't happened yet (covers the current month).
    yesterday = datetime.now() - timedelta(days=1)
    if end > yesterday:
        end = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    if end < start:
        raise SystemExit(f"No completed days available yet for {month_str}.")

    output_csv = f"foxess_history_{year}-{month:02d}.csv"
    return start, end, output_csv


def make_headers(path: str) -> dict:
    timestamp = str(round(time.time() * 1000))
    raw = f"{path}\r\n{API_KEY}\r\n{timestamp}"
    signature = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return {
        "token": API_KEY,
        "timestamp": timestamp,
        "signature": signature,
        "lang": "en",
        "Content-Type": "application/json",
        "User-Agent": "foxess-export/1.0",
    }


def get_device_list():
    """Handy helper to confirm your serial number if you're not sure of it."""
    resp = requests.post(BASE_URL + DEVICE_LIST_PATH,
                          headers=make_headers(DEVICE_LIST_PATH),
                          json={"currentPage": 1, "pageSize": 10})
    resp.raise_for_status()
    return resp.json()


def fetch_day(day: datetime):
    begin_ms = int(day.timestamp() * 1000)
    end_ms = int((day + timedelta(days=1)).timestamp() * 1000)
    body = {"sn": DEVICE_SN, "variables": VARIABLES,
            "begin": begin_ms, "end": end_ms}
    resp = requests.post(BASE_URL + HISTORY_PATH,
                          headers=make_headers(HISTORY_PATH), json=body)
    resp.raise_for_status()
    data = resp.json()
    if data.get("errno") != 0:
        print(f"  Warning on {day.date()}: {data.get('msg')} (errno {data.get('errno')})")
        return []
    # Each entry in "result" is a device, with its variable blocks nested
    # under "datas" (not directly on the entry itself).
    var_blocks = []
    for device_entry in data.get("result", []):
        var_blocks.extend(device_entry.get("datas", []))
    return var_blocks


def main():
    parser = argparse.ArgumentParser(description="Export a month of FoxESS history to CSV.")
    parser.add_argument("month", help="Month to export, format MM-YYYY (e.g. 08-2026)")
    args = parser.parse_args()

    start, end, output_csv = parse_month_arg(args.month)

    rows = {}  # timestamp -> {variable: value}
    day = start
    while day <= end:
        print(f"Fetching {day.date()}...")
        result = fetch_day(day)
        for var_block in result:
            var_name = var_block.get("variable")
            for point in var_block.get("data", []):
                ts = point.get("time")
                rows.setdefault(ts, {})[var_name] = point.get("value")
        day += timedelta(days=1)
        time.sleep(1.1)  # stay under 1 call/second rate limit

    if not rows:
        print("No data returned. Check your API key, SN, and date range.")
        return

    fieldnames = ["time"] + VARIABLES
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ts in sorted(rows.keys()):
            row = {"time": ts}
            row.update(rows[ts])
            writer.writerow(row)

    print(f"Done. Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    main()
