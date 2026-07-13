# GA4 + GSC Data Exporter (UI scripting, no API)

A **local-only** macOS desktop app that drives a logged-in browser through the
Google Analytics 4 and Search Console web UIs and downloads **all** historical
data as flat CSVs — no Google API, no OAuth, no service account.

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
  the session locally on your Mac (`analytics_exporter/.browser_profile/`,
  git-ignored).
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
playwright install chromium   # or use channel="chrome" with real Chrome installed
python ui.py
```
1. Enter your **company Google email**, GA4 property IDs, GSC site URLs.
2. Set the date range and chunk mode (**monthly** default, or **daily** for
   spike investigation).
3. Pick an **output folder** (you choose where CSVs land).
4. Click **Login (once)** — a browser opens; sign in to Google (2FA handled
   there). This seeds the local profile.
5. Click **Run export** — the app reuses the session headlessly and downloads
   per-chunk CSVs + a `manifest.json`.

## Verification (on macOS — this machine is staging only)
- Single chunk per property/site yields a non-empty CSV matching the UI row
  count for that chunk.
- Full range produces one file per chunk + a reconciling manifest.
- Headless re-run shows NO login page (persistent profile works).
- Re-auth: if Google boots the session mid-run, re-click **Login (once)**.

## Status
Built in verifiable chunks; syntax-checked + pytest (15 tests) pass on Windows
staging. Browser/UI behavior must be verified on the Mac (Playwright not run
here). Hardened flows: explicit waits, retry/backoff on export+download,
re-auth detection with pause, background-threaded UI with progress + status.

