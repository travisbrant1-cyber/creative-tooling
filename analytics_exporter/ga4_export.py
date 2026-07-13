"""GA4 UI export flow (no API) — hardened.

Drives the logged-in browser through analytics.google.com:
  Report -> set date range (Custom start/end) -> Export -> Download CSV.

Hardening vs v1:
- Explicit wait_for_load_state + element waits (no blind timing).
- Re-auth detection: if Google boots the session, returns a sentinel so the
  orchestrator can pause for a manual re-login.
- Retry/backoff on the export click + download via download.py.
- Date inputs located by type, not index-only.

Returns (Path | None, logged_out: bool).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from playwright.sync_api import BrowserContext, Page

from download import wait_for_download, click_export_csv
from reauth import session_logged_out


def _set_date_range(page: Page, start: str, end: str, log_fn: Callable[[str], None]) -> bool:
    try:
        # The date-range control usually reads like "Last 28 days".
        page.get_by_text("Last 7 days").or_(
            page.get_by_text("Last 28 days")).or_(
            page.get_by_text("Last 30 days")).first.click(timeout=8000)
        page.get_by_text("Custom", exact=True).click(timeout=8000)
        date_inputs = page.locator("input[type='date']")
        if date_inputs.count() >= 2:
            date_inputs.nth(0).fill(start)
            date_inputs.nth(1).fill(end)
        page.get_by_role("button", name="Apply").click(timeout=8000)
        page.wait_for_load_state("networkidle", timeout=20000)
        return True
    except Exception as e:
        log_fn(f"  GA4 date-range set failed: {e}")
        return False


def export_ga4_property(ctx: BrowserContext, property_id: str, start: str, end: str,
                        out_dir: Path, log_fn: Callable[[str], None] = print
                        ) -> tuple[Path | None, bool]:
    """Export one GA4 property for one date chunk.

    Returns (csv_path_or_None, logged_out). `logged_out=True` means Google
    booted the session and the caller should pause for a manual re-login.
    """
    page = ctx.new_page()
    dest = out_dir / f"ga4_{property_id}_{start}_{end}.csv"
    logged_out = False
    try:
        page.goto(
            f"https://analytics.google.com/analytics/web/#/p{property_id}/reports/intelligenthome",
            timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        if session_logged_out(page):
            logged_out = True
            log_fn(f"GA4 {property_id}: session logged out (re-auth needed).")
            return None, True
        if not _set_date_range(page, start, end, log_fn):
            return None, False
        click_export_csv(page, csv_label="Download file (CSV)", export_btn="Export", log_fn=log_fn)
        ok = wait_for_download(page, dest, timeout_s=180, log_fn=log_fn)
        if ok:
            log_fn(f"GA4 {property_id} [{start}..{end}] -> {dest.name}")
            return dest, False
        log_fn(f"GA4 {property_id} [{start}..{end}] download failed.")
        return None, False
    except Exception as e:
        log_fn(f"GA4 {property_id} [{start}..{end}] FAILED: {e}")
        return None, False
    finally:
        page.close()
