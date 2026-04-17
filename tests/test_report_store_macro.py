from datetime import datetime, timezone
from pathlib import Path

from src.db.report_store import ReportStore


def test_save_and_retrieve_macro_snapshot_as_of(tmp_path: Path):
    store = ReportStore(db_path=str(tmp_path / "r.db"), cache_hours=24)
    as_of = datetime(2026, 4, 17, 14, 5, tzinfo=timezone.utc)
    store.save_report(
        ticker="RELIANCE", exchange="NSE", profile="swing",
        report_md="# Test", pdf_path=None,
        macro_snapshot_as_of=as_of,
    )
    row = store.get_latest_report("RELIANCE", "NSE")
    assert row is not None
    stored = row.get("macro_snapshot_as_of")
    assert stored is not None


def test_save_report_without_macro_still_works(tmp_path: Path):
    # Back-compat: old callers that don't pass macro_snapshot_as_of.
    store = ReportStore(db_path=str(tmp_path / "r.db"), cache_hours=24)
    store.save_report(
        ticker="INFY", exchange="NSE", profile="swing",
        report_md="# Test", pdf_path=None,
    )
    row = store.get_latest_report("INFY", "NSE")
    assert row is not None
    assert row.get("macro_snapshot_as_of") in (None, "")


def test_macro_column_added_to_legacy_db(tmp_path: Path):
    # Simulate a pre-phase-2 DB with no macro_snapshot_as_of column.
    import sqlite3
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                exchange TEXT NOT NULL,
                profile TEXT NOT NULL,
                report_markdown TEXT NOT NULL,
                pdf_path TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO reports (ticker, exchange, profile, report_markdown, pdf_path) "
            "VALUES ('OLD', 'NSE', 'swing', '# legacy', NULL)"
        )

    # Opening via ReportStore must trigger the additive migration.
    store = ReportStore(db_path=str(db_path), cache_hours=0)
    row = store.get_latest_report("OLD", "NSE")
    assert row is not None
    # Column exists after migration (value is NULL for legacy rows).
    assert "macro_snapshot_as_of" in row
