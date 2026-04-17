# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Tests for src.config.symbol_resolver.

These tests MUST run without network. yfinance import is monkey-patched
out in the one test that exercises the network path, and the
``SYMBOL_RESOLVER_NETWORK`` env-flag disables it everywhere else.
"""

from __future__ import annotations

import os

import pytest

from src.config import symbol_resolver as sr
from src.config.exchanges import ExchangeEnum, normalize_ticker


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Disable the yf.Search fallback for deterministic tests."""
    monkeypatch.setenv("SYMBOL_RESOLVER_NETWORK", "0")
    # Clear lru_cache so test-env changes are honoured.
    sr._load_catalog.cache_clear()


class TestCatalogLoad:
    def test_catalog_contains_known_symbols(self):
        valid, name_map = sr._load_catalog()
        # stocks-names.txt ships with these — treat as contract.
        assert "NATCOPHARM" in valid
        assert "INFY" in valid
        assert "BAJAJ-AUTO" in valid
        assert "ARE&M" in valid
        assert "GVT&D" in valid

    def test_catalog_has_name_to_symbol_mapping(self):
        _, name_map = sr._load_catalog()
        # Company full name should map back to the NSE symbol.
        assert name_map[sr._norm_key("Natco Pharma Limited")] == "NATCOPHARM"
        assert name_map[sr._norm_key("Infosys Limited")] == "INFY"


class TestResolveExactSymbol:
    def test_exact_symbol_passes_through(self):
        assert sr.resolve_symbol("NATCOPHARM", "NSE") == "NATCOPHARM"
        assert sr.resolve_symbol("RELIANCE", "NSE") == "RELIANCE"
        # Special chars in catalog are preserved.
        assert sr.resolve_symbol("ARE&M", "NSE") == "ARE&M"
        assert sr.resolve_symbol("BAJAJ-AUTO", "NSE") == "BAJAJ-AUTO"

    def test_case_insensitive_symbol_hit(self):
        assert sr.resolve_symbol("infy", "NSE") == "INFY"
        assert sr.resolve_symbol("natcopharm", "NSE") == "NATCOPHARM"


class TestResolveAlias:
    def test_common_nicknames(self):
        assert sr.resolve_symbol("NATCO", "NSE") == "NATCOPHARM"
        assert sr.resolve_symbol("infosys", "NSE") == "INFY"
        assert sr.resolve_symbol("bajajauto", "NSE") == "BAJAJ-AUTO"
        assert sr.resolve_symbol("larsen", "NSE") == "LT"

    def test_alias_ignores_extra_words_and_spaces(self):
        assert sr.resolve_symbol("Reliance Industries", "NSE") == "RELIANCE"


class TestResolveCompanyName:
    def test_full_company_name_to_symbol(self):
        assert sr.resolve_symbol("Natco Pharma Limited", "NSE") == "NATCOPHARM"
        assert sr.resolve_symbol("Infosys Limited", "NSE") == "INFY"
        # Catalog name for LT is "Larsen & Toubro Limited".
        assert sr.resolve_symbol("Larsen & Toubro Limited", "NSE") == "LT"


class TestResolvePassThrough:
    def test_bse_numeric_scrip_unchanged(self):
        assert sr.resolve_symbol("500325", "BSE") == "500325"

    def test_nse_ns_suffix_stripped(self):
        assert sr.resolve_symbol("RELIANCE.NS", "NSE") == "RELIANCE"

    def test_bse_bo_suffix_stripped(self):
        assert sr.resolve_symbol("500325.BO", "BSE") == "500325"

    def test_unknown_input_returned_as_is_without_network(self):
        # Network disabled by autouse fixture; unknown input falls through.
        assert sr.resolve_symbol("ZZZZ_NOT_A_REAL_TICKER", "NSE") == "ZZZZ_NOT_A_REAL_TICKER"


class TestNormalizeTickerIntegration:
    def test_normalize_resolves_short_name_to_canonical_nse_symbol(self):
        assert normalize_ticker("natco", ExchangeEnum.NSE) == "NATCOPHARM.NS"

    def test_normalize_resolves_company_name(self):
        assert normalize_ticker("Infosys Limited", ExchangeEnum.NSE) == "INFY.NS"

    def test_normalize_keeps_exact_symbol(self):
        assert normalize_ticker("RELIANCE", ExchangeEnum.NSE) == "RELIANCE.NS"

    def test_normalize_nasdaq_unchanged(self):
        assert normalize_ticker("AAPL", ExchangeEnum.NASDAQ) == "AAPL"


class TestYfSearchFallback:
    """The network fallback must only run when env-flag is on AND yf.Search
    returns a quote on the right exchange. This test stubs yf.Search."""

    def test_yf_search_path_hit(self, monkeypatch):
        monkeypatch.setenv("SYMBOL_RESOLVER_NETWORK", "1")

        class _StubSearch:
            def __init__(self, *a, **kw):
                self.quotes = [
                    {"symbol": "SOMEFOO.NS", "longname": "Some Foo Ltd", "exchange": "NSI"},
                    {"symbol": "SOMEFOO.BO", "longname": "Some Foo Ltd", "exchange": "BSE"},
                ]

        class _StubYf:
            Search = _StubSearch

        monkeypatch.setattr(
            "builtins.__import__",
            _patched_import({"yfinance": _StubYf}),
        )

        # Input isn't in catalog / aliases -> stub Search resolves it.
        assert sr.resolve_symbol("SOMEFOO", "NSE") == "SOMEFOO"
        # With a non-catalog input Search would normally hit; here the stub
        # returns "SOMEFOO.NS" so resolver returns "SOMEFOO" (suffix stripped).

    def test_yf_search_misses_returns_original(self, monkeypatch):
        monkeypatch.setenv("SYMBOL_RESOLVER_NETWORK", "1")

        class _StubSearch:
            def __init__(self, *a, **kw):
                self.quotes = []

        class _StubYf:
            Search = _StubSearch

        monkeypatch.setattr(
            "builtins.__import__",
            _patched_import({"yfinance": _StubYf}),
        )

        assert sr.resolve_symbol("QQQQUNKNOWN", "NSE") == "QQQQUNKNOWN"


def _patched_import(replacements: dict):
    """Return a new __import__ that substitutes certain modules."""
    import builtins
    real_import = builtins.__import__

    def _imp(name, globals=None, locals=None, fromlist=(), level=0):
        if name in replacements:
            return replacements[name]
        return real_import(name, globals, locals, fromlist, level)

    return _imp
