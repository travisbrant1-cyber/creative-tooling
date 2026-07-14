"""GSC UI export flow (no API) — hardened.

Drives the logged-in browser through search.google.com/search-console:
  Performance -> set date range -> (per dimension tab) -> Export -> Download CSV.

Hardening vs v1: explicit waits, re-auth detection, retry/backoff on export +
download via download.py, dimension tabs tried independently (a missing tab is
skipped, not fatal).

Returns (list[Path], logged_out: bool).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from playwright.sync_api import BrowserContext, Page

from download import wait_for_download
from reauth import session_logged_out

# Dimension tabs users typically want. Order = export order.
GSC_DIMENSIONS = ["Queries", "Pages", "Countries", "Devices", "Search appearance"]


def _set_date_range(page: Page, start: str, end: str, log_fn: Callable[[str], None]) -> bool:
    try:
        page.get_by_text("Custom", exact=False).first.click(timeout=8000)
        date_inputs = page.locator("input[type='date']")
        if date_inputs.count() >= 2:
            date_inputs.nth(0).fill(start)
            date_inputs.nth(1).fill(end)
        page.get_by_role("button", name="Apply").click(timeout=8000)
        page.wait_for_load_state("networkidle", timeout=20000)
        return True
    except Exception as e:
        log_fn(f"  GSC date-range set failed: {e}")
        return False


def export_gsc_site(ctx: BrowserContext, site_url: str, start: str, end: str,
                    out_dir: Path, dimensions: list[str] | None = None,
                    log_fn: Callable[[str], None] = print) -> tuple[list[Path], bool]:
    """Export one GSC site for one date chunk, per dimension.

    Returns (csv_paths, logged_out). A failed dimension is skipped (logged),
    not fatal; only a full session-logout sets logged_out=True.
    """
    dimensions = dimensions or GSC_DIMENSIONS
    results: list[Path] = []
    page = ctx.new_page()
    logged_out = False
    try:
        page.goto(
            f"https://search.google.com/search-console/performance/search-analytics?resource_id={site_url}",
            timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        if session_logged_out(page):
            logged_out = True
            log_fn(f"GSC {site_url}: session logged out (re-auth needed).")
            return results, True
        if not _set_date_range(page, start, end, log_fn):
            return results, False
        for dim in dimensions:
            dest = out_dir / f"gsc_{_safe(site_url)}_{dim}_{start}_{end}.csv"
            try:
                page.get_by_text(dim, exact=True).first.click(timeout=5000)
                ok = wait_for_download(page, dest, csv_label="Download .csv",
                                       export_btn="Export", timeout_s=180, log_fn=log_fn)
                if ok:
                    results.append(dest)
                    log_fn(f"GSC {site_url} [{dim}] [{start}..{end}] -> {dest.name}")
                else:
                    log_fn(f"GSC {site_url} [{dim}] download failed (skipped).")
            except Exception as e:
                log_fn(f"GSC {site_url} [{dim}] skipped: {e}")
    except Exception as e:
        log_fn(f"GSC {site_url} [{start}..{end}] FAILED: {e}")
    finally:
        page.close()
    return results, logged_out


def _safe(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_")
