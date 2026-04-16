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
from unittest.mock import patch, MagicMock
from src.tools.scraping_tools import (
    scrape_google_finance,
    scrape_yahoo_finance_page,
    scrape_moneycontrol,
    scrape_trendlyne,
    scrape_tickertape,
)


SAMPLE_GF_HTML = """
<html>
<body>
<div class="YMlKec fxKbKc">$175.50</div>
<div class="P6K39c">
    <div class="mfs7Fc">Market cap</div>
    <div class="YMlKec">2.7T</div>
</div>
<div class="bLLb2d">Apple Inc. designs and sells consumer electronics.</div>
<div class="Yfwt5">Apple reports record quarterly revenue</div>
<div class="Yfwt5">iPhone sales exceed expectations</div>
</body>
</html>
"""

SAMPLE_YF_HTML = """
<html>
<body>
<table>
<tr><td>Previous Close</td><td>174.20</td></tr>
<tr><td>Open</td><td>175.00</td></tr>
<tr><td>Day's Range</td><td>173.50 - 176.00</td></tr>
</table>
</body>
</html>
"""


class TestScrapeGoogleFinance:
    @patch("src.tools.scraping_tools.httpx")
    def test_extracts_price(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_GF_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_google_finance.__wrapped__("AAPL", "NASDAQ")
        assert result["source"] == "Google Finance"
        assert result["current_price"] == "$175.50"

    @patch("src.tools.scraping_tools.httpx")
    def test_extracts_stats(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_GF_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_google_finance.__wrapped__("AAPL", "NASDAQ")
        assert "Market cap" in result.get("stats", {})

    @patch("src.tools.scraping_tools.httpx")
    def test_extracts_news(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_GF_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_google_finance.__wrapped__("AAPL", "NASDAQ")
        assert len(result["news_headlines"]) == 2

    @patch("src.tools.scraping_tools._safe_get")
    def test_handles_failure(self, mock_get):
        mock_get.return_value = None
        result = scrape_google_finance.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestScrapeYahooFinancePage:
    @patch("src.tools.scraping_tools.httpx")
    def test_extracts_stats(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_YF_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_yahoo_finance_page.__wrapped__("AAPL", "NASDAQ")
        assert result["source"] == "Yahoo Finance"
        assert "Previous Close" in result.get("summary_stats", {})


class TestScrapeTrendlyne:
    @patch("src.tools.scraping_tools._safe_get")
    def test_returns_trendlyne_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = '<html><body><table><tr><td>DMA 200</td><td>Above</td></tr></table></body></html>'
        mock_get.return_value = mock_response
        result = scrape_trendlyne.__wrapped__("RELIANCE")
        assert "source" in result
        assert result["source"] == "trendlyne"
        assert "data" in result

    @patch("src.tools.scraping_tools._safe_get")
    def test_handles_failure(self, mock_get):
        mock_get.return_value = None
        result = scrape_trendlyne.__wrapped__("INVALID")
        assert "error" in result


class TestScrapeTickertape:
    @patch("src.tools.scraping_tools._safe_get")
    def test_returns_tickertape_data(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = '<html><body><table><tr><td>TCS</td><td>PE: 25</td></tr></table></body></html>'
        mock_get.return_value = mock_response
        result = scrape_tickertape.__wrapped__("RELIANCE")
        assert "source" in result
        assert result["source"] == "tickertape"
        assert "data" in result

    @patch("src.tools.scraping_tools._safe_get")
    def test_handles_failure(self, mock_get):
        mock_get.return_value = None
        result = scrape_tickertape.__wrapped__("INVALID")
        assert "error" in result
