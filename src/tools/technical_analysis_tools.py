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
import yfinance as yf
import pandas as pd
import numpy as np
import pandas_ta as ta
from strands import tool
from src.config.exchanges import ExchangeEnum, normalize_ticker, get_display_ticker
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _fetch_price_data(ticker: str, exchange: str, period: str = "1y") -> pd.DataFrame:
    """Fetch and clean price data from yfinance."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    df = yf.download(yf_ticker, period=period, progress=False)
    if df.empty:
        return df
    # Flatten multi-level columns
    if hasattr(df.columns, 'levels') and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)
    return df


@tool
def calculate_200dma(ticker: str, exchange: str) -> dict:
    """Calculate 200-Day Moving Average analysis with breakpoint detection.
    Returns current price vs 200DMA, trend, and recent crossover dates."""
    df = _fetch_price_data(ticker, exchange, period="2y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    dma_period = settings.dma_period
    df["SMA_200"] = ta.sma(df["Close"], length=dma_period)
    df = df.dropna(subset=["SMA_200"])

    if df.empty:
        return {"error": f"Insufficient data for {dma_period}-DMA calculation"}

    current_price = round(float(df["Close"].iloc[-1]), 2)
    current_dma = round(float(df["SMA_200"].iloc[-1]), 2)
    above_dma = current_price > current_dma
    distance_pct = round(((current_price - current_dma) / current_dma) * 100, 2)

    # Detect crossovers (breakpoints)
    df["above"] = df["Close"] > df["SMA_200"]
    df["crossover"] = df["above"].ne(df["above"].shift())
    crossovers = df[df["crossover"]].tail(10)

    breakpoints = []
    for date, row in crossovers.iterrows():
        breakpoints.append({
            "date": date.strftime("%Y-%m-%d"),
            "direction": "BULLISH (crossed above)" if row["above"] else "BEARISH (crossed below)",
            "price": round(float(row["Close"]), 2),
            "dma_value": round(float(row["SMA_200"]), 2),
        })

    # Trend determination
    sma_values = df["SMA_200"].tail(20)
    trend = "RISING" if sma_values.iloc[-1] > sma_values.iloc[0] else "FALLING"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "dma_period": dma_period,
        "current_price": current_price,
        "dma_value": current_dma,
        "price_vs_dma": "ABOVE" if above_dma else "BELOW",
        "distance_percent": distance_pct,
        "dma_trend": trend,
        "recent_breakpoints": breakpoints,
        "signal": "BULLISH" if above_dma and trend == "RISING" else
                  "BEARISH" if not above_dma and trend == "FALLING" else "NEUTRAL",
    }


@tool
def calculate_macd(ticker: str, exchange: str) -> dict:
    """Calculate MACD (12, 26, 9) indicator with crossover detection.
    Returns MACD line, signal line, histogram, and bullish/bearish signals."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    if macd_df is None or macd_df.empty:
        return {"error": "MACD calculation failed"}

    df = pd.concat([df, macd_df], axis=1)
    df = df.dropna()

    if df.empty:
        return {"error": "Insufficient data for MACD"}

    macd_col = [c for c in df.columns if "MACD_12_26_9" in str(c) and "h" not in str(c).lower() and "s" not in str(c).lower()]
    signal_col = [c for c in df.columns if "MACDs_12_26_9" in str(c)]
    hist_col = [c for c in df.columns if "MACDh_12_26_9" in str(c)]

    if not macd_col or not signal_col or not hist_col:
        return {"error": "MACD columns not found"}

    macd_col, signal_col, hist_col = macd_col[0], signal_col[0], hist_col[0]

    current_macd = round(float(df[macd_col].iloc[-1]), 4)
    current_signal = round(float(df[signal_col].iloc[-1]), 4)
    current_hist = round(float(df[hist_col].iloc[-1]), 4)

    # Detect crossovers
    df["macd_above_signal"] = df[macd_col] > df[signal_col]
    df["macd_crossover"] = df["macd_above_signal"].ne(df["macd_above_signal"].shift())
    crossovers = df[df["macd_crossover"]].tail(5)

    signals = []
    for date, row in crossovers.iterrows():
        signals.append({
            "date": date.strftime("%Y-%m-%d"),
            "type": "BULLISH CROSSOVER" if row["macd_above_signal"] else "BEARISH CROSSOVER",
            "macd": round(float(row[macd_col]), 4),
            "signal": round(float(row[signal_col]), 4),
        })

    # Histogram trend
    recent_hist = df[hist_col].tail(5).tolist()
    hist_expanding = all(abs(recent_hist[i]) <= abs(recent_hist[i + 1]) for i in range(len(recent_hist) - 1))

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "macd_line": current_macd,
        "signal_line": current_signal,
        "histogram": current_hist,
        "macd_above_signal": current_macd > current_signal,
        "histogram_expanding": hist_expanding,
        "recent_crossovers": signals,
        "signal": "BULLISH" if current_macd > current_signal and current_hist > 0 else
                  "BEARISH" if current_macd < current_signal and current_hist < 0 else "NEUTRAL",
    }


@tool
def calculate_support_resistance(ticker: str, exchange: str) -> dict:
    """Calculate key support and resistance levels using pivot points and local extrema."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    high = float(df["High"].max())
    low = float(df["Low"].min())
    close = float(df["Close"].iloc[-1])
    current = close

    # Classic Pivot Points
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)

    # Local min/max (20-day window)
    window = 20
    df["local_max"] = df["High"].rolling(window=window, center=True).max()
    df["local_min"] = df["Low"].rolling(window=window, center=True).min()

    resistance_levels = sorted(set(round(float(v), 2) for v in df["local_max"].dropna().unique() if v > current))[:5]
    support_levels = sorted(set(round(float(v), 2) for v in df["local_min"].dropna().unique() if v < current), reverse=True)[:5]

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "current_price": round(current, 2),
        "pivot_points": {
            "pivot": round(pivot, 2),
            "resistance_1": round(r1, 2),
            "resistance_2": round(r2, 2),
            "resistance_3": round(r3, 2),
            "support_1": round(s1, 2),
            "support_2": round(s2, 2),
            "support_3": round(s3, 2),
        },
        "key_resistance_levels": resistance_levels[:3],
        "key_support_levels": support_levels[:3],
    }


@tool
def estimate_next_high_low(ticker: str, exchange: str) -> dict:
    """Estimate expected next high and low using ATR and Bollinger Bands.
    DISCLAIMER: These are statistical estimates, not guaranteed predictions."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    current = float(df["Close"].iloc[-1])

    # ATR (14-period)
    atr_series = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    if atr_series is None or atr_series.dropna().empty:
        return {"error": "ATR calculation failed"}
    atr = float(atr_series.iloc[-1])

    # Bollinger Bands (20-period, 2 std)
    bb = ta.bbands(df["Close"], length=20, std=2)
    if bb is None or bb.empty:
        return {"error": "Bollinger Bands calculation failed"}

    bb_upper_col = [c for c in bb.columns if "BBU" in c][0]
    bb_lower_col = [c for c in bb.columns if "BBL" in c][0]
    bb_mid_col = [c for c in bb.columns if "BBM" in c][0]

    bb_upper = float(bb[bb_upper_col].iloc[-1])
    bb_lower = float(bb[bb_lower_col].iloc[-1])
    bb_mid = float(bb[bb_mid_col].iloc[-1])
    bb_width = round(((bb_upper - bb_lower) / bb_mid) * 100, 2)

    # Short-term estimates (1-2 weeks): price +/- 2*ATR
    short_high = round(current + 2 * atr, 2)
    short_low = round(current - 2 * atr, 2)

    # Medium-term estimates (1 month): Bollinger Band boundaries
    medium_high = round(bb_upper, 2)
    medium_low = round(bb_lower, 2)

    # Confidence based on volatility
    if bb_width < 10:
        confidence = "HIGH (low volatility, tighter range)"
    elif bb_width < 20:
        confidence = "MEDIUM"
    else:
        confidence = "LOW (high volatility, wider range)"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "current_price": round(current, 2),
        "atr_14": round(atr, 2),
        "short_term_estimate": {
            "timeframe": "1-2 weeks",
            "expected_high": short_high,
            "expected_low": short_low,
            "method": "ATR-based (price +/- 2x ATR)",
        },
        "medium_term_estimate": {
            "timeframe": "1 month",
            "expected_high": medium_high,
            "expected_low": medium_low,
            "method": "Bollinger Bands (20, 2)",
        },
        "bollinger_band_width_pct": bb_width,
        "confidence": confidence,
        "disclaimer": "Statistical estimates based on historical volatility. Not investment advice.",
    }


@tool
def get_technical_summary(ticker: str, exchange: str) -> dict:
    """Get comprehensive technical indicator dashboard: RSI, Stochastic, ADX, Bollinger Bands."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    current = float(df["Close"].iloc[-1])
    result = {"ticker": get_display_ticker(ticker), "exchange": exchange, "current_price": round(current, 2)}

    # RSI (14)
    rsi = ta.rsi(df["Close"], length=14)
    if rsi is not None and not rsi.dropna().empty:
        rsi_val = round(float(rsi.iloc[-1]), 2)
        result["rsi_14"] = rsi_val
        result["rsi_signal"] = "OVERBOUGHT" if rsi_val > 70 else "OVERSOLD" if rsi_val < 30 else "NEUTRAL"

    # Stochastic (14, 3, 3)
    stoch = ta.stoch(df["High"], df["Low"], df["Close"], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        k_col = [c for c in stoch.columns if "STOCHk" in c]
        d_col = [c for c in stoch.columns if "STOCHd" in c]
        if k_col and d_col:
            k_val = round(float(stoch[k_col[0]].iloc[-1]), 2)
            d_val = round(float(stoch[d_col[0]].iloc[-1]), 2)
            result["stochastic_k"] = k_val
            result["stochastic_d"] = d_val
            result["stochastic_signal"] = "OVERBOUGHT" if k_val > 80 else "OVERSOLD" if k_val < 20 else "NEUTRAL"

    # ADX (14)
    adx = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    if adx is not None and not adx.empty:
        adx_col = [c for c in adx.columns if "ADX_14" == c]
        if adx_col:
            adx_val = round(float(adx[adx_col[0]].iloc[-1]), 2)
            result["adx_14"] = adx_val
            result["trend_strength"] = "STRONG" if adx_val > 25 else "WEAK"

    # Volume analysis
    avg_vol = int(df["Volume"].tail(20).mean())
    last_vol = int(df["Volume"].iloc[-1])
    result["avg_volume_20d"] = avg_vol
    result["last_volume"] = last_vol
    result["volume_signal"] = "HIGH" if last_vol > 1.5 * avg_vol else "LOW" if last_vol < 0.5 * avg_vol else "NORMAL"

    return result


@tool
def calculate_ema_crossovers(ticker: str, exchange: str) -> dict:
    """Calculate EMA (9, 21, 50) crossover signals for short and medium-term momentum."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    df["EMA_9"] = ta.ema(df["Close"], length=9)
    df["EMA_21"] = ta.ema(df["Close"], length=21)
    df["EMA_50"] = ta.ema(df["Close"], length=50)
    df = df.dropna(subset=["EMA_9", "EMA_21", "EMA_50"])

    if df.empty:
        return {"error": "Insufficient data for EMA calculation"}

    ema_9 = round(float(df["EMA_9"].iloc[-1]), 2)
    ema_21 = round(float(df["EMA_21"].iloc[-1]), 2)
    ema_50 = round(float(df["EMA_50"].iloc[-1]), 2)

    # Alignment
    if ema_9 > ema_21 > ema_50:
        alignment = "BULLISH"
    elif ema_9 < ema_21 < ema_50:
        alignment = "BEARISH"
    else:
        alignment = "MIXED"

    # Short-term crossover (9/21)
    df["short_above"] = df["EMA_9"] > df["EMA_21"]
    df["short_cross"] = df["short_above"].ne(df["short_above"].shift())
    short_crosses = df[df["short_cross"]].tail(5)
    short_term_signal = "BULLISH" if ema_9 > ema_21 else "BEARISH"

    # Medium-term crossover (21/50)
    df["med_above"] = df["EMA_21"] > df["EMA_50"]
    df["med_cross"] = df["med_above"].ne(df["med_above"].shift())
    med_crosses = df[df["med_cross"]].tail(5)
    medium_term_signal = "BULLISH" if ema_21 > ema_50 else "BEARISH"

    short_crossovers = [
        {"date": d.strftime("%Y-%m-%d"), "type": "BULLISH" if r["short_above"] else "BEARISH"}
        for d, r in short_crosses.iterrows()
    ]
    medium_crossovers = [
        {"date": d.strftime("%Y-%m-%d"), "type": "BULLISH" if r["med_above"] else "BEARISH"}
        for d, r in med_crosses.iterrows()
    ]

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "ema_9": ema_9,
        "ema_21": ema_21,
        "ema_50": ema_50,
        "alignment": alignment,
        "short_term_signal": short_term_signal,
        "medium_term_signal": medium_term_signal,
        "short_term_crossovers": short_crossovers,
        "medium_term_crossovers": medium_crossovers,
    }


@tool
def detect_golden_death_cross(ticker: str, exchange: str) -> dict:
    """Detect Golden Cross (SMA50 crosses above SMA200) or Death Cross (below).
    These are major institutional trend reversal signals."""
    df = _fetch_price_data(ticker, exchange, period="2y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    df["SMA_50"] = ta.sma(df["Close"], length=50)
    df["SMA_200"] = ta.sma(df["Close"], length=200)
    df = df.dropna(subset=["SMA_50", "SMA_200"])

    if df.empty:
        return {"error": "Insufficient data for Golden/Death Cross detection"}

    sma_50 = round(float(df["SMA_50"].iloc[-1]), 2)
    sma_200 = round(float(df["SMA_200"].iloc[-1]), 2)
    distance_pct = round(((sma_50 - sma_200) / sma_200) * 100, 2)

    # Detect crossovers
    df["fifty_above"] = df["SMA_50"] > df["SMA_200"]
    df["cross"] = df["fifty_above"].ne(df["fifty_above"].shift())
    crosses = df[df["cross"]].tail(5)

    if sma_50 > sma_200:
        current_state = "GOLDEN_CROSS"
    elif sma_50 < sma_200:
        current_state = "DEATH_CROSS"
    else:
        current_state = "NEITHER"

    last_crossover = None
    if not crosses.empty:
        last_row = crosses.iloc[-1]
        last_crossover = {
            "date": crosses.index[-1].strftime("%Y-%m-%d"),
            "type": "GOLDEN_CROSS" if last_row["fifty_above"] else "DEATH_CROSS",
        }

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "distance_percent": distance_pct,
        "current_state": current_state,
        "last_crossover": last_crossover,
        "signal": "BULLISH" if current_state == "GOLDEN_CROSS" else
                  "BEARISH" if current_state == "DEATH_CROSS" else "NEUTRAL",
    }


@tool
def calculate_fibonacci_levels(ticker: str, exchange: str) -> dict:
    """Calculate Fibonacci retracement levels from 6-month high/low swing.
    Returns key levels (23.6%, 38.2%, 50%, 61.8%, 78.6%) and nearest support/resistance."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    swing_high = float(df["High"].max())
    swing_low = float(df["Low"].min())
    current = float(df["Close"].iloc[-1])
    diff = swing_high - swing_low

    ratios = {"23.6%": 0.236, "38.2%": 0.382, "50.0%": 0.500, "61.8%": 0.618, "78.6%": 0.786}
    levels = {pct: round(swing_high - diff * ratio, 2) for pct, ratio in ratios.items()}

    nearest_support = None
    nearest_resistance = None
    for pct, level in sorted(levels.items(), key=lambda x: x[1]):
        if level < current and (nearest_support is None or level > levels[nearest_support]):
            nearest_support = pct
        if level > current and (nearest_resistance is None or level < levels[nearest_resistance]):
            nearest_resistance = pct

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "current_price": round(current, 2),
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "levels": levels,
        "nearest_support": {"level": nearest_support, "price": levels.get(nearest_support)} if nearest_support else None,
        "nearest_resistance": {"level": nearest_resistance, "price": levels.get(nearest_resistance)} if nearest_resistance else None,
    }


@tool
def calculate_vwap(ticker: str, exchange: str) -> dict:
    """Calculate Volume-Weighted Average Price. VWAP is a key institutional reference price."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    cumulative_tp_vol = (typical_price * df["Volume"]).cumsum()
    cumulative_vol = df["Volume"].cumsum()
    df["VWAP"] = cumulative_tp_vol / cumulative_vol

    current = float(df["Close"].iloc[-1])
    vwap_val = round(float(df["VWAP"].iloc[-1]), 2)
    distance_pct = round(((current - vwap_val) / vwap_val) * 100, 2)

    vwap_recent = df["VWAP"].tail(20)
    vwap_trend = "RISING" if float(vwap_recent.iloc[-1]) > float(vwap_recent.iloc[0]) else "FALLING"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "current_price": round(current, 2),
        "vwap": vwap_val,
        "price_vs_vwap": "ABOVE" if current > vwap_val else "BELOW",
        "distance_percent": distance_pct,
        "vwap_trend": vwap_trend,
    }


@tool
def calculate_obv(ticker: str, exchange: str) -> dict:
    """Calculate On-Balance Volume to detect accumulation/distribution via volume flow.
    Also detects price/OBV divergence (bullish or bearish)."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    obv_series = ta.obv(df["Close"], df["Volume"])
    if obv_series is None or obv_series.dropna().empty:
        return {"error": "OBV calculation failed"}

    df["OBV"] = obv_series
    current_obv = int(df["OBV"].iloc[-1])

    obv_20 = df["OBV"].tail(20)
    obv_trend = "RISING" if float(obv_20.iloc[-1]) > float(obv_20.iloc[0]) else "FALLING"

    price_20 = df["Close"].tail(20)
    price_trend = "RISING" if float(price_20.iloc[-1]) > float(price_20.iloc[0]) else "FALLING"

    if price_trend == "FALLING" and obv_trend == "RISING":
        divergence = "BULLISH_DIVERGENCE"
    elif price_trend == "RISING" and obv_trend == "FALLING":
        divergence = "BEARISH_DIVERGENCE"
    else:
        divergence = "NONE"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "obv": current_obv,
        "obv_trend": obv_trend,
        "price_trend": price_trend,
        "divergence": divergence,
        "signal": "BULLISH" if divergence == "BULLISH_DIVERGENCE" or (obv_trend == "RISING" and price_trend == "RISING") else
                  "BEARISH" if divergence == "BEARISH_DIVERGENCE" or (obv_trend == "FALLING" and price_trend == "FALLING") else "NEUTRAL",
    }


@tool
def calculate_ichimoku(ticker: str, exchange: str) -> dict:
    """Calculate Ichimoku Cloud components: Tenkan-sen, Kijun-sen, Senkou Span A/B.
    Widely used in Asian markets for trend, support/resistance, and momentum."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    ichimoku = ta.ichimoku(df["High"], df["Low"], df["Close"])
    if ichimoku is None or (isinstance(ichimoku, tuple) and ichimoku[0].empty):
        return {"error": "Ichimoku calculation failed"}

    ichi_df = ichimoku[0] if isinstance(ichimoku, tuple) else ichimoku
    df = pd.concat([df, ichi_df], axis=1)
    df = df.dropna()

    if df.empty:
        return {"error": "Insufficient data for Ichimoku"}

    tenkan_col = [c for c in df.columns if "ITS" in str(c)]
    kijun_col = [c for c in df.columns if "IKS" in str(c)]
    span_a_col = [c for c in df.columns if "ISA" in str(c)]
    span_b_col = [c for c in df.columns if "ISB" in str(c)]

    current = float(df["Close"].iloc[-1])
    tenkan = round(float(df[tenkan_col[0]].iloc[-1]), 2) if tenkan_col else None
    kijun = round(float(df[kijun_col[0]].iloc[-1]), 2) if kijun_col else None
    span_a = round(float(df[span_a_col[0]].iloc[-1]), 2) if span_a_col else None
    span_b = round(float(df[span_b_col[0]].iloc[-1]), 2) if span_b_col else None

    cloud_color = "GREEN" if span_a and span_b and span_a > span_b else "RED"

    cloud_top = max(span_a or 0, span_b or 0)
    cloud_bottom = min(span_a or 0, span_b or 0)
    if current > cloud_top:
        price_vs_cloud = "ABOVE"
    elif current < cloud_bottom:
        price_vs_cloud = "BELOW"
    else:
        price_vs_cloud = "INSIDE"

    tk_signal = "BULLISH" if tenkan and kijun and tenkan > kijun else "BEARISH"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "current_price": round(current, 2),
        "tenkan_sen": tenkan,
        "kijun_sen": kijun,
        "senkou_span_a": span_a,
        "senkou_span_b": span_b,
        "cloud_color": cloud_color,
        "price_vs_cloud": price_vs_cloud,
        "tk_cross_signal": tk_signal,
        "signal": "BULLISH" if price_vs_cloud == "ABOVE" and cloud_color == "GREEN" else
                  "BEARISH" if price_vs_cloud == "BELOW" and cloud_color == "RED" else "NEUTRAL",
    }


@tool
def calculate_williams_r(ticker: str, exchange: str) -> dict:
    """Calculate Williams %R (14-period) overbought/oversold indicator.
    Range: 0 to -100. Overbought > -20, Oversold < -80."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    willr = ta.willr(df["High"], df["Low"], df["Close"], length=14)
    if willr is None or willr.dropna().empty:
        return {"error": "Williams %R calculation failed"}

    value = round(float(willr.iloc[-1]), 2)

    if value > -20:
        signal = "OVERBOUGHT"
    elif value < -80:
        signal = "OVERSOLD"
    else:
        signal = "NEUTRAL"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "williams_r": value,
        "signal": signal,
    }


@tool
def calculate_adx_directional(ticker: str, exchange: str) -> dict:
    """Calculate ADX with +DI and -DI for both trend strength AND direction.
    ADX > 25 = strong trend. +DI > -DI = bullish direction."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    if adx_df is None or adx_df.empty:
        return {"error": "ADX calculation failed"}

    adx_col = [c for c in adx_df.columns if c == "ADX_14"]
    dmp_col = [c for c in adx_df.columns if "DMP" in c]
    dmn_col = [c for c in adx_df.columns if "DMN" in c]

    if not adx_col or not dmp_col or not dmn_col:
        return {"error": "ADX directional columns not found"}

    adx_val = round(float(adx_df[adx_col[0]].iloc[-1]), 2)
    plus_di = round(float(adx_df[dmp_col[0]].iloc[-1]), 2)
    minus_di = round(float(adx_df[dmn_col[0]].iloc[-1]), 2)

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "adx": adx_val,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "trend_strength": "STRONG" if adx_val > 25 else "WEAK",
        "trend_direction": "BULLISH" if plus_di > minus_di else "BEARISH",
        "signal": "STRONG_BULLISH" if adx_val > 25 and plus_di > minus_di else
                  "STRONG_BEARISH" if adx_val > 25 and plus_di < minus_di else
                  "WEAK_BULLISH" if plus_di > minus_di else "WEAK_BEARISH",
    }


@tool
def calculate_trend_strength(ticker: str, exchange: str) -> dict:
    """Calculate composite trend strength score (0-100) combining ADX, EMA alignment, and OBV."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    score = 0

    # ADX strength component (0-40 points)
    adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    if adx_df is not None and not adx_df.empty:
        adx_col = [c for c in adx_df.columns if c == "ADX_14"]
        if adx_col:
            adx_val = float(adx_df[adx_col[0]].iloc[-1])
            score += min(40, adx_val * 1.6)

    # EMA alignment component (0-30 points)
    ema_9 = ta.ema(df["Close"], length=9)
    ema_21 = ta.ema(df["Close"], length=21)
    ema_50 = ta.ema(df["Close"], length=50)
    if ema_9 is not None and ema_21 is not None and ema_50 is not None:
        e9 = float(ema_9.iloc[-1])
        e21 = float(ema_21.iloc[-1])
        e50 = float(ema_50.iloc[-1])
        if e9 > e21 > e50 or e9 < e21 < e50:
            score += 30
        elif (e9 > e21 and e21 < e50) or (e9 < e21 and e21 > e50):
            score += 15

    # Volume confirmation component (0-30 points)
    obv = ta.obv(df["Close"], df["Volume"])
    if obv is not None and not obv.dropna().empty:
        obv_20 = obv.tail(20)
        price_20 = df["Close"].tail(20)
        obv_rising = float(obv_20.iloc[-1]) > float(obv_20.iloc[0])
        price_rising = float(price_20.iloc[-1]) > float(price_20.iloc[0])
        if obv_rising == price_rising:
            score += 30
        else:
            score += 10

    score = min(100, round(score))

    current = float(df["Close"].iloc[-1])
    sma_50 = ta.sma(df["Close"], length=50)
    if sma_50 is not None and not sma_50.dropna().empty:
        sma_val = float(sma_50.iloc[-1])
        if current > sma_val * 1.02:
            direction = "UP"
        elif current < sma_val * 0.98:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"
    else:
        direction = "SIDEWAYS"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "trend_score": score,
        "trend_direction": direction,
        "confidence": "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW",
    }


@tool
def detect_chart_patterns(ticker: str, exchange: str) -> dict:
    """Detect basic chart patterns: double top/bottom, ascending/descending triangles.
    Uses peak/trough detection on 6-month data."""
    df = _fetch_price_data(ticker, exchange, period="6mo")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    patterns = []
    highs = df["High"].values
    lows = df["Low"].values

    window = 10
    peaks = []
    troughs = []
    for i in range(window, len(highs) - window):
        if highs[i] == max(highs[i - window:i + window + 1]):
            peaks.append((i, float(highs[i])))
        if lows[i] == min(lows[i - window:i + window + 1]):
            troughs.append((i, float(lows[i])))

    tolerance = 0.03

    # Double Top
    for i in range(len(peaks) - 1):
        idx1, p1 = peaks[i]
        idx2, p2 = peaks[i + 1]
        if abs(p1 - p2) / p1 < tolerance and idx2 - idx1 > 10:
            patterns.append({
                "pattern": "DOUBLE_TOP",
                "date_range": f"{df.index[idx1].strftime('%Y-%m-%d')} to {df.index[idx2].strftime('%Y-%m-%d')}",
                "level": round((p1 + p2) / 2, 2),
                "signal": "BEARISH",
            })

    # Double Bottom
    for i in range(len(troughs) - 1):
        idx1, t1 = troughs[i]
        idx2, t2 = troughs[i + 1]
        if abs(t1 - t2) / t1 < tolerance and idx2 - idx1 > 10:
            patterns.append({
                "pattern": "DOUBLE_BOTTOM",
                "date_range": f"{df.index[idx1].strftime('%Y-%m-%d')} to {df.index[idx2].strftime('%Y-%m-%d')}",
                "level": round((t1 + t2) / 2, 2),
                "signal": "BULLISH",
            })

    # Ascending/Descending Triangle
    if len(peaks) >= 2 and len(troughs) >= 2:
        recent_peaks = peaks[-3:]
        recent_troughs = troughs[-3:]
        peak_levels = [p[1] for p in recent_peaks]
        trough_levels = [t[1] for t in recent_troughs]

        flat_resistance = max(peak_levels) - min(peak_levels) < max(peak_levels) * tolerance
        rising_support = all(trough_levels[i] < trough_levels[i + 1] for i in range(len(trough_levels) - 1))

        if flat_resistance and rising_support and len(recent_troughs) >= 2:
            patterns.append({
                "pattern": "ASCENDING_TRIANGLE",
                "resistance": round(sum(peak_levels) / len(peak_levels), 2),
                "signal": "BULLISH",
            })

        flat_support = max(trough_levels) - min(trough_levels) < max(trough_levels) * tolerance
        falling_resistance = all(peak_levels[i] > peak_levels[i + 1] for i in range(len(peak_levels) - 1))

        if flat_support and falling_resistance and len(recent_peaks) >= 2:
            patterns.append({
                "pattern": "DESCENDING_TRIANGLE",
                "support": round(sum(trough_levels) / len(trough_levels), 2),
                "signal": "BEARISH",
            })

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "patterns": patterns,
        "total_patterns_found": len(patterns),
    }


@tool
def calculate_risk_metrics(ticker: str, exchange: str) -> dict:
    """Calculate risk metrics: Sharpe ratio, max drawdown, beta, VaR, and volatility."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    returns = df["Close"].pct_change().dropna()
    if len(returns) < 20:
        return {"error": "Insufficient data for risk calculation"}

    volatility = round(float(returns.std() * np.sqrt(252) * 100), 2)

    annual_return = float((1 + returns.mean()) ** 252 - 1)
    risk_free = settings.risk_free_rate
    sharpe = round((annual_return - risk_free) / (returns.std() * np.sqrt(252)), 2) if returns.std() > 0 else 0.0

    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = round(float(drawdown.min() * 100), 2)
    max_dd_end = drawdown.idxmin()
    max_dd_start = cumulative[:max_dd_end].idxmax() if max_dd_end is not None else None

    # Beta vs market index
    ex = ExchangeEnum(exchange.upper())
    index_map = {
        ExchangeEnum.NSE: "^NSEI",
        ExchangeEnum.BSE: "^BSESN",
        ExchangeEnum.NASDAQ: "^IXIC",
    }
    beta = 1.0
    try:
        idx_df = yf.download(index_map[ex], period="1y", progress=False)
        if hasattr(idx_df.columns, 'levels') and len(idx_df.columns.levels) > 1:
            idx_df.columns = idx_df.columns.get_level_values(0)
        idx_returns = idx_df["Close"].pct_change().dropna()
        aligned = pd.concat([returns, idx_returns], axis=1, join="inner")
        aligned.columns = ["stock", "market"]
        if len(aligned) > 20:
            cov = aligned["stock"].cov(aligned["market"])
            var_market = aligned["market"].var()
            beta = round(cov / var_market, 2) if var_market > 0 else 1.0
    except Exception:
        pass

    confidence = settings.var_confidence
    var_95 = round(float(np.percentile(returns, (1 - confidence) * 100) * 100), 2)

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": max_dd,
        "max_drawdown_period": {
            "start": max_dd_start.strftime("%Y-%m-%d") if max_dd_start is not None else None,
            "end": max_dd_end.strftime("%Y-%m-%d") if max_dd_end is not None else None,
        },
        "beta": beta,
        "var_95": var_95,
        "volatility": volatility,
    }


@tool
def calculate_relative_strength(ticker: str, exchange: str) -> dict:
    """Compare stock performance against its market index over multiple timeframes."""
    df = _fetch_price_data(ticker, exchange, period="1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}

    ex = ExchangeEnum(exchange.upper())
    index_map = {
        ExchangeEnum.NSE: "^NSEI",
        ExchangeEnum.BSE: "^BSESN",
        ExchangeEnum.NASDAQ: "^IXIC",
    }

    try:
        idx_df = yf.download(index_map[ex], period="1y", progress=False)
        if hasattr(idx_df.columns, 'levels') and len(idx_df.columns.levels) > 1:
            idx_df.columns = idx_df.columns.get_level_values(0)
    except Exception:
        return {"error": "Could not fetch market index data"}

    if idx_df.empty:
        return {"error": "No market index data available"}

    performance = {}
    for label, days in [("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126)]:
        if len(df) > days and len(idx_df) > days:
            stock_ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-days]) - 1) * 100
            idx_ret = (float(idx_df["Close"].iloc[-1]) / float(idx_df["Close"].iloc[-days]) - 1) * 100
            performance[label] = {
                "stock": round(stock_ret, 2),
                "market": round(idx_ret, 2),
                "excess": round(stock_ret - idx_ret, 2),
            }

    excess_3m = performance.get("3m", {}).get("excess", 0)
    if excess_3m > 5:
        classification = "OUTPERFORMING"
    elif excess_3m < -5:
        classification = "UNDERPERFORMING"
    else:
        classification = "IN_LINE"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "relative_performance": performance,
        "classification": classification,
    }
