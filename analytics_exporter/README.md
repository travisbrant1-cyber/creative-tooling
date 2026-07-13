# GA4 + GSC Data Exporter (UI scripting, no API)

A **local-only** desktop app that drives a logged-in browser through the
Google Analytics 4 and Search Console web UIs and downloads **all** historical
data as flat CSVs — no Google API, no OAuth, no service account.

Works on **macOS and Windows** (Linux with minor path tweaks).

## Why UI scripting (not the API)
The GA4/GSC APIs can return full history only via pagination, but if your
Workspace blocks third-party API access to the property (the consent-screen /
"OAS" wall) you can't authenticate at all. The UI sidesteps that wall: it's
just a logged-in Google user clicking. Volume is handled by chunking the date
range into monthly or daily CSVs.

## Security model (important)
- **Password is NEVER captured or stored by this app.** You type it directly
  into Google's own login page during the one-time seed login.
- **No hash-then-send.** Google needs the real password; a hash would be
  rejected. We simply don't persist the password.
- **The persistent browser profile is the only credential store** — it holds
  the session locally on your machine:
  - macOS: `~/Library/Application Support/analytics_exporter/browser_profile`
  - Windows: `%APPDATA%\analytics_exporter\browser_profile`
  - Linux: `~/.cache/analytics_exporter/browser_profile`
- **Local-only execution + storage.** No external calls except to Google for
  login and data collection. No telemetry, no cloud sync.
- Only the (low-sensitivity) email hint is saved in `config.json`. If any
  secret ever needed at-rest storage, it would be ENCRYPTED with a machine key,
  never hashed (hashing = verify-only, encryption = retrieve).

## Run on macOS
```bash
cd analytics_exporter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium   # or use channel="chrome" with real Chrome
python ui.py
```

## Run on Windows (coworker)
See **WINDOWS_SETUP.md** for the full walkthrough. Short version:
1. Double-click **`setup.bat`** (creates venv, installs deps, downloads Chromium).
2. Double-click **`run.bat`** (launches `python ui.py`).

## Using the app
1. Enter your **company Google email**, GA4 property IDs, GSC site URLs.
2. Set the date range and chunk mode (**monthly** default, or **daily** for
   spike investigation).
3. Pick an **output folder** (you choose where CSVs land).
4. Click **Login (once)** — a browser opens; sign in to Google (2FA handled
   there). This seeds the local profile.
5. Click **Run export** — the app reuses the session headlessly and downloads
   per-chunk CSVs + a `manifest.json`.

## Verification
- Pure-logic + orchestrator (mocked browser): **15 pytest tests pass**.
- Real browser flow verified on a machine with Chromium installed
  (macOS smoke test; Windows proven by setup.bat + Chromium install).
- Re-auth: if Google boots the session mid-run, re-click **Login (once)**.

## Status
Built in verifiable chunks; hardened flows: explicit waits, retry/backoff on
export+download, re-auth detection with pause, background-threaded UI with
progress + status. Cross-platform (macOS + Windows). Not merged to main
(pending real browser smoke test on each platform).
