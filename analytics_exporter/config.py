"""Configuration model for the GA4 + GSC UI exporter.

Local-only. No credentials are stored here -- only the (low-sensitivity) email
hint and run preferences. The actual Google session lives in the persistent
browser profile (see profile.py), never in this file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Literal

ChunkMode = Literal["monthly", "daily"]
APP_NAME = "analytics_exporter"


@dataclass
class AppConfig:
    # Company Google login identity (low-sensitivity; used only as a login hint).
    email: str = ""
    # Property / site identifiers the user wants to scrape.
    # GA4 property IDs (numeric, e.g. "123456789") and/or GSC site URLs.
    ga4_property_ids: list[str] = field(default_factory=list)
    gsc_site_urls: list[str] = field(default_factory=list)
    # Date range (inclusive). Empty = unbounded; UI fills defaults.
    start_date: str = ""  # ISO YYYY-MM-DD
    end_date: str = ""    # ISO YYYY-MM-DD
    # File granularity: one CSV per chunk.
    chunk_mode: ChunkMode = "monthly"
    # User-chosen output directory (absolute path on the Mac).
    output_dir: str = ""
    # Where the persistent browser profile lives (machine-local, git-ignored).
    profile_dir: str = ""

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty == valid)."""
        errors: list[str] = []
        if not self.email:
            errors.append("Company Google email is required.")
        if not self.ga4_property_ids and not self.gsc_site_urls:
            errors.append("Add at least one GA4 property ID or GSC site URL.")
        if not self.output_dir:
            errors.append("Choose an output directory.")
        else:
            p = Path(self.output_dir)
            if not p.exists():
                errors.append(f"Output directory does not exist: {self.output_dir}")
        if self.start_date and self.end_date:
            try:
                s = date.fromisoformat(self.start_date)
                e = date.fromisoformat(self.end_date)
                if s > e:
                    errors.append("Start date is after end date.")
            except ValueError:
                errors.append("Dates must be ISO format YYYY-MM-DD.")
        return errors

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except (json.JSONDecodeError, TypeError):
            return cls()
