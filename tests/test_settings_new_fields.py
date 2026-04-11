import pytest
from src.config.settings import Settings


def test_report_cache_hours_default():
    s = Settings()
    assert s.report_cache_hours == 24


def test_report_cache_hours_zero_disables_expiry():
    s = Settings(REPORT_CACHE_HOURS="0")
    assert s.report_cache_hours == 0


def test_reports_dir_default(monkeypatch):
    monkeypatch.delenv("REPORTS_DIR", raising=False)
    s = Settings()
    assert s.reports_dir == "reports"


def test_db_path_default(monkeypatch):
    monkeypatch.delenv("DB_PATH", raising=False)
    s = Settings()
    assert s.db_path == "data/reports.db"
