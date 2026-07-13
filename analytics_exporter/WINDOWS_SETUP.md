# Windows Setup — GA4 + GSC Data Exporter

For a coworker setting this up on a **Windows** machine. The app is
local-only: it drives your own logged-in browser through Google's GA4 and
Search Console web UIs and downloads data as CSVs. No Google API, no OAuth.

## What you need
- Windows 10/11 (64-bit)
- Python 3.10+ installed and on PATH (check: open a terminal, run `python --version`)
- A Google account that already has access to the GA4 property(s) and/or
  Search Console site(s) you want to export.

## One-time setup
1. Clone or unzip this folder (`analytics_exporter`).
2. Double-click **`setup.bat`**.
   It creates a virtual environment, installs Python deps, and downloads
   Chromium (the browser the app automates). This can take a few minutes the
   first time.

## Running it
3. Double-click **`run.bat`** (or run `python ui.py` from inside the venv).
   A window opens.
4. Enter your **company Google email**, the GA4 property IDs, and/or GSC site
   URLs.
5. Set the **date range** and chunk mode (monthly by default; daily if you
   need to investigate a traffic spike).
6. Pick an **output folder** — that's where the CSVs land. You choose it.
7. Click **Login (once)**. A browser window opens to Google. Sign in normally
   (including 2FA if prompted). This seeds a local session so the app can run
   without showing login pages later. **You type your password only into
   Google's own page — the app never sees or stores it.**
8. Click **Run export**. The app reuses your session and downloads per-chunk
   CSVs plus a `manifest.json` summary.

## Re-auth
If Google logs the session out mid-run (it sometimes challenges automation),
the app shows a "Re-auth needed" notice. Just click **Login (once)** again,
then **Run export** to continue.

## Where things live
- Session/profile: `%APPDATA%\analytics_exporter\browser_profile` (git-ignored)
- Config: `analytics_exporter\config.json` (your email hint only)
- Outputs: the folder you picked in step 6

## Troubleshooting
- **Browser doesn't open on Login:** Chromium may not have installed. Re-run
  `setup.bat` and watch for errors during `playwright install chromium`.
- **Export clicks miss / wrong data downloaded:** Google's UIs change. The
  selectors live in `ga4_export.py` and `gsc_export.py` — tell the maintainer
  what you see and it can be adjusted.
- **Empty CSVs:** the date chunk may have no data, or the report didn't finish
  rendering before export. Try a smaller (daily) chunk.

## Security notes
- Password is never captured or stored by this app.
- Runs fully locally; only talks to Google for login + data.
- No telemetry, no cloud upload.
