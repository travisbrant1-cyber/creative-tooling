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
- **The persistent browser profile holds a LIVE Google session — treat it like
  a password, not "low-sensitivity" local state.** `storage_state.json` inside
  the profile dir contains unexpired session cookies. Anyone who can read that
  file can hijack the Google account **without the password and without a
  re-login prompt**. The app locks it down (0700 dir / 0600 file on macOS/Linux)
  on every seed + load, but that only blocks *other local users* — not malware
  running as you, and not a backup/sync service. **Keep the profile dir out of
  Dropbox/OneDrive/iCloud and out of any git repo.** Only the (low-sensitivity)
  email hint is saved in `config.json`.
- **Local-only execution + storage.** No external calls except to Google for
  login and data collection. No telemetry, no cloud sync.
- If any secret ever needed at-rest storage, it would be ENCRYPTED with a
  machine key, never hashed (hashing = verify-only, encryption = retrieve).

## Compliance / abuse note (read before running)
This tool scripts a **real Google consumer account through its web UI,
headlessly**. That is precisely the pattern Google's automated-abuse detection
is built to catch — which is why `reauth.py` exists (to recover when Google
boots the session). Depending on your Workspace/account terms, this may violate
Google's Terms of Service for that surface. It is a **business/legal risk, not
a code defect**. Use it only where you have authorization to access the data
(e.g. your own property, or a client who has explicitly consented), and prefer
the official GA4/GSC **API** where automation is sanctioned. This exporter is a
fallback for when the API is blocked by the consent-screen / OAS wall — not a
way to circumvent ToS.

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
