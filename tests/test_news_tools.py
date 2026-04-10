# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from src.tools.news_tools import (
    search_google_news,
    search_news_batch,
    extract_article_content,
    search_location_news,
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
