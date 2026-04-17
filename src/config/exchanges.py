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

from enum import Enum
from urllib.parse import quote


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
    """Convert ticker to yfinance-compatible format.

    Runs ``resolve_symbol`` first so free-form inputs like ``"natco"``,
    ``"infosys"`` or ``"Natco Pharma Limited"`` map to the canonical NSE
    symbol (``NATCOPHARM``, ``INFY``) instead of being shipped to yfinance
    as a bogus ``NATCO.NS`` that 404s.
    """
    clean = strip_prefix(ticker).strip()
    # Remove existing suffixes
    for suffix in (".NS", ".BO"):
        if clean.upper().endswith(suffix):
            clean = clean[: -len(suffix)]

    # Resolve free-form names to canonical symbols (alias/catalog/yf.Search).
    # Never raises; falls back to `clean` if no match is found.
    from src.config.symbol_resolver import resolve_symbol
    try:
        clean = resolve_symbol(clean, exchange.value)
    except Exception:
        pass

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


def url_encode_ticker(ticker: str) -> str:
    """URL-encode a ticker for safe use in URLs. Handles special chars like & in ARE&M."""
    return quote(get_display_ticker(ticker), safe="")
