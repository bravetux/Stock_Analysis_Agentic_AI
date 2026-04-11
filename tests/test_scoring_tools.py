import pytest
from src.tools.scoring_tools import calculate_composite_score


class TestCalculateCompositeScore:
    def test_bullish_scenario(self):
        technical = {
            "trend_score": 80, "trend_direction": "UP",
            "macd_signal": "BULLISH", "rsi": 55,
            "obv_trend": "RISING", "price_trend": "RISING",
            "nearest_support_distance": 5.0, "patterns": [],
        }
        fundamental = {
            "pe_vs_sector": "BELOW", "roe": 20.0, "roce": 18.0,
            "earnings_growth": 15.0, "revenue_growth": 12.0,
            "debt_to_equity": 0.5, "insider_sentiment": "NET_BUYING",
        }
        sentiment = {
            "positive_pct": 70, "negative_pct": 10, "neutral_pct": 20,
            "analyst_consensus": "BUY", "insider_direction": "NET_BUYING",
            "trends_momentum": "RISING",
        }
        market = {"current_price": 3200, "atr": 50, "nearest_resistance": 3400, "nearest_support": 3100}
        result = calculate_composite_score.__wrapped__(technical, fundamental, sentiment, market)
        assert result["composite_score"] >= 65
        assert result["signal"] in ("BUY", "STRONG_BUY")
        assert "sub_scores" in result
        assert "confidence" in result
        assert "bull_case" in result
        assert "bear_case" in result

    def test_bearish_scenario(self):
        technical = {
            "trend_score": 20, "trend_direction": "DOWN",
            "macd_signal": "BEARISH", "rsi": 75,
            "obv_trend": "FALLING", "price_trend": "FALLING",
            "nearest_support_distance": 2.0,
            "patterns": [{"signal": "BEARISH"}],
        }
        fundamental = {
            "pe_vs_sector": "ABOVE", "roe": 5.0, "roce": 4.0,
            "earnings_growth": -10.0, "revenue_growth": -5.0,
            "debt_to_equity": 2.5, "insider_sentiment": "NET_SELLING",
        }
        sentiment = {
            "positive_pct": 15, "negative_pct": 65, "neutral_pct": 20,
            "analyst_consensus": "SELL", "insider_direction": "NET_SELLING",
            "trends_momentum": "FALLING",
        }
        market = {"current_price": 2800, "atr": 60, "nearest_resistance": 3000, "nearest_support": 2600}
        result = calculate_composite_score.__wrapped__(technical, fundamental, sentiment, market)
        assert result["composite_score"] <= 44
        assert result["signal"] in ("SELL", "STRONG_SELL")

    def test_mixed_signals(self):
        technical = {
            "trend_score": 60, "trend_direction": "UP",
            "macd_signal": "BULLISH", "rsi": 50,
            "obv_trend": "RISING", "price_trend": "RISING",
            "nearest_support_distance": 3.0, "patterns": [],
        }
        fundamental = {
            "pe_vs_sector": "ABOVE", "roe": 10.0, "roce": 8.0,
            "earnings_growth": 5.0, "revenue_growth": 3.0,
            "debt_to_equity": 1.5, "insider_sentiment": "NEUTRAL",
        }
        sentiment = {
            "positive_pct": 40, "negative_pct": 35, "neutral_pct": 25,
            "analyst_consensus": "HOLD", "insider_direction": "NEUTRAL",
            "trends_momentum": "STABLE",
        }
        market = {"current_price": 3000, "atr": 45, "nearest_resistance": 3100, "nearest_support": 2900}
        result = calculate_composite_score.__wrapped__(technical, fundamental, sentiment, market)
        assert 30 <= result["composite_score"] <= 79
        assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")

    def test_score_range(self):
        technical = {"trend_score": 50, "trend_direction": "SIDEWAYS",
                     "macd_signal": "NEUTRAL", "rsi": 50,
                     "obv_trend": "RISING", "price_trend": "RISING",
                     "nearest_support_distance": 5.0, "patterns": []}
        fundamental = {"pe_vs_sector": "BELOW", "roe": 15, "roce": 12,
                       "earnings_growth": 10, "revenue_growth": 8,
                       "debt_to_equity": 1.0, "insider_sentiment": "NEUTRAL"}
        sentiment = {"positive_pct": 50, "negative_pct": 25, "neutral_pct": 25,
                     "analyst_consensus": "HOLD", "insider_direction": "NEUTRAL",
                     "trends_momentum": "STABLE"}
        market = {"current_price": 100, "atr": 5, "nearest_resistance": 110, "nearest_support": 90}
        result = calculate_composite_score.__wrapped__(technical, fundamental, sentiment, market)
        assert 0 <= result["composite_score"] <= 100

    def test_signal_always_valid(self):
        technical = {"trend_score": 50, "trend_direction": "UP",
                     "macd_signal": "BULLISH", "rsi": 50,
                     "obv_trend": "RISING", "price_trend": "RISING",
                     "nearest_support_distance": 5.0, "patterns": []}
        fundamental = {"pe_vs_sector": "BELOW", "roe": 15, "roce": 12,
                       "earnings_growth": 10, "revenue_growth": 8,
                       "debt_to_equity": 1.0, "insider_sentiment": "NEUTRAL"}
        sentiment = {"positive_pct": 50, "negative_pct": 25, "neutral_pct": 25,
                     "analyst_consensus": "HOLD", "insider_direction": "NEUTRAL",
                     "trends_momentum": "STABLE"}
        market = {"current_price": 100, "atr": 5, "nearest_resistance": 110, "nearest_support": 90}
        result = calculate_composite_score.__wrapped__(technical, fundamental, sentiment, market)
        assert result["signal"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")
