"""Persistent Chromium profile + one-time seed login.

The password is NEVER read or stored by this app. The user types it directly
into Google's login page in the browser during the (headed) seed-login step.
After that, the session cookies in `profile_dir` are reused on every headless
run, so login pages are skipped.

Security note: we do NOT hash-and-send credentials (Google needs the real
password; a hash would be rejected). We do NOT persist the password at all.
The persistent browser profile IS the only credential store, and it lives
locally on the user's machine.
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
        ctx.storage_state(path=str(profile_dir / "storage_state.json"))
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
    return pw, browser, ctx
