"""Re-auth detection: Google sometimes boots the automation session mid-run
and throws a login/2FA page. We detect that and signal the caller to pause for
a manual re-login rather than failing silently.
"""
from __future__ import annotations

from playwright.sync_api import Page


def session_logged_out(page: Page) -> bool:
    """True if Google is showing a login / challenge page instead of app content."""
    url = page.url.lower()
    if "accounts.google.com" in url or "signin" in url or "challenge" in url:
        return True
    # In-page signals (heuristic; GA4/GSC keep you inside the app when logged in).
    for text in ("Sign in", "Verify it's you", "Choose an account"):
        if page.get_by_text(text, exact=False).count() > 0:
            return True
    return False
