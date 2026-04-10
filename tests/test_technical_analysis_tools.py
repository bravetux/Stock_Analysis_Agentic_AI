# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_macd,
    calculate_support_resistance,
    estimate_next_high_low,
    get_technical_summary,
)


def _make_price_df(days: int = 300, base_price: float = 100.0, trend: float = 0.1):
    """Generate synthetic price data for testing."""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")
    np.random.seed(42)
    noise = np.random.randn(days) * 2
    prices = base_price + np.cumsum(noise) + np.arange(days) * trend

    df = pd.DataFrame({
        "Open": prices - np.random.rand(days),
        "High": prices + np.abs(np.random.randn(days) * 1.5),
        "Low": prices - np.abs(np.random.randn(days) * 1.5),
        "Close": prices,
        "Volume": np.random.randint(100000, 1000000, days),
    }, index=dates)
    return df


class TestCalculate200DMA:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_dma_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=300)
        result = calculate_200dma.__wrapped__("RELIANCE", "NSE")
        assert "current_price" in result
        assert "dma_value" in result
        assert "price_vs_dma" in result
        assert result["price_vs_dma"] in ("ABOVE", "BELOW")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_detects_breakpoints(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=300)
        result = calculate_200dma.__wrapped__("RELIANCE", "NSE")
        assert "recent_breakpoints" in result
        assert isinstance(result["recent_breakpoints"], list)

    @patch("src.tools.technical_analysis_tools.yf")
    def test_signal_field(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=300)
        result = calculate_200dma.__wrapped__("AAPL", "NASDAQ")
        assert result["signal"] in ("BULLISH", "BEARISH", "NEUTRAL")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_200dma.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateMACD:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_macd_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_macd.__wrapped__("TCS", "NSE")
        assert "macd_line" in result
        assert "signal_line" in result
        assert "histogram" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_crossover_detection(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_macd.__wrapped__("AAPL", "NASDAQ")
        assert "recent_crossovers" in result
        assert isinstance(result["recent_crossovers"], list)

    @patch("src.tools.technical_analysis_tools.yf")
    def test_signal_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_macd.__wrapped__("INFY", "NSE")
        assert result["signal"] in ("BULLISH", "BEARISH", "NEUTRAL")


class TestEstimateNextHighLow:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_estimates(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = estimate_next_high_low.__wrapped__("RELIANCE", "NSE")
        assert "short_term_estimate" in result
        assert "medium_term_estimate" in result
        assert "expected_high" in result["short_term_estimate"]
        assert "expected_low" in result["short_term_estimate"]

    @patch("src.tools.technical_analysis_tools.yf")
    def test_high_greater_than_low(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = estimate_next_high_low.__wrapped__("AAPL", "NASDAQ")
        if "error" not in result:
            assert result["short_term_estimate"]["expected_high"] > result["short_term_estimate"]["expected_low"]

    @patch("src.tools.technical_analysis_tools.yf")
    def test_disclaimer_present(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = estimate_next_high_low.__wrapped__("MSFT", "NASDAQ")
        if "error" not in result:
            assert "disclaimer" in result


class TestGetTechnicalSummary:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_indicators(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = get_technical_summary.__wrapped__("RELIANCE", "NSE")
        assert "current_price" in result
        assert "rsi_14" in result or "error" not in result
