# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from src.tools.market_data_tools import (
    detect_exchange_for_ticker,
    get_stock_quote,
    get_historical_data,
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
