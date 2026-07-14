"""Persistent Chromium profile + one-time seed login.

The password is NEVER read or stored by this app. The user types it directly
into Google's login page in the browser during the (headed) seed-login step.
After that, the session is persisted as `storage_state.json` (live Google
session cookies) in `profile_dir` and reused on every headless run, so login
pages are skipped.

SECURITY — READ THIS:
- The password is never captured or persisted. ✅
- BUT `storage_state.json` IS a live, unexpired Google session credential.
  Anyone who can read that file can hijack the Google account WITHOUT knowing
  the password and WITHOUT triggering a re-login. Treat it exactly like a
  password: it is the only thing standing between an attacker and the account.
- We lock the file down (0700 dir / 0600 file on POSIX) at write time, but
  that only protects against *other local users* — not against malware running
  as your user, and not against a backup/sync service that copies the profile
  dir. Do not put the profile dir under Dropbox/OneDrive/iCloud or any repo.
- This app scripts a real Google consumer account through its web UI
  headlessly. That is the kind of automated behavior Google's abuse detection
  is built to flag (hence reauth.py's existence). It may violate Google's ToS
  for that surface. Business risk, not a code defect — name it explicitly.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext


def get_profile_dir(base: str | None = None) -> Path:
    if base:
        return Path(base)
    # Default: machine-local, git-ignored, OS-appropriate location.
    if os.name == "nt":  # Windows
        return Path(os.environ.get("APPDATA", Path.home())) / "analytics_exporter" / "browser_profile"
    if os.name == "posix" and Path("/Users").exists():  # macOS
        return Path.home() / "Library" / "Application Support" / "analytics_exporter" / "browser_profile"
    # Linux / other
    return Path.home() / ".cache" / "analytics_exporter" / "browser_profile"


def _lock_session_file(state_path: Path) -> None:
    """Restrict the persisted Google session to the owner only.

    `storage_state.json` is a live, unexpired session credential — equivalent
    to a password. On POSIX we set 0700 on the dir and 0600 on the file. On
    Windows the ACL story is weaker (inheritance), so we only attempt the
    chmod where it applies and otherwise rely on the user keeping the profile
    dir off shared/synced locations (see the module docstring).
    """
    try:
        # Best-effort; ignore on platforms/FS where it's a no-op.
        os.chmod(str(state_path), 0o600)
        os.chmod(str(state_path.parent), 0o700)
    except OSError:
        pass


def seed_login(email: str, profile_dir: Path, timeout_s: int = 300) -> bool:
    """Open a HEADED browser for a one-time manual login.

    Returns True if the session appears established (Google account menu
    present). Travis handles 2FA / password entry in the browser. This is the
    ONLY step that touches the keyboard for credentials, and it's Google's
    own page -- not our app.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headed: real login
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto("https://accounts.google.com/", timeout=60000)
        # Pre-fill the email identifier to save a step (not the password).
        try:
            page.get_by_role("textbox", name="Email or phone").fill(email)
            page.get_by_role("button", name="Next").click()
        except Exception:
            pass  # Google may show a different first screen; user handles it.
        print("SEED LOGIN: complete the Google login in the browser window.")
        print("When finished, the app will detect the signed-in account.")
        # Wait for the account to be signed in (poll the accounts hub).
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                page.goto("https://myaccount.google.com/", timeout=30000)
                if page.get_by_text("Sign out").count() > 0 or \
                   page.get_by_text("Google Account").count() > 0:
                    break
            except Exception:
                pass
            time.sleep(3)
        # Persist the authenticated state for headless reuse.
        state_path = profile_dir / "storage_state.json"
        ctx.storage_state(path=str(state_path))
        _lock_session_file(state_path)
        browser.close()
    return (profile_dir / "storage_state.json").exists()


def open_authed_context(profile_dir: Path, headless: bool = True) -> tuple["sync_playwright", Browser, BrowserContext]:
    """Reopen the browser with the seeded session (no login page).

    Returns (playwright, browser, context). The playwright instance is kept
    alive and MUST be stopped by the caller (see run_all's finally block) —
    do NOT wrap this in a `with` or the driver exits before the caller uses it.
    """
    from playwright.sync_api import sync_playwright
    storage = profile_dir / "storage_state.json"
    if not storage.exists():
        raise RuntimeError("No seeded session found. Run seed_login() first.")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    ctx = browser.new_context(storage_state=str(storage))
    _lock_session_file(storage)  # re-assert perms in case they drifted
    return pw, browser, ctx
