# FoxESS History Exporter

A small Python script that pulls historical inverter/battery data from the [FoxESS Open API](https://developer-eu.foxesscloud.com/login) and saves it as CSV, ready for analysis (e.g. self-consumption, self-sufficiency, battery cycling, export/import timing).

## What it does

- Authenticates against the FoxESS Open API using MD5-signed request headers
- Pulls 5-minute interval data for a full calendar month, looping day-by-day (the API only accepts a 1-day range per call)
- Handles the current month gracefully — stops at yesterday instead of requesting future dates that don't exist yet
- Writes output to `foxess_history_YYYY-MM.csv`

## Setup

1. Clone this repo and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Get your API key from the FoxESS Cloud portal:
   `foxesscloud.com` → **User Profile** → **API Management** → generate a key.

3. Get your inverter's serial number (SN) from the same portal, or by calling
   the `/op/v0/device/list` endpoint (see `get_device_list()` in the script).

4. Copy `.env.example` to `.env` and fill in your real values:

   ```bash
   cp .env.example .env
   ```

   ```
   FOXESS_API_KEY=your_actual_api_key
   FOXESS_DEVICE_SN=your_actual_device_sn
   ```

   `.env` is already covered by `.gitignore` — it will never be committed.

## Usage

```bash
python foxess_export.py MM-YYYY
```

Example — pull all of August 2026:

```bash
python foxess_export.py 08-2026
```

This produces `foxess_history_2026-08.csv` with columns:

time, pvPower, loadsPower, feedinPower, gridConsumptionPower, batChargePower, batDischargePower, SoC, remainCapacity

## Configuration

The variables pulled from the API can be changed by editing the `VARIABLES` list near the top of `foxess_export.py`. Defaults:

```python
VARIABLES = ["pvPower", "loadsPower", "feedinPower", "gridConsumptionPower",
             "batChargePower", "batDischargePower", "SoC"]
```

## Notes / gotchas

- The FoxESS history endpoint only accepts single-day ranges — multi-day requests return `errno 40257`. This script already loops day-by-day to work around that.
- Timestamps in the CSV include a timezone suffix (e.g. `BST+0100`). Strip or convert this before parsing with `pandas.to_datetime`.
- The API's "yield"/generation figures can differ slightly from what the FoxESS app shows, since yield includes all inverter output (including battery-sourced), not just solar production.
- API calls are rate-limited to roughly 1 request/second; the script already sleeps between calls to stay under this.

## License

MIT — do whatever you like with it.
