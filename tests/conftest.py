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

import os
import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Set test environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.2")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "4096")
    monkeypatch.setenv("DEFAULT_EXCHANGE", "NSE")
    monkeypatch.setenv("STOCKS_FILE", "stocks.txt")
    monkeypatch.setenv("NEWS_SEARCH_COUNT", "10")
    monkeypatch.setenv("SCRAPE_DELAY_SECONDS", "0")
    monkeypatch.setenv("NEWS_API_DELAY", "0")
    monkeypatch.setenv("RISK_FREE_RATE", "0.065")
    monkeypatch.setenv("VAR_CONFIDENCE", "0.95")
    monkeypatch.setenv("TECHNICAL_WEIGHT", "0.40")
    monkeypatch.setenv("FUNDAMENTAL_WEIGHT", "0.35")
    monkeypatch.setenv("SENTIMENT_WEIGHT", "0.25")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("CACHE_DIR", ".test-cache")
    monkeypatch.setenv("TRENDS_TIMEFRAME", "today 3-m")
    monkeypatch.setenv("REPORT_CACHE_HOURS", "720")
    monkeypatch.setenv("REPORTS_DIR", ".test-reports")
    monkeypatch.setenv("DB_PATH", ":memory:")
