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
import pandas as pd
from unittest.mock import patch, MagicMock
from src.tools.news_tools import (
    search_google_news,
    search_news_batch,
    extract_article_content,
    search_location_news,
    get_google_trends,
)


class TestSearchGoogleNews:
    @patch("src.tools.news_tools.GoogleNews")
    def test_returns_articles(self, MockGN):
        mock_gn = MagicMock()
        MockGN.return_value = mock_gn
        mock_gn.results.return_value = [
            {"title": "Stock surges", "date": "2 hours ago", "media": "Reuters", "link": "http://example.com/1", "desc": "Stock went up"},
            {"title": "Earnings beat", "date": "1 day ago", "media": "CNBC", "link": "http://example.com/2", "desc": "Earnings exceeded"},
        ]

        result = search_google_news.__wrapped__("RELIANCE quarterly results", "1m")
        assert len(result) == 2
        assert result[0]["title"] == "Stock surges"
        assert result[0]["source"] == "Reuters"


class TestSearchNewsBatch:
    @patch("src.tools.news_tools.GoogleNews")
    def test_batch_search(self, MockGN):
        mock_gn = MagicMock()
        MockGN.return_value = mock_gn
        mock_gn.results.return_value = [
            {"title": "Test article", "date": "1d", "media": "Test", "link": "http://example.com/1", "desc": "desc"},
        ]

        result = search_news_batch.__wrapped__("RELIANCE", "Reliance Industries", "NSE", max_queries=5)
        assert result["queries_executed"] == 5
        assert result["total_articles"] > 0

    @patch("src.tools.news_tools.GoogleNews")
    def test_deduplication(self, MockGN):
        mock_gn = MagicMock()
        MockGN.return_value = mock_gn
        # Same URL returned for all queries
        mock_gn.results.return_value = [
            {"title": "Same article", "date": "1d", "media": "Test", "link": "http://example.com/same", "desc": "same"},
        ]

        result = search_news_batch.__wrapped__("TCS", "TCS Ltd", "NSE", max_queries=5)
        # Should deduplicate to just 1 article
        assert result["total_articles"] == 1


class TestSearchLocationNews:
    @patch("src.tools.news_tools.GoogleNews")
    def test_india_sources(self, MockGN):
        mock_gn = MagicMock()
        MockGN.return_value = mock_gn
        mock_gn.results.return_value = [
            {"title": "India news", "date": "1d", "media": "MoneyControl", "link": "http://mc.com/1", "desc": "desc"},
        ]

        result = search_location_news.__wrapped__("RELIANCE", "NSE")
        assert result["location"] == "India"
        assert result["sources_searched"] == 8  # 8 Indian sources

    @patch("src.tools.news_tools.GoogleNews")
    def test_us_sources(self, MockGN):
        mock_gn = MagicMock()
        MockGN.return_value = mock_gn
        mock_gn.results.return_value = []

        result = search_location_news.__wrapped__("AAPL", "NASDAQ")
        assert result["location"] == "United States"
        assert result["sources_searched"] == 8  # 8 US sources


class TestGetGoogleTrends:
    @patch("src.tools.news_tools.TrendReq")
    def test_returns_trends_data(self, mock_trend_class):
        mock_pytrends = MagicMock()
        mock_pytrends.interest_over_time.return_value = pd.DataFrame({
            "Reliance Industries": [50, 60, 70, 80, 65, 75],
            "isPartial": [False] * 6,
        }, index=pd.date_range("2026-01-01", periods=6, freq="W"))
        mock_pytrends.related_queries.return_value = {
            "Reliance Industries": {"rising": pd.DataFrame({"query": ["reliance jio", "reliance share"], "value": [100, 80]})}
        }
        mock_trend_class.return_value = mock_pytrends

        result = get_google_trends.__wrapped__("RELIANCE", "Reliance Industries")
        assert "current_interest" in result
        assert "trend" in result
        assert result["trend"] in ("RISING", "FALLING", "STABLE")

    @patch("src.tools.news_tools.TrendReq")
    def test_handles_no_data(self, mock_trend_class):
        mock_pytrends = MagicMock()
        mock_pytrends.interest_over_time.return_value = pd.DataFrame()
        mock_trend_class.return_value = mock_pytrends

        result = get_google_trends.__wrapped__("OBSCURE", "Obscure Corp")
        assert "message" in result
