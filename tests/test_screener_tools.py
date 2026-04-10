# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from src.tools.screener_tools import scrape_screener_in


SAMPLE_SCREENER_HTML = """
<html>
<body>
<ul id="top-ratios">
    <li><span class="name">Stock P/E</span><span class="number">25.5</span></li>
    <li><span class="name">Market Cap</span><span class="number">1,50,000 Cr.</span></li>
    <li><span class="name">Book Value</span><span class="number">850</span></li>
    <li><span class="name">ROCE</span><span class="number">18.5 %</span></li>
    <li><span class="name">ROE</span><span class="number">15.2 %</span></li>
</ul>
<div class="pros">
    <ul>
        <li>Company has delivered good profit growth</li>
        <li>Company has low debt</li>
    </ul>
</div>
<div class="cons">
    <ul>
        <li>Stock is trading at high PE</li>
    </ul>
</div>
</body>
</html>
"""


class TestScrapeScreenerIn:
    @patch("src.tools.screener_tools.httpx")
    def test_extracts_ratios(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_SCREENER_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_screener_in.__wrapped__("RELIANCE")
        assert result["source"] == "Screener.in"
        assert result["stock_pe"] == "25.5"
        assert result["market_cap"] == "1,50,000 Cr."
        assert result["roce"] == "18.5 %"

    @patch("src.tools.screener_tools.httpx")
    def test_extracts_pros_cons(self, mock_httpx):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_SCREENER_HTML
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        result = scrape_screener_in.__wrapped__("RELIANCE")
        assert len(result["pros"]) == 2
        assert len(result["cons"]) == 1

    @patch("src.tools.screener_tools.httpx")
    def test_handles_error(self, mock_httpx):
        mock_httpx.get.side_effect = Exception("Connection failed")
        result = scrape_screener_in.__wrapped__("INVALID")
        assert "error" in result
