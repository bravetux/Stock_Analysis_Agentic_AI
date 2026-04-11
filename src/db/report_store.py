import os
import sqlite3
from datetime import datetime, timedelta, timezone


class ReportStore:
    def __init__(self, db_path: str = "data/reports.db", cache_hours: int = 24):
        self.db_path = db_path
        self.cache_hours = cache_hours
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    report_markdown TEXT NOT NULL,
                    pdf_path TEXT,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_ticker ON reports(ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_analyzed_at ON reports(analyzed_at)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_report(self, ticker: str, exchange: str, profile: str, report_md: str, pdf_path: str | None = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO reports (ticker, exchange, profile, report_markdown, pdf_path, analyzed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (ticker.upper(), exchange.upper(), profile, report_md, pdf_path, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.lastrowid

    def get_latest_report(self, ticker: str, exchange: str) -> dict | None:
        self.cleanup_expired()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE ticker = ? AND exchange = ? ORDER BY analyzed_at DESC LIMIT 1",
                (ticker.upper(), exchange.upper()),
            ).fetchone()
            return dict(row) if row else None

    def get_report_history(self, ticker: str) -> list[dict]:
        self.cleanup_expired()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reports WHERE ticker = ? ORDER BY analyzed_at DESC",
                (ticker.upper(),),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_report_by_id(self, report_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            return dict(row) if row else None

    def search_tickers(self, query: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM reports WHERE ticker LIKE ? ORDER BY ticker",
                (f"{query.upper()}%",),
            ).fetchall()
            return [r["ticker"] for r in rows]

    def cleanup_expired(self):
        if self.cache_hours == 0:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=self.cache_hours)).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM reports WHERE analyzed_at < ?", (cutoff,))
