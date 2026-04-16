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
from strands import tool
from src.config.exchanges import (
    ExchangeEnum, detect_exchange, normalize_ticker, strip_prefix, get_display_ticker,
)
from src.config.settings import settings

logger = logging.getLogger(__name__)


@tool
def detect_exchange_for_ticker(ticker: str) -> dict:
    """Detect which stock exchange a ticker belongs to (NSE, BSE, or NASDAQ).
    Returns exchange name, normalized yfinance ticker, and location."""
    exchange = detect_exchange(ticker)
    yf_ticker = normalize_ticker(ticker, exchange)
    display = get_display_ticker(ticker)
    return {
        "ticker": display,
        "exchange": exchange.value,
        "yfinance_ticker": yf_ticker,
        "location": "India" if exchange in (ExchangeEnum.NSE, ExchangeEnum.BSE) else "United States",
    }


@tool
def get_stock_quote(ticker: str, exchange: str) -> dict:
    """Get real-time stock quote. Exchange must be NSE, BSE, or NASDAQ.
    Returns current price, open, high, low, volume, 52-week range."""
    ex = ExchangeEnum(exchange.upper())
    display = get_display_ticker(ticker)

    if ex == ExchangeEnum.NSE:
        try:
            from nsetools import Nse
            nse = Nse()
            quote = nse.get_quote(display)
            if quote:
                return {
                    "ticker": display,
                    "exchange": "NSE",
                    "last_price": quote.get("lastPrice"),
                    "open": quote.get("open"),
                    "high": quote.get("dayHigh"),
                    "low": quote.get("dayLow"),
                    "close": quote.get("previousClose"),
                    "volume": quote.get("totalTradedVolume"),
                    "52w_high": quote.get("high52"),
                    "52w_low": quote.get("low52"),
                    "source": "nsetools",
                }
        except Exception as e:
            logger.warning("nsetools failed for %s: %s, falling back to yfinance", display, e)

    if ex == ExchangeEnum.BSE:
        try:
            from bsedata.bse import BSE
            bse = BSE()
            scrip_code = display
            quote = bse.getQuote(scrip_code)
            if quote:
                return {
                    "ticker": scrip_code,
                    "exchange": "BSE",
                    "last_price": quote.get("currentValue"),
                    "open": quote.get("open"),
                    "high": quote.get("dayHigh"),
                    "low": quote.get("dayLow"),
                    "close": quote.get("previousClose"),
                    "volume": quote.get("totalTradedQuantity"),
                    "52w_high": quote.get("52weekHigh"),
                    "52w_low": quote.get("52weekLow"),
                    "source": "bsedata",
                }
        except Exception as e:
            logger.warning("bsedata failed for %s: %s, falling back to yfinance", display, e)

    # Fallback / NASDAQ: use yfinance
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)
    info = stock.info
    return {
        "ticker": display,
        "exchange": ex.value,
        "last_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "open": info.get("open") or info.get("regularMarketOpen"),
        "high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
        "low": info.get("dayLow") or info.get("regularMarketDayLow"),
        "close": info.get("previousClose") or info.get("regularMarketPreviousClose"),
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "market_cap": info.get("marketCap"),
        "company_name": info.get("longName") or info.get("shortName"),
        "source": "yfinance",
    }


@tool
def get_historical_data(ticker: str, exchange: str, days: int = 365) -> dict:
    """Fetch historical OHLCV data for a stock. Returns date-indexed price data."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)

    period_map = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y", 730: "2y"}
    period = "1y"
    for threshold, p in sorted(period_map.items()):
        if days <= threshold:
            period = p
            break

    df = yf.download(yf_ticker, period=period, progress=False)
    if df.empty:
        return {"error": f"No data found for {yf_ticker}", "ticker": get_display_ticker(ticker)}

    # Flatten multi-level columns if present
    if hasattr(df.columns, 'levels') and len(df.columns.levels) > 1:
        df.columns = df.columns.get_level_values(0)

    records = []
    for date, row in df.iterrows():
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": ex.value,
        "period": period,
        "data_points": len(records),
        "data": records,
    }


@tool
def get_market_overview(exchange: str) -> dict:
    """Get market index overview for an exchange (NIFTY50, SENSEX, or NASDAQ Composite)."""
    ex = ExchangeEnum(exchange.upper())

    index_map = {
        ExchangeEnum.NSE: {"symbol": "^NSEI", "name": "NIFTY 50"},
        ExchangeEnum.BSE: {"symbol": "^BSESN", "name": "SENSEX"},
        ExchangeEnum.NASDAQ: {"symbol": "^IXIC", "name": "NASDAQ Composite"},
    }

    idx = index_map[ex]
    stock = yf.Ticker(idx["symbol"])
    info = stock.info

    return {
        "index_name": idx["name"],
        "exchange": ex.value,
        "value": info.get("regularMarketPrice"),
        "change": info.get("regularMarketChange"),
        "change_percent": info.get("regularMarketChangePercent"),
        "day_high": info.get("regularMarketDayHigh"),
        "day_low": info.get("regularMarketDayLow"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
    }


SECTOR_ETFS = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


@tool
def get_options_chain(ticker: str, exchange: str) -> dict:
    """Get options chain summary: put/call ratio, max pain, implied volatility.
    Not all stocks have listed options — returns graceful message if unavailable."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)

    if not stock.options:
        return {"ticker": get_display_ticker(ticker), "message": "No options data available for this stock"}

    nearest_expiry = stock.options[0]
    chain = stock.option_chain(nearest_expiry)

    calls = chain.calls
    puts = chain.puts
    total_call_oi = int(calls["openInterest"].sum()) if "openInterest" in calls.columns else 0
    total_put_oi = int(puts["openInterest"].sum()) if "openInterest" in puts.columns else 0
    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 0

    # Max pain: strike price where option holders lose the most
    all_strikes = sorted(set(calls["strike"].tolist() + puts["strike"].tolist()))
    max_pain_strike = None
    min_total_value = float("inf")
    for strike in all_strikes:
        call_itm = calls[calls["strike"] < strike]
        call_loss = (call_itm["openInterest"] * (strike - call_itm["strike"])).sum() if not call_itm.empty else 0
        put_itm = puts[puts["strike"] > strike]
        put_loss = (put_itm["openInterest"] * (put_itm["strike"] - strike)).sum() if not put_itm.empty else 0
        total = call_loss + put_loss
        if total < min_total_value:
            min_total_value = total
            max_pain_strike = strike

    # Average implied volatility
    avg_iv_calls = round(float(calls["impliedVolatility"].mean()) * 100, 2) if "impliedVolatility" in calls.columns else None
    avg_iv_puts = round(float(puts["impliedVolatility"].mean()) * 100, 2) if "impliedVolatility" in puts.columns else None
    avg_iv = round((avg_iv_calls + avg_iv_puts) / 2, 2) if avg_iv_calls and avg_iv_puts else None

    # Top OI strikes
    top_call_oi = calls.nlargest(5, "openInterest")[["strike", "openInterest"]].to_dict("records") if "openInterest" in calls.columns else []
    top_put_oi = puts.nlargest(5, "openInterest")[["strike", "openInterest"]].to_dict("records") if "openInterest" in puts.columns else []

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "expiry": nearest_expiry,
        "put_call_ratio": pcr,
        "max_pain": max_pain_strike,
        "avg_implied_volatility": avg_iv,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "top_call_strikes": top_call_oi,
        "top_put_strikes": top_put_oi,
        "signal": "BEARISH" if pcr > 1.5 else "BULLISH" if pcr < 0.7 else "NEUTRAL",
    }


@tool
def get_sector_performance(ticker: str, exchange: str) -> dict:
    """Compare stock performance vs its sector ETF for relative strength analysis."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)
    sector = stock.info.get("sector", "")

    if not sector:
        return {"ticker": get_display_ticker(ticker), "error": "Sector information not available"}

    sector_etf = SECTOR_ETFS.get(sector)
    if not sector_etf:
        return {"ticker": get_display_ticker(ticker), "sector": sector, "error": f"No ETF mapping for sector '{sector}'"}

    stock_df = yf.download(yf_ticker, period="1y", progress=False)
    etf_df = yf.download(sector_etf, period="1y", progress=False)

    for df_item in [stock_df, etf_df]:
        if hasattr(df_item.columns, 'levels') and len(df_item.columns.levels) > 1:
            df_item.columns = df_item.columns.get_level_values(0)

    if stock_df.empty or etf_df.empty:
        return {"ticker": get_display_ticker(ticker), "error": "Insufficient data for comparison"}

    performance = {}
    for label, days in [("1w", 5), ("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252)]:
        if len(stock_df) > days and len(etf_df) > days:
            stock_ret = (float(stock_df["Close"].iloc[-1]) / float(stock_df["Close"].iloc[-days]) - 1) * 100
            etf_ret = (float(etf_df["Close"].iloc[-1]) / float(etf_df["Close"].iloc[-days]) - 1) * 100
            performance[label] = {
                "stock": round(stock_ret, 2),
                "sector": round(etf_ret, 2),
                "excess": round(stock_ret - etf_ret, 2),
            }

    excess_3m = performance.get("3m", {}).get("excess", 0)

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "sector": sector,
        "sector_etf": sector_etf,
        "performance": performance,
        "relative_strength": "OUTPERFORMING" if excess_3m > 5 else "UNDERPERFORMING" if excess_3m < -5 else "IN_LINE",
    }
