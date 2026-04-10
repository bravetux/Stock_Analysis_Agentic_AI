# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from src.tools.chartink_tools import scrape_chartink_screener


SAMPLE_CHARTINK_PAGE = """
<html>
<head><meta name="csrf-token" content="test-csrf-token-12345"></head>
<body></body>
</html>
"""


class TestScrapeChartinkScreener:
    @patch("src.tools.chartink_tools.httpx")
    def test_successful_scan(self, mock_httpx):
        # First call: GET for CSRF token
        mock_csrf_resp = MagicMock()
        mock_csrf_resp.text = SAMPLE_CHARTINK_PAGE
        mock_csrf_resp.cookies = {"session": "test123"}

        # Second call: POST screener query
        mock_post_resp = MagicMock()
        mock_post_resp.json.return_value = {
            "data": [
                {"nsecode": "RELIANCE", "bsecode": "500325", "per_chg": "2.5", "close": "2500", "volume": "1000000"},
                {"nsecode": "TCS", "bsecode": "532540", "per_chg": "1.2", "close": "3500", "volume": "500000"},
            ]
        }
        mock_post_resp.raise_for_status = MagicMock()

        mock_httpx.get.return_value = mock_csrf_resp
        mock_httpx.post.return_value = mock_post_resp

        scan = "( {cash} ( latest close > latest sma( close,200 ) ) )"
        result = scrape_chartink_screener.__wrapped__(scan)
        assert result["source"] == "Chartink"
        assert result["total_matches"] == 2
        assert result["stocks"][0]["name"] == "RELIANCE"

    @patch("src.tools.chartink_tools.httpx")
    def test_missing_csrf(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = "<html><head></head></html>"
        mock_httpx.get.return_value = mock_resp

        result = scrape_chartink_screener.__wrapped__("test scan")
        assert "error" in result
