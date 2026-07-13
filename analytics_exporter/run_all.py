"""Chunked orchestrator + run manifest.

Splits the date range into monthly or daily chunks (daily = better for
spike investigation / high-volume GSC sites), then drives each export flow.
Writes a manifest.json next to the outputs recording files, counts, timestamps,
and any re-auth events.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from config import AppConfig
from profile import get_profile_dir, open_authed_context
from ga4_export import export_ga4_property
from gsc_export import export_gsc_site


def _chunk_dates(start: str, end: str, mode: str) -> list[tuple[str, str]]:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    chunks: list[tuple[str, str]] = []
    cur = s
    while cur <= e:
        if mode == "daily":
            chunk_end = cur
        else:  # monthly
            # last day of cur's month, capped at e
            if cur.month == 12:
                nxt = cur.replace(year=cur.year + 1, month=1, day=1)
            else:
                nxt = cur.replace(month=cur.month + 1, day=1)
            chunk_end = min(nxt - timedelta(days=1), e)
        chunks.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + timedelta(days=1)
    return chunks


def run_exports(cfg: AppConfig, log_fn: Callable[[str], None] = print) -> dict:
    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    profile_dir = get_profile_dir(cfg.profile_dir or None)
    chunks = _chunk_dates(
        cfg.start_date or "2005-01-01",
        cfg.end_date or date.today().isoformat(),
        cfg.chunk_mode,
    )
    log_fn(f"Export plan: {len(chunks)} chunk(s) in {cfg.chunk_mode} mode.")

    manifest = {"chunks": len(chunks), "files": [], "errors": [], "started": _now()}
    browser, ctx = open_authed_context(profile_dir, headless=True)
    try:
        for (cs, ce) in chunks:
            for pid in cfg.ga4_property_ids:
                p = export_ga4_property(ctx, pid, cs, ce, out, log_fn)
                if p:
                    manifest["files"].append(str(p))
                else:
                    manifest["errors"].append(f"GA4 {pid} {cs}..{ce}")
            for site in cfg.gsc_site_urls:
                paths = export_gsc_site(ctx, site, cs, ce, out, log_fn=log_fn)
                if paths:
                    manifest["files"].extend(str(x) for x in paths)
                else:
                    manifest["errors"].append(f"GSC {site} {cs}..{ce}")
    finally:
        browser.close()

    manifest["finished"] = _now()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log_fn(f"Done. {len(manifest['files'])} files, {len(manifest['errors'])} errors. Manifest written.")
    return manifest


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
