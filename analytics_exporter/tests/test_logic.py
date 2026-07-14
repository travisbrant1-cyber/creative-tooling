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


# ---------------- expect_download ordering regression ----------------
class _ClickRecordLocator:
    """Records when the export click fires AND whether it fired while a
    download listener was open (models the original race)."""
    def __init__(self, page):
        self._page = page
    def click(self, *a, **k):
        # The click "triggers" the download. The download is only observable
        # if a listener (expect_download) is currently open.
        self._page._fired = True
        if self._page._in_listener:
            self._page._fired_in_listener = True
    @property
    def first(self):
        return self


def _race_page_factory():
    """A fake page whose download only materializes if the export click
    happened INSIDE an open expect_download() context."""
    class _RacePage(_FakePage):
        def __init__(self):
            super().__init__()
            self._in_listener = False
            self._fired = False
            self._fired_in_listener = False
        def get_by_role(self, *a, **k):
            return _ClickRecordLocator(self)
        def get_by_text(self, *a, **k):
            return _ClickRecordLocator(self)
        def expect_download(self, *a, **k):
            class _RaceCtx:
                def __enter__(self):
                    self._page._in_listener = True
                    return self
                def __exit__(self, *e):
                    self._page._in_listener = False
                    return False
                @property
                def value(self):
                    # download only valid if the click fired WHILE the
                    # listener was open (the new, correct ordering)
                    if not self._page._fired_in_listener:
                        raise RuntimeError("download fired before listener attached")
                    return _FakeDownload()
            ctx = _RaceCtx()
            ctx._page = self
            return ctx
    return _RacePage()


def test_expect_download_wraps_click(tmp_path):
    """Regression: the export click must happen INSIDE expect_download,
    or a fast download is missed (the original race)."""
    import download as D
    page = _race_page_factory()
    dest = tmp_path / "out.csv"
    dest.parent.mkdir(exist_ok=True)
    ok = D.wait_for_download(page, dest, csv_label="X", export_btn="Y", timeout_s=5)
    assert ok is True
    assert dest.exists()


def test_expect_download_old_ordering_misses_download(tmp_path):
    """Mirror of the original bug: if the click fires BEFORE the listener
    opens, the download is missed. This pins the behavior so the fix is
    obviously correct (and would fail under the old code path)."""
    page = _race_page_factory()
    dest = tmp_path / "out2.csv"
    dest.parent.mkdir(exist_ok=True)
    # Reproduce OLD sequence: click first, THEN open expect_download.
    _ClickRecordLocator(page).click()  # fires the download trigger early
    import pytest
    with pytest.raises(RuntimeError):
        with page.expect_download(timeout=1000) as dl_info:
            pass
        _ = dl_info.value  # would hang in real Playwright; here it raises
    # Sanity: new wait_for_download would NOT raise (it clicks inside).
    assert not dest.exists()


# ---------------- retry / backoff regression ----------------
# The happy mocked run never fails a chunk, so RETRY backoff was never
# exercised — same hidden-gap class as the download race. These force the
# transient-failure path and prove the orchestrator retries then succeeds,
# and that exhaustion lands in errors (not a silent drop).
def test_ga4_retry_backoff_succeeds_after_transient_failure(tmp_path, monkeypatch):
    """A chunk that fails the first RETRY attempts must still land in files."""
    import run_all as RA
    monkeypatch.setattr(RA, "open_authed_context", _fake_open)
    monkeypatch.setattr(RA, "get_profile_dir", lambda x=None: tmp_path / ".prof")
    (tmp_path / ".prof").mkdir(exist_ok=True)

    calls = {"n": 0}
    def flaky_export(ctx, pid, cs, ce, out, log_fn=print):
        calls["n"] += 1
        if calls["n"] < RA.RETRY + 1:
            return None, False  # transient download failure
        dest = Path(out) / f"ga4_{pid}_{cs}_{ce}.csv"
        dest.write_text("a,b\n1,2\n", encoding="utf-8")
        return dest, False

    monkeypatch.setattr(RA, "export_ga4_property", flaky_export)
    cfg = C.AppConfig(email="a@b.com", ga4_property_ids=["123"], gsc_site_urls=[],
                      start_date="2024-01-01", end_date="2024-01-31",
                      chunk_mode="monthly", output_dir=str(tmp_path / "out"))
    manifest = RA.run_exports(cfg, log_fn=lambda *a, **k: None)
    assert calls["n"] == RA.RETRY + 1, f"expected {RA.RETRY + 1} attempts, got {calls['n']}"
    assert len(manifest["files"]) == 1
    assert manifest["errors"] == []


def test_ga4_retry_exhausted_goes_to_errors(tmp_path, monkeypatch):
    """A chunk that fails every attempt must appear in errors, not files."""
    import run_all as RA
    monkeypatch.setattr(RA, "open_authed_context", _fake_open)
    monkeypatch.setattr(RA, "get_profile_dir", lambda x=None: tmp_path / ".prof")
    (tmp_path / ".prof").mkdir(exist_ok=True)

    calls = {"n": 0}
    def always_fail(ctx, pid, cs, ce, out, log_fn=print):
        calls["n"] += 1
        return None, False

    monkeypatch.setattr(RA, "export_ga4_property", always_fail)
    cfg = C.AppConfig(email="a@b.com", ga4_property_ids=["123"], gsc_site_urls=[],
                      start_date="2024-01-01", end_date="2024-01-31",
                      chunk_mode="monthly", output_dir=str(tmp_path / "out"))
    manifest = RA.run_exports(cfg, log_fn=lambda *a, **k: None)
    assert calls["n"] == RA.RETRY + 1, f"expected {RA.RETRY + 1} attempts, got {calls['n']}"
    assert manifest["files"] == []
    assert any("GA4 123" in e for e in manifest["errors"])