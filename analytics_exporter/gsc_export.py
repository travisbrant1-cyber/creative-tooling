"""GSC UI export flow (no API).

Drives the logged-in browser through search.google.com/search-console:
  Performance -> set date range -> (per dimension tab) -> Export -> Download CSV.

GSC Performance caps on-screen rows (~1,000), so callers should use small
date chunks (daily mode) for high-volume sites. Selectors anchored on stable
text ("Performance", "Export", "Download .csv", "Custom", "Apply").
"""
from __future__ import annotations

from pathlib import Path
from playwright.sync_api import BrowserContext, Page

# Dimension tabs users typically want.
GSC_DIMENSIONS = ["Queries", "Pages", "Countries", "Devices", "Search appearance"]


def _set_date_range(page: Page, start: str, end: str) -> None:
    page.get_by_text("Custom", exact=False).first.click()
    date_inputs = page.locator("input[type='date']")
    if date_inputs.count() >= 2:
        date_inputs.nth(0).fill(start)
        date_inputs.nth(1).fill(end)
    page.get_by_role("button", name="Apply").click()


def export_gsc_site(ctx: BrowserContext, site_url: str, start: str, end: str,
                    out_dir: Path, dimensions: list[str] | None = None,
                    log_fn=print) -> list[Path]:
    """Export one GSC site for one date chunk, per dimension. Returns CSV paths."""
    dimensions = dimensions or GSC_DIMENSIONS
    results: list[Path] = []
    page = ctx.new_page()
    try:
        page.goto(f"https://search.google.com/search-console/performance/search-analytics?resource_id={site_url}",
                  timeout=60000)
        page.wait_for_load_state("networkidle", timeout=30000)
        _set_date_range(page, start, end)
        for dim in dimensions:
            try:
                # Switch the dimension tab if present.
                page.get_by_text(dim, exact=True).first.click(timeout=5000)
            except Exception:
                pass  # dimension may not be available; skip
            try:
                page.get_by_role("button", name="Export").click(timeout=5000)
                page.get_by_text("Download .csv").click(timeout=5000)
                with page.expect_download(timeout=120000) as dl_info:
                    pass
                download = dl_info.value
                dest = out_dir / f"gsc_{_safe(site_url)}_{dim}_{start}_{end}.csv"
                download.save_as(str(dest))
                results.append(dest)
                log_fn(f"GSC {site_url} [{dim}] [{start}..{end}] -> {dest.name}")
            except Exception as e:
                log_fn(f"GSC {site_url} [{dim}] [{start}..{end}] FAILED: {e}")
    except Exception as e:
        log_fn(f"GSC {site_url} [{start}..{end}] FAILED: {e}")
    finally:
        page.close()
    return results


def _safe(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_")
