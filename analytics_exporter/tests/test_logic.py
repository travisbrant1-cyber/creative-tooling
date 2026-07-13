"""Tests for analytics_exporter pure logic (no browser needed).

Run:  pytest tests/ -q
Covers: config validation + round-trip, date chunking (monthly/daily/leap),
download completeness check, re-auth heuristic, and a mocked full run_exports
using a fake Playwright context so the orchestrator logic is exercised without
a real browser.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import config as C
from run_all import _chunk_dates, run_exports
from download import _is_complete
from reauth import session_logged_out


# ---------------- config ----------------
def test_config_valid_ok(tmp_path):
    c = C.AppConfig(email="me@co.com", ga4_property_ids=["123"], gsc_site_urls=[],
                    start_date="2024-01-01", end_date="2024-03-31",
                    output_dir=str(tmp_path))
    assert c.validate() == []


def test_config_empty_invalid():
    c = C.AppConfig()
    errs = c.validate()
    assert "Company Google email is required." in errs
    assert "Add at least one GA4 property ID or GSC site URL." in errs


def test_config_bad_date_order(tmp_path):
    c = C.AppConfig(email="x@y.com", ga4_property_ids=["1"], start_date="2024-06-01",
                    end_date="2024-05-01", output_dir=str(tmp_path))
    assert any("after end" in e for e in c.validate())


def test_config_roundtrip(tmp_path):
    p = tmp_path / "cfg.json"
    c = C.AppConfig(email="a@b.com", ga4_property_ids=["9"], gsc_site_urls=["https://s.com"],
                    start_date="2023-01-01", end_date="2023-12-31", chunk_mode="daily",
                    output_dir=str(tmp_path))
    c.save(p)
    loaded = C.AppConfig.load(p)
    assert loaded.email == c.email
    assert loaded.ga4_property_ids == c.ga4_property_ids
    assert loaded.chunk_mode == "daily"


def test_config_load_missing_defaults(tmp_path):
    c = C.AppConfig.load(tmp_path / "nope.json")
    assert c.email == ""


# ---------------- chunking ----------------
def test_chunk_monthly():
    assert _chunk_dates("2024-01-01", "2024-03-31", "monthly") == [
        ("2024-01-01", "2024-01-31"),
        ("2024-02-01", "2024-02-29"),
        ("2024-03-01", "2024-03-31"),
    ]


def test_chunk_daily_leap():
    assert _chunk_dates("2024-02-28", "2024-03-01", "daily") == [
        ("2024-02-28", "2024-02-28"),
        ("2024-02-29", "2024-02-29"),
        ("2024-03-01", "2024-03-01"),
    ]


def test_chunk_single_day():
    assert _chunk_dates("2024-05-05", "2024-05-05", "daily") == [("2024-05-05", "2024-05-05")]


# ---------------- download completeness ----------------
def test_is_complete_rejects_empty(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("")  # 0 bytes
    assert _is_complete(f) is False


def test_is_complete_accepts_nonempty(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b,c\n1,2,3\n")
    assert _is_complete(f) is True


def test_is_complete_rejects_partial(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("data")
    (tmp_path / "x.csv.crdownload").write_text("partial")
    assert _is_complete(f) is False


# ---------------- re-auth heuristic ----------------
class _Locator:
    def __init__(self, n=0):
        self._n = n
    def count(self):
        return self._n
    def click(self, *a, **k):
        return None
    def or_(self, other):  # Playwright Locator.or_()
        return self
    def nth(self, i):
        return self
    def fill(self, value, *a, **k):
        return None
    @property
    def first(self):
        return self


class _FakePage:
    def __init__(self, url="", texts=()):
        self._url = url
        self._texts = texts
    @property
    def url(self):
        return self._url
    def get_by_text(self, text, exact=False):
        return _Locator(1 if text in self._texts else 0)
    def get_by_role(self, *a, **k):
        return _Locator(1)
    def locator(self, *a, **k):
        return _Locator(2)
    def wait_for_load_state(self, *a, **k):
        return None
    def goto(self, *a, **k):
        return None
    def expect_download(self, *a, **k):
        class _Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *e):
                return False
            value = _FakeDownload()
        return _Ctx()
    def close(self):
        return None


def test_reauth_true_on_accounts_url():
    assert session_logged_out(_FakePage(url="https://accounts.google.com/")) is True


def test_reauth_true_on_challenge_text():
    assert session_logged_out(_FakePage(texts=("Verify it's you",))) is True


def test_reauth_false_when_logged_in():
    assert session_logged_out(_FakePage(url="https://analytics.google.com/", texts=())) is False


# ---------------- orchestrator with mocked context ----------------
class _FakeDownload:
    def save_as(self, path):
        Path(path).write_text("col1,col2\n1,2\n", encoding="utf-8")


class _FakeContext:
    def new_page(self):
        return _FakePage()
    def close(self):
        return None


class _FakeBrowser:
    def close(self):
        return None


class _FakePW:
    def stop(self):
        return None


def _fake_open(profile_dir, headless=True):
    return _FakePW(), _FakeBrowser(), _FakeContext()


def test_run_exports_mocked(tmp_path, monkeypatch):
    import run_all as RA
    monkeypatch.setattr(RA, "open_authed_context", _fake_open)
    monkeypatch.setattr(RA, "get_profile_dir", lambda x=None: tmp_path / ".prof")

    cfg = C.AppConfig(email="a@b.com", ga4_property_ids=["123"], gsc_site_urls=[],
                      start_date="2024-01-01", end_date="2024-01-31",
                      chunk_mode="monthly", output_dir=str(tmp_path / "out"))
    (tmp_path / ".prof").mkdir(exist_ok=True)
    manifest = run_exports(cfg, log_fn=lambda *a, **k: None)
    assert len(manifest["files"]) == 1
    assert manifest["errors"] == []
    assert (tmp_path / "out" / "ga4_123_2024-01-01_2024-01-31.csv").exists()
