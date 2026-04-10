# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
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
    import yfinance as yf
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
    import yfinance as yf

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
    import yfinance as yf

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
