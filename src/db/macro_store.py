# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Author: B.Vignesh Kumar aka Bravetux
# Email:  ic19939@gmail.com
# Developed: 17th April 2026

"""SQLite persistence for the macro snapshot rolling history.

Shares the same DB file as ReportStore (settings.db_path) — no second
connection lifecycle for users to manage.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.tools.macro_tools import IndicatorReading, MacroSnapshot


class MacroStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS macro_snapshots (
                    indicator TEXT NOT NULL,
                    as_of     TIMESTAMP NOT NULL,
                    value     REAL NOT NULL,
                    source    TEXT,
                    PRIMARY KEY (indicator, as_of)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_macro_indicator_asof "
                "ON macro_snapshots (indicator, as_of DESC)"
            )

    def insert_snapshot(self, snapshot: MacroSnapshot) -> None:
        with self._conn() as conn:
            for reading in snapshot.indicators.values():
                conn.execute(
                    "INSERT OR REPLACE INTO macro_snapshots "
                    "(indicator, as_of, value, source) VALUES (?, ?, ?, ?)",
                    (reading.code, reading.as_of.isoformat(), reading.value, reading.source),
                )

    def get_latest(self, indicator: str) -> Optional[IndicatorReading]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT indicator, as_of, value, source FROM macro_snapshots "
                "WHERE indicator = ? ORDER BY as_of DESC LIMIT 1",
                (indicator,),
            ).fetchone()
        if row is None:
            return None
        code, as_of, value, source = row
        if isinstance(as_of, str):
            as_of = datetime.fromisoformat(as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        return IndicatorReading(
            code=code, label=code, value=float(value),
            d1_pct=None, w1_pct=None, m1_pct=None,
            regime=None, source=source or "", as_of=as_of,
        )

    def get_value_n_days_ago(
        self,
        indicator: str,
        n: int,
        reference: Optional[datetime] = None,
    ) -> Optional[float]:
        """Weekend-aware: returns value at the most recent row on or before
        (reference - n days). Returns None if no such row exists."""
        if reference is None:
            reference = datetime.now(timezone.utc)
        cutoff = reference - timedelta(days=n)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM macro_snapshots "
                "WHERE indicator = ? AND as_of <= ? "
                "ORDER BY as_of DESC LIMIT 1",
                (indicator, cutoff.isoformat()),
            ).fetchone()
        return None if row is None else float(row[0])

    def is_fresh(self, indicator: str, max_age_minutes: int) -> bool:
        latest = self.get_latest(indicator)
        if latest is None:
            return False
        age = (datetime.now(timezone.utc) - latest.as_of).total_seconds() / 60.0
        return age <= max_age_minutes

    def prune(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM macro_snapshots WHERE as_of < ?", (cutoff.isoformat(),)
            )
            return cur.rowcount
