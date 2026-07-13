"""GA4 UI export flow (no API).

Drives the logged-in browser through analytics.google.com:
  Report -> set date range (Custom start/end) -> Export -> Download CSV.
Returns the download path so run_all can rename + chunk.

Selectors are anchored on STABLE text ("Export", "Download file (CSV)",
"Custom", "Apply") rather than brittle CSS, because GA4's UI changes.
"""
from __future__ import annotations

from pathlib import Path
from playwright.sync_api import BrowserContext, Page


def _set_date_range(page: Page, start: str, end: str) -> None:
    """Open the date-range chip, pick Custom, fill start/end, Apply."""
    # The date range control usually shows like "Last 28 days".
    page.get_by_text("Last 7 days").or_(page.get_by_text("Last 28 days")) \
        .or_(page.get_by_text("Last 30 days")).first.click()
    page.get_by_text("Custom").click()
    # Two date inputs appear; fill start then end.
    inputs = page.get_by_role("textbox").filter(has_attribute="type", attr="type")
    # GA4 uses date inputs; fill both robustly.
    date_inputs = page.locator("input[type='date']")
    if date_inputs.count() >= 2:
        date_inputs.nth(0).fill(start)
        date_inputs.nth(1).fill(end)
    page.get_by_role("button", name="Apply").click()


def export_ga4_property(ctx: BrowserContext, property_id: str, start: str, end: str,
                        out_dir: Path, log_fn=print) -> Path | None:
    """Export one GA4 property for one date chunk. Returns CSV path or None."""
    page = ctx.new_page()
    try:
        page.goto(f"https://analytics.google.com/analytics/web/#/p{property_id}/reports/intelligenthome",
                  timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        _set_date_range(page, start, end)
        # Open the Export menu and pick CSV.
        page.get_by_role("button", name="Export").click()
        page.get_by_text("Download file (CSV)").click()
        # Wait for the download to complete.
        with page.expect_download(timeout=120000) as dl_info:
            pass
        download = dl_info.value
        dest = out_dir / f"ga4_{property_id}_{start}_{end}.csv"
        download.save_as(str(dest))
        log_fn(f"GA4 {property_id} [{start}..{end}] -> {dest.name}")
        return dest
    except Exception as e:
        log_fn(f"GA4 {property_id} [{start}..{end}] FAILED: {e}")
        return None
    finally:
        page.close()
