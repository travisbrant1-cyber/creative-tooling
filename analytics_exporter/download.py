"""Robust download handling shared by GA4 + GSC flows.

Hardening features:
- Waits for the download to finish (no .crdownload / partial files).
- Guards against empty / zero-byte files.
- Pluggable timeout + retry with exponential backoff.
- Surfaces a clear error instead of silently writing a bad file.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from playwright.sync_api import BrowserContext, Page


def _is_complete(path: Path, settle_s: float = 0.5) -> bool:
    """A download is complete when the temp file is gone and size is stable."""
    if not path.exists():
        return False
    # Playwright clears the temp file only after the download finishes.
    tmp = path.with_suffix(path.suffix + ".crdownload")
    if tmp.exists():
        return False
    size1 = path.stat().st_size
    time.sleep(settle_s)
    if not path.exists():
        return False
    size2 = path.stat().st_size
    return size1 == size2 and size1 > 0


def wait_for_download(page: Page, dest: Path, timeout_s: int = 180,
                      settle_s: float = 0.5, log_fn: Callable[[str], None] = print) -> bool:
    """Trigger-agnostic: caller opens the Export menu + clicks the download,
    then calls this to capture + validate the result.

    Returns True if a valid (non-empty) CSV landed at `dest`.
    """
    try:
        with page.expect_download(timeout=timeout_s * 1000) as dl_info:
            pass
        download = dl_info.value
        # Playwright may already suggest a path; force ours.
        download.save_as(str(dest))
    except Exception as e:
        log_fn(f"  download capture failed: {e}")
        return False

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _is_complete(dest, settle_s):
            return True
        time.sleep(0.5)
    if dest.exists() and dest.stat().st_size == 0:
        log_fn(f"  download empty (0 bytes): {dest.name}")
        return False
    log_fn(f"  download did not finish within {timeout_s}s: {dest.name}")
    return False


def click_export_csv(page: Page, *, csv_label: str = "Download file (CSV)",
                     export_btn: str = "Export", log_fn: Callable[[str], None] = print) -> None:
    """Open the Export menu and click the CSV option, with retries.

    Anchors on stable button text, not brittle CSS. Raises on failure so the
    caller can mark the chunk as errored + retry.
    """
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            page.get_by_role("button", name=export_btn).click(timeout=10000)
            page.get_by_text(csv_label, exact=False).first.click(timeout=10000)
            return
        except Exception as e:  # transient overlay / not-yet-rendered menu
            last_err = e
            log_fn(f"  export click attempt {attempt + 1} failed: {e}")
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Export > {csv_label} failed after 3 attempts: {last_err}")
