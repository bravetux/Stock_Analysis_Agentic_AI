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
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_macd,
    calculate_support_resistance,
    estimate_next_high_low,
    get_technical_summary,
    calculate_ema_crossovers,
    detect_golden_death_cross,
    calculate_fibonacci_levels,
    calculate_vwap,
    calculate_obv,
    calculate_ichimoku,
    calculate_williams_r,
    calculate_adx_directional,
    calculate_trend_strength,
    detect_chart_patterns,
    calculate_risk_metrics,
    calculate_relative_strength,
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


class TestCalculateEMACrossovers:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_ema_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ema_crossovers.__wrapped__("RELIANCE", "NSE")
        assert "ema_9" in result
        assert "ema_21" in result
        assert "ema_50" in result
        assert "alignment" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_alignment_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ema_crossovers.__wrapped__("AAPL", "NASDAQ")
        assert result["alignment"] in ("BULLISH", "BEARISH", "MIXED")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_crossover_signals(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ema_crossovers.__wrapped__("TCS", "NSE")
        assert "short_term_signal" in result
        assert "medium_term_signal" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_ema_crossovers.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestDetectGoldenDeathCross:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_cross_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=300)
        result = detect_golden_death_cross.__wrapped__("RELIANCE", "NSE")
        assert "current_state" in result
        assert "sma_50" in result
        assert "sma_200" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_state_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=300)
        result = detect_golden_death_cross.__wrapped__("AAPL", "NASDAQ")
        assert result["current_state"] in ("GOLDEN_CROSS", "DEATH_CROSS", "NEITHER")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = detect_golden_death_cross.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateFibonacciLevels:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_fib_levels(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_fibonacci_levels.__wrapped__("RELIANCE", "NSE")
        assert "levels" in result
        levels = result["levels"]
        assert "23.6%" in levels
        assert "38.2%" in levels
        assert "50.0%" in levels
        assert "61.8%" in levels

    @patch("src.tools.technical_analysis_tools.yf")
    def test_nearest_level(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_fibonacci_levels.__wrapped__("AAPL", "NASDAQ")
        assert "nearest_support" in result
        assert "nearest_resistance" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_fibonacci_levels.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateVWAP:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_vwap_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_vwap.__wrapped__("RELIANCE", "NSE")
        assert "vwap" in result
        assert "price_vs_vwap" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_price_vs_vwap_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_vwap.__wrapped__("TCS", "NSE")
        assert result["price_vs_vwap"] in ("ABOVE", "BELOW")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_vwap.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateOBV:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_obv_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_obv.__wrapped__("RELIANCE", "NSE")
        assert "obv" in result
        assert "obv_trend" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_obv_trend_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_obv.__wrapped__("AAPL", "NASDAQ")
        assert result["obv_trend"] in ("RISING", "FALLING")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_divergence_field(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_obv.__wrapped__("TCS", "NSE")
        assert result["divergence"] in ("BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NONE")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_obv.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateIchimoku:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_ichimoku_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ichimoku.__wrapped__("RELIANCE", "NSE")
        assert "tenkan_sen" in result
        assert "kijun_sen" in result
        assert "cloud_color" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_cloud_color_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ichimoku.__wrapped__("AAPL", "NASDAQ")
        assert result["cloud_color"] in ("GREEN", "RED")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_price_vs_cloud(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_ichimoku.__wrapped__("TCS", "NSE")
        assert result["price_vs_cloud"] in ("ABOVE", "INSIDE", "BELOW")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_ichimoku.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateWilliamsR:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_williams_r(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_williams_r.__wrapped__("RELIANCE", "NSE")
        assert "williams_r" in result
        assert "signal" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_signal_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_williams_r.__wrapped__("AAPL", "NASDAQ")
        assert result["signal"] in ("OVERBOUGHT", "OVERSOLD", "NEUTRAL")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_williams_r.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateADXDirectional:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_adx_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_adx_directional.__wrapped__("RELIANCE", "NSE")
        assert "adx" in result
        assert "plus_di" in result
        assert "minus_di" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_trend_direction(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_adx_directional.__wrapped__("AAPL", "NASDAQ")
        assert result["trend_direction"] in ("BULLISH", "BEARISH")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_trend_strength(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = calculate_adx_directional.__wrapped__("TCS", "NSE")
        assert result["trend_strength"] in ("STRONG", "WEAK")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_adx_directional.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateTrendStrength:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_trend_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_trend_strength.__wrapped__("RELIANCE", "NSE")
        assert "trend_score" in result
        assert 0 <= result["trend_score"] <= 100
        assert "trend_direction" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_direction_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_trend_strength.__wrapped__("AAPL", "NASDAQ")
        assert result["trend_direction"] in ("UP", "DOWN", "SIDEWAYS")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_trend_strength.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestDetectChartPatterns:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_patterns(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=150)
        result = detect_chart_patterns.__wrapped__("RELIANCE", "NSE")
        assert "patterns" in result
        assert isinstance(result["patterns"], list)

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = detect_chart_patterns.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateRiskMetrics:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_risk_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=365)
        result = calculate_risk_metrics.__wrapped__("RELIANCE", "NSE")
        assert "sharpe_ratio" in result
        assert "max_drawdown_pct" in result
        assert "beta" in result
        assert "var_95" in result
        assert "volatility" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_risk_metrics.__wrapped__("INVALID", "NSE")
        assert "error" in result


class TestCalculateRelativeStrength:
    @patch("src.tools.technical_analysis_tools.yf")
    def test_returns_rs_data(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_relative_strength.__wrapped__("RELIANCE", "NSE")
        assert "relative_performance" in result
        assert "classification" in result

    @patch("src.tools.technical_analysis_tools.yf")
    def test_classification_values(self, mock_yf):
        mock_yf.download.return_value = _make_price_df(days=200)
        result = calculate_relative_strength.__wrapped__("AAPL", "NASDAQ")
        assert result["classification"] in ("OUTPERFORMING", "UNDERPERFORMING", "IN_LINE")

    @patch("src.tools.technical_analysis_tools.yf")
    def test_empty_data(self, mock_yf):
        mock_yf.download.return_value = pd.DataFrame()
        result = calculate_relative_strength.__wrapped__("INVALID", "NSE")
        assert "error" in result
