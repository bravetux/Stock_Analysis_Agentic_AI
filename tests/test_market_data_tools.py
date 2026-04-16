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
import numpy as np
from unittest.mock import patch, MagicMock
from src.tools.market_data_tools import (
    detect_exchange_for_ticker,
    get_stock_quote,
    get_historical_data,
    get_options_chain,
    get_sector_performance,
)


class TestDetectExchangeForTicker:
    def test_nse_ticker(self):
        result = detect_exchange_for_ticker.__wrapped__("NSE:RELIANCE")
        assert result["exchange"] == "NSE"
        assert result["ticker"] == "RELIANCE"
        assert result["yfinance_ticker"] == "RELIANCE.NS"
        assert result["location"] == "India"

    def test_nasdaq_ticker(self):
        result = detect_exchange_for_ticker.__wrapped__("NASDAQ:AAPL")
        assert result["exchange"] == "NASDAQ"
        assert result["ticker"] == "AAPL"
        assert result["location"] == "United States"

    def test_bse_scrip(self):
        result = detect_exchange_for_ticker.__wrapped__("BSE:500325")
        assert result["exchange"] == "BSE"
        assert result["yfinance_ticker"] == "500325.BO"


class TestGetStockQuote:
    @patch("src.tools.market_data_tools.yf")
    def test_nasdaq_quote(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 175.50,
            "open": 174.00,
            "dayHigh": 176.00,
            "dayLow": 173.50,
            "previousClose": 174.20,
            "volume": 50000000,
            "fiftyTwoWeekHigh": 200.00,
            "fiftyTwoWeekLow": 150.00,
            "marketCap": 2700000000000,
            "longName": "Apple Inc.",
        }
        mock_yf.Ticker.return_value = mock_ticker

        result = get_stock_quote.__wrapped__("AAPL", "NASDAQ")
        assert result["last_price"] == 175.50
        assert result["source"] == "yfinance"
        assert result["company_name"] == "Apple Inc."

    @patch("src.tools.market_data_tools.yf")
    def test_nse_fallback_to_yfinance(self, mock_yf):
        """When nsetools fails, should fall back to yfinance."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 2500.0,
            "longName": "Reliance Industries",
        }
        mock_yf.Ticker.return_value = mock_ticker

        # nsetools will fail in test env, should fall back to yfinance
        result = get_stock_quote.__wrapped__("RELIANCE", "NSE")
        assert "last_price" in result


class TestGetHistoricalData:
    @patch("src.tools.market_data_tools.yf")
    def test_returns_data(self, mock_yf):
        import pandas as pd
        import numpy as np
        dates = pd.date_range(end="2026-04-10", periods=30, freq="B")
        df = pd.DataFrame({
            "Open": np.random.rand(30) * 100 + 100,
            "High": np.random.rand(30) * 100 + 105,
            "Low": np.random.rand(30) * 100 + 95,
            "Close": np.random.rand(30) * 100 + 100,
            "Volume": np.random.randint(100000, 500000, 30),
        }, index=dates)
        mock_yf.download.return_value = df

        result = get_historical_data.__wrapped__("AAPL", "NASDAQ", 30)
        assert result["data_points"] == 30
        assert len(result["data"]) == 30
        assert "open" in result["data"][0]

    @patch("src.tools.market_data_tools.yf")
    def test_empty_data(self, mock_yf):
        import pandas as pd
        mock_yf.download.return_value = pd.DataFrame()

        result = get_historical_data.__wrapped__("INVALID", "NSE", 30)
        assert "error" in result


def _make_stock_df(days: int = 200, base_price: float = 100.0):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")
    np.random.seed(42)
    prices = base_price + np.cumsum(np.random.randn(days) * 2)
    return pd.DataFrame({
        "Open": prices - 1, "High": prices + 2, "Low": prices - 2,
        "Close": prices, "Volume": np.random.randint(100000, 1000000, days),
    }, index=dates)


class TestGetOptionsChain:
    @patch("src.tools.market_data_tools.yf")
    def test_returns_options_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = ("2026-05-16",)
        mock_chain = MagicMock()
        mock_chain.calls = pd.DataFrame({
            "strike": [100, 105, 110],
            "openInterest": [500, 1000, 300],
            "impliedVolatility": [0.25, 0.22, 0.28],
        })
        mock_chain.puts = pd.DataFrame({
            "strike": [95, 100, 105],
            "openInterest": [400, 800, 200],
            "impliedVolatility": [0.30, 0.27, 0.24],
        })
        mock_ticker.option_chain.return_value = mock_chain
        mock_yf.Ticker.return_value = mock_ticker
        result = get_options_chain.__wrapped__("AAPL", "NASDAQ")
        assert "put_call_ratio" in result
        assert "max_pain" in result
        assert "avg_implied_volatility" in result

    @patch("src.tools.market_data_tools.yf")
    def test_no_options_available(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.options = ()
        mock_yf.Ticker.return_value = mock_ticker
        result = get_options_chain.__wrapped__("SMALLCAP", "NSE")
        assert "message" in result


class TestGetSectorPerformance:
    @patch("src.tools.market_data_tools.yf")
    def test_returns_sector_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {"sector": "Technology"}
        mock_yf.Ticker.return_value = mock_ticker
        mock_yf.download.return_value = _make_stock_df(days=200)
        result = get_sector_performance.__wrapped__("AAPL", "NASDAQ")
        assert "sector" in result
        assert "relative_strength" in result

    @patch("src.tools.market_data_tools.yf")
    def test_missing_sector(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker
        result = get_sector_performance.__wrapped__("UNKNOWN", "NSE")
        assert "error" in result
