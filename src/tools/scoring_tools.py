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

import logging
from strands import tool
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _technical_score(data: dict) -> tuple[int, dict]:
    """Calculate technical sub-score (0-100)."""
    score = 0
    components = {}

    # Trend strength (30%)
    trend_score = data.get("trend_score", 50)
    trend_pts = round(trend_score * 0.30)
    components["trend_strength"] = trend_pts
    score += trend_pts

    # Momentum — MACD + RSI (25%)
    momentum_pts = 0
    macd = data.get("macd_signal", "NEUTRAL")
    if macd == "BULLISH":
        momentum_pts += 15
    elif macd == "BEARISH":
        momentum_pts += 0
    else:
        momentum_pts += 7

    rsi = data.get("rsi", 50)
    if 40 <= rsi <= 60:
        momentum_pts += 10
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        momentum_pts += 5

    components["momentum"] = momentum_pts
    score += momentum_pts

    # Volume confirmation (20%)
    obv_trend = data.get("obv_trend", "")
    price_trend = data.get("price_trend", "")
    if obv_trend == price_trend and obv_trend in ("RISING", "FALLING"):
        vol_pts = 20
    elif obv_trend in ("RISING",) and price_trend in ("RISING",):
        vol_pts = 20
    else:
        vol_pts = 5
    components["volume_confirmation"] = vol_pts
    score += vol_pts

    # Support proximity (15%)
    support_dist = data.get("nearest_support_distance", 10)
    if support_dist > 10:
        support_pts = 15
    elif support_dist > 5:
        support_pts = 10
    else:
        support_pts = 5
    components["support_proximity"] = support_pts
    score += support_pts

    # Chart patterns (10%)
    patterns = data.get("patterns", [])
    bullish_patterns = sum(1 for p in patterns if p.get("signal") == "BULLISH")
    bearish_patterns = sum(1 for p in patterns if p.get("signal") == "BEARISH")
    if bullish_patterns > bearish_patterns:
        pattern_pts = 10
    elif bearish_patterns > bullish_patterns:
        pattern_pts = 0
    else:
        pattern_pts = 5
    components["patterns"] = pattern_pts
    score += pattern_pts

    return min(100, score), components


def _fundamental_score(data: dict) -> tuple[int, dict]:
    """Calculate fundamental sub-score (0-100)."""
    score = 0
    components = {}

    # Valuation — PE vs sector (25%)
    pe_status = data.get("pe_vs_sector", "FAIR")
    if pe_status == "BELOW":
        val_pts = 25
    elif pe_status == "FAIR":
        val_pts = 15
    else:
        val_pts = 5
    components["valuation"] = val_pts
    score += val_pts

    # Quality — ROE + ROCE (25%)
    roe = data.get("roe", 0) or 0
    roce = data.get("roce", 0) or 0
    avg_quality = (roe + roce) / 2
    if avg_quality >= 15:
        quality_pts = 25
    elif avg_quality >= 10:
        quality_pts = 15
    else:
        quality_pts = 5
    components["quality"] = quality_pts
    score += quality_pts

    # Growth (20%)
    eg = data.get("earnings_growth", 0) or 0
    rg = data.get("revenue_growth", 0) or 0
    avg_growth = (eg + rg) / 2
    if avg_growth >= 15:
        growth_pts = 20
    elif avg_growth >= 5:
        growth_pts = 12
    elif avg_growth >= 0:
        growth_pts = 6
    else:
        growth_pts = 0
    components["growth"] = growth_pts
    score += growth_pts

    # Debt health (15%)
    dte = data.get("debt_to_equity", 1.0) or 1.0
    if dte < 0.5:
        debt_pts = 15
    elif dte < 1.0:
        debt_pts = 10
    elif dte < 2.0:
        debt_pts = 5
    else:
        debt_pts = 0
    components["debt_health"] = debt_pts
    score += debt_pts

    # Insider conviction (15%)
    insider = data.get("insider_sentiment", "NEUTRAL")
    if insider == "NET_BUYING":
        insider_pts = 15
    elif insider == "NEUTRAL":
        insider_pts = 7
    else:
        insider_pts = 0
    components["insider_conviction"] = insider_pts
    score += insider_pts

    return min(100, score), components


def _sentiment_score(data: dict) -> tuple[int, dict]:
    """Calculate sentiment sub-score (0-100)."""
    score = 0
    components = {}

    # News sentiment ratio (35%)
    pos = data.get("positive_pct", 33) or 33
    neg = data.get("negative_pct", 33) or 33
    sentiment_ratio = pos / (pos + neg) if (pos + neg) > 0 else 0.5
    news_pts = round(sentiment_ratio * 35)
    components["news_sentiment"] = news_pts
    score += news_pts

    # Analyst consensus (25%)
    consensus = data.get("analyst_consensus", "HOLD")
    consensus_map = {"STRONG_BUY": 25, "BUY": 20, "HOLD": 12, "SELL": 5, "STRONG_SELL": 0}
    analyst_pts = consensus_map.get(consensus, 12)
    components["analyst_consensus"] = analyst_pts
    score += analyst_pts

    # Insider direction (20%)
    insider_dir = data.get("insider_direction", "NEUTRAL")
    if insider_dir == "NET_BUYING":
        insider_pts = 20
    elif insider_dir == "NEUTRAL":
        insider_pts = 10
    else:
        insider_pts = 0
    components["insider_direction"] = insider_pts
    score += insider_pts

    # Google Trends momentum (20%)
    trends = data.get("trends_momentum", "STABLE")
    if trends == "RISING":
        trends_pts = 20
    elif trends == "STABLE":
        trends_pts = 10
    else:
        trends_pts = 5
    components["trends_momentum"] = trends_pts
    score += trends_pts

    return min(100, score), components


@tool
def calculate_composite_score(
    technical_data: dict,
    fundamental_data: dict,
    sentiment_data: dict,
    market_data: dict,
) -> dict:
    """Calculate composite stock score (0-100) from technical, fundamental, and sentiment data.
    Returns score, signal (STRONG_BUY to STRONG_SELL), confidence level, and bull/bear cases."""
    tech_score, tech_components = _technical_score(technical_data)
    fund_score, fund_components = _fundamental_score(fundamental_data)
    sent_score, sent_components = _sentiment_score(sentiment_data)

    tw = settings.technical_weight
    fw = settings.fundamental_weight
    sw = settings.sentiment_weight

    composite = round(tech_score * tw + fund_score * fw + sent_score * sw)
    composite = max(0, min(100, composite))

    if composite >= 80:
        signal = "STRONG_BUY"
    elif composite >= 65:
        signal = "BUY"
    elif composite >= 45:
        signal = "HOLD"
    elif composite >= 30:
        signal = "SELL"
    else:
        signal = "STRONG_SELL"

    scores = [tech_score, fund_score, sent_score]
    spread = max(scores) - min(scores)
    if spread <= 15:
        confidence = "HIGH"
    elif spread <= 30:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    price = market_data.get("current_price", 0)
    atr = market_data.get("atr", 0)
    resistance = market_data.get("nearest_resistance", price + 2 * atr)
    support = market_data.get("nearest_support", price - 2 * atr)

    bull_price = max(price + 2 * atr, resistance) if atr else resistance
    bear_price = min(price - 2 * atr, support) if atr else support

    bull_pct = round(((bull_price - price) / price) * 100, 1) if price else 0
    bear_pct = round(((bear_price - price) / price) * 100, 1) if price else 0

    return {
        "composite_score": composite,
        "signal": signal,
        "sub_scores": {
            "technical": {"score": tech_score, "weight": tw, "components": tech_components},
            "fundamental": {"score": fund_score, "weight": fw, "components": fund_components},
            "sentiment": {"score": sent_score, "weight": sw, "components": sent_components},
        },
        "confidence": confidence,
        "risk_level": "LOW" if composite >= 65 else "MODERATE" if composite >= 45 else "HIGH",
        "bull_case": {"price": round(bull_price, 2), "change_pct": bull_pct},
        "bear_case": {"price": round(bear_price, 2), "change_pct": bear_pct},
    }
