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
# Developed: 10th April 2026

import pytest
from src.config.settings import Settings


def test_report_cache_hours_default():
    s = Settings()
    assert s.report_cache_hours == 720


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
