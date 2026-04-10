# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from src.config.exchanges import (
    ExchangeEnum,
    detect_exchange,
    normalize_ticker,
    strip_prefix,
    get_display_ticker,
    get_location,
    get_currency,
)


class TestDetectExchange:
    def test_nse_prefix(self):
        assert detect_exchange("NSE:RELIANCE") == ExchangeEnum.NSE

    def test_bse_prefix(self):
        assert detect_exchange("BSE:500325") == ExchangeEnum.BSE

    def test_nasdaq_prefix(self):
        assert detect_exchange("NASDAQ:AAPL") == ExchangeEnum.NASDAQ

    def test_ns_suffix(self):
        assert detect_exchange("RELIANCE.NS") == ExchangeEnum.NSE

    def test_bo_suffix(self):
        assert detect_exchange("500325.BO") == ExchangeEnum.BSE

    def test_numeric_scrip(self):
        assert detect_exchange("500325") == ExchangeEnum.BSE

    def test_default_exchange(self):
        # Default is NSE from test env
        result = detect_exchange("RELIANCE")
        assert result == ExchangeEnum.NSE


class TestNormalizeTicker:
    def test_nse_normalization(self):
        assert normalize_ticker("RELIANCE", ExchangeEnum.NSE) == "RELIANCE.NS"

    def test_bse_normalization(self):
        assert normalize_ticker("500325", ExchangeEnum.BSE) == "500325.BO"

    def test_nasdaq_normalization(self):
        assert normalize_ticker("AAPL", ExchangeEnum.NASDAQ) == "AAPL"

    def test_strips_existing_suffix(self):
        assert normalize_ticker("RELIANCE.NS", ExchangeEnum.NSE) == "RELIANCE.NS"

    def test_prefix_stripped(self):
        assert normalize_ticker("NSE:TCS", ExchangeEnum.NSE) == "TCS.NS"


class TestStripPrefix:
    def test_nse_prefix(self):
        assert strip_prefix("NSE:RELIANCE") == "RELIANCE"

    def test_no_prefix(self):
        assert strip_prefix("AAPL") == "AAPL"


class TestGetDisplayTicker:
    def test_with_prefix(self):
        assert get_display_ticker("NSE:RELIANCE") == "RELIANCE"

    def test_with_suffix(self):
        assert get_display_ticker("RELIANCE.NS") == "RELIANCE"

    def test_plain(self):
        assert get_display_ticker("AAPL") == "AAPL"


class TestGetLocation:
    def test_nse_india(self):
        assert get_location(ExchangeEnum.NSE) == "India"

    def test_bse_india(self):
        assert get_location(ExchangeEnum.BSE) == "India"

    def test_nasdaq_us(self):
        assert get_location(ExchangeEnum.NASDAQ) == "United States"


class TestGetCurrency:
    def test_nse_inr(self):
        assert get_currency(ExchangeEnum.NSE) == "INR"

    def test_nasdaq_usd(self):
        assert get_currency(ExchangeEnum.NASDAQ) == "USD"
