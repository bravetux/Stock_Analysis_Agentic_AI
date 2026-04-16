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
