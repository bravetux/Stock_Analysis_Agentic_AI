# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
import yfinance as yf
import pandas as pd
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
