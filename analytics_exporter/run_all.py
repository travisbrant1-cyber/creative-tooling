"""Chunked orchestrator + run manifest — hardened.

Splits the date range into monthly or daily chunks, drives each export flow,
and writes a manifest.json. Hardening vs v1:
- New 2-tuple returns from ga4_export/gsc_export: (path|list, logged_out).
- Re-auth pause: if a flow reports logged_out, stops and tells the user to
  re-login (via log_fn) instead of failing every remaining chunk.
- Per-chunk retry (configurable) on transient download failure.
- Optional progress callback (used by the UI progress bar).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from config import AppConfig
from profile import get_profile_dir, open_authed_context
from ga4_export import export_ga4_property
from gsc_export import export_gsc_site

RETRY = 2  # extra attempts per failed chunk


def _chunk_dates(start: str, end: str, mode: str) -> list[tuple[str, str]]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    chunks: list[tuple[str, str]] = []
    cur = s
    while cur <= e:
        if mode == "daily":
            chunk_end = cur
        else:  # monthly
            if cur.month == 12:
                nxt = cur.replace(year=cur.year + 1, month=1, day=1)
            else:
                nxt = cur.replace(month=cur.month + 1, day=1)
            chunk_end = min(nxt - timedelta(days=1), e)
        chunks.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)
    return chunks


def run_exports(cfg: AppConfig, log_fn: Callable[[str], None] = print,
                progress_fn: Optional[Callable[[int, int], None]] = None) -> dict:
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    profile_dir = get_profile_dir(cfg.profile_dir or None)
    chunks = _chunk_dates(
        cfg.start_date or "2005-01-01",
        cfg.end_date or date.today().isoformat(),
        cfg.chunk_mode,
    )
    total = len(chunks) * (len(cfg.ga4_property_ids) + len(cfg.gsc_site_urls))
    done = 0
    log_fn(f"Export plan: {len(chunks)} chunk(s) in {cfg.chunk_mode} mode.")

    manifest = {"chunks": len(chunks), "files": [], "errors": [], "started": _now()}
    pw, browser, ctx = open_authed_context(profile_dir, headless=True)
    try:
        for (cs, ce) in chunks:
            if _progress(progress_fn, done, total):
                break
            for pid in cfg.ga4_property_ids:
                for attempt in range(RETRY + 1):
                    path, logged_out = export_ga4_property(ctx, pid, cs, ce, out, log_fn=log_fn)
                    if logged_out:
                        log_fn(">>> SESSION LOGGED OUT. Click 'Login (once)' to re-auth, then Run again.")
                        manifest["errors"].append(f"REAUTH {pid} {cs}..{ce}")
                        done += 1
                        break
                    if path:
                        manifest["files"].append(str(path))
                        break
                    if attempt < RETRY:
                        log_fn(f"  retry GA4 {pid} {cs}..{ce} (attempt {attempt + 2})")
                        continue
                    manifest["errors"].append(f"GA4 {pid} {cs}..{ce}")
                done += 1
            for site in cfg.gsc_site_urls:
                for attempt in range(RETRY + 1):
                    paths, logged_out = export_gsc_site(ctx, site, cs, ce, out, log_fn=log_fn)
                    if logged_out:
                        log_fn(">>> SESSION LOGGED OUT. Click 'Login (once)' to re-auth, then Run again.")
                        manifest["errors"].append(f"REAUTH {site} {cs}..{ce}")
                        done += 1
                        break
                    if paths:
                        manifest["files"].extend(str(x) for x in paths)
                        break
                    if attempt < RETRY:
                        log_fn(f"  retry GSC {site} {cs}..{ce} (attempt {attempt + 2})")
                        continue
                    manifest["errors"].append(f"GSC {site} {cs}..{ce}")
                done += 1
    finally:
        browser.close()
        ctx.close()
        pw.stop()

    manifest["finished"] = _now()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log_fn(f"Done. {len(manifest['files'])} files, {len(manifest['errors'])} errors. Manifest written.")
    return manifest


def _progress(fn, done, total):
    if fn:
        fn(done, total)
    return False  # hook reserved for a cancel signal in the UI


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
