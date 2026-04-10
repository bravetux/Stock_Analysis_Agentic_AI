# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from enum import Enum


class ExchangeEnum(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NASDAQ = "NASDAQ"


def detect_exchange(ticker: str) -> ExchangeEnum:
    """
    Detect exchange from ticker format.
    Supports: NSE:RELIANCE, BSE:500325, NASDAQ:AAPL, RELIANCE.NS, 500325.BO,
    and plain tickers (heuristic: all-digit = BSE scrip code, else defaults to settings).
    """
    upper = ticker.strip().upper()

    # Explicit prefix
    if upper.startswith("NSE:"):
        return ExchangeEnum.NSE
    if upper.startswith("BSE:"):
        return ExchangeEnum.BSE
    if upper.startswith("NASDAQ:"):
        return ExchangeEnum.NASDAQ

    # yfinance suffix
    if upper.endswith(".NS"):
        return ExchangeEnum.NSE
    if upper.endswith(".BO"):
        return ExchangeEnum.BSE

    # BSE scrip codes are purely numeric
    clean = upper.split(":")[-1]
    if clean.isdigit():
        return ExchangeEnum.BSE

    # Default from settings
    from src.config.settings import settings
    try:
        return ExchangeEnum(settings.default_exchange.upper())
    except ValueError:
        return ExchangeEnum.NSE


def strip_prefix(ticker: str) -> str:
    """Remove exchange prefix like NSE:, BSE:, NASDAQ: from ticker."""
    for prefix in ("NSE:", "BSE:", "NASDAQ:"):
        if ticker.upper().startswith(prefix):
            return ticker[len(prefix):]
    return ticker


def normalize_ticker(ticker: str, exchange: ExchangeEnum) -> str:
    """Convert ticker to yfinance-compatible format."""
    clean = strip_prefix(ticker).strip()
    # Remove existing suffixes
    for suffix in (".NS", ".BO"):
        if clean.upper().endswith(suffix):
            clean = clean[: -len(suffix)]

    if exchange == ExchangeEnum.NSE:
        return f"{clean}.NS"
    elif exchange == ExchangeEnum.BSE:
        return f"{clean}.BO"
    else:
        return clean


def get_location(exchange: ExchangeEnum) -> str:
    """Get geographic location for exchange-specific news searches."""
    if exchange in (ExchangeEnum.NSE, ExchangeEnum.BSE):
        return "India"
    return "United States"


def get_currency(exchange: ExchangeEnum) -> str:
    if exchange in (ExchangeEnum.NSE, ExchangeEnum.BSE):
        return "INR"
    return "USD"


def get_display_ticker(ticker: str) -> str:
    """Get a clean display name from any ticker format."""
    clean = strip_prefix(ticker).strip()
    for suffix in (".NS", ".BO"):
        if clean.upper().endswith(suffix):
            clean = clean[: -len(suffix)]
    return clean
