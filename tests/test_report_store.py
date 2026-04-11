import time
from datetime import datetime, timedelta, timezone
from src.db.report_store import ReportStore


def test_save_and_get_latest(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    row_id = db.save_report("RELIANCE", "NSE", "beginner", "# Report\nContent here", "/path/to/report.pdf")
    assert row_id == 1

    report = db.get_latest_report("RELIANCE", "NSE")
    assert report is not None
    assert report["ticker"] == "RELIANCE"
    assert report["exchange"] == "NSE"
    assert report["profile"] == "beginner"
    assert report["report_markdown"] == "# Report\nContent here"
    assert report["pdf_path"] == "/path/to/report.pdf"


def test_get_latest_returns_none_when_empty(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    assert db.get_latest_report("RELIANCE", "NSE") is None


def test_get_latest_returns_most_recent(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    db.save_report("RELIANCE", "NSE", "beginner", "Old report")
    db.save_report("RELIANCE", "NSE", "expert", "New report")

    report = db.get_latest_report("RELIANCE", "NSE")
    assert report["report_markdown"] == "New report"
    assert report["profile"] == "expert"


def test_get_report_history(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    db.save_report("RELIANCE", "NSE", "beginner", "Report 1")
    db.save_report("RELIANCE", "BSE", "novice", "Report 2")
    db.save_report("AAPL", "NASDAQ", "expert", "Report 3")

    history = db.get_report_history("RELIANCE")
    assert len(history) == 2
    # Newest first
    assert history[0]["exchange"] == "BSE"
    assert history[1]["exchange"] == "NSE"


def test_search_tickers(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    db.save_report("RELIANCE", "NSE", "beginner", "r1")
    db.save_report("RELIANCE", "BSE", "beginner", "r2")
    db.save_report("AAPL", "NASDAQ", "beginner", "r3")
    db.save_report("AMZN", "NASDAQ", "beginner", "r4")

    results = db.search_tickers("REL")
    assert results == ["RELIANCE"]

    results = db.search_tickers("A")
    assert set(results) == {"AAPL", "AMZN"}

    results = db.search_tickers("NOPE")
    assert results == []


def test_cleanup_expired(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=1)
    # Insert a report with a timestamp 2 hours ago
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn.execute(
        "INSERT INTO reports (ticker, exchange, profile, report_markdown, analyzed_at) VALUES (?, ?, ?, ?, ?)",
        ("RELIANCE", "NSE", "beginner", "Old", two_hours_ago),
    )
    conn.commit()
    conn.close()

    db.save_report("RELIANCE", "NSE", "beginner", "New")

    db.cleanup_expired()

    history = db.get_report_history("RELIANCE")
    assert len(history) == 1
    assert history[0]["report_markdown"] == "New"


def test_cleanup_disabled_when_zero(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=0)
    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "test.db"))
    old_time = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    conn.execute(
        "INSERT INTO reports (ticker, exchange, profile, report_markdown, analyzed_at) VALUES (?, ?, ?, ?, ?)",
        ("RELIANCE", "NSE", "beginner", "Ancient report", old_time),
    )
    conn.commit()
    conn.close()

    db.cleanup_expired()

    history = db.get_report_history("RELIANCE")
    assert len(history) == 1


def test_get_report_by_id(tmp_path):
    db = ReportStore(db_path=str(tmp_path / "test.db"), cache_hours=24)
    row_id = db.save_report("RELIANCE", "NSE", "beginner", "Report content")
    report = db.get_report_by_id(row_id)
    assert report is not None
    assert report["report_markdown"] == "Report content"
