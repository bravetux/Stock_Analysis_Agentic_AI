# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Resolve free-form user input (company name, nickname, symbol) to the
canonical exchange symbol that yfinance / nsetools understand.

Resolution order:
  1. Pass-through for inputs already matching the expected format (suffix /
     valid catalog symbol / numeric BSE scrip code).
  2. Hard-coded alias table for well-known typos (INFOSYS -> INFY,
     BAJAJAUTO -> BAJAJ-AUTO, NATCO -> NATCOPHARM, ...).
  3. Local catalog from ``stocks-names.txt`` (company-name substring match).
  4. ``yfinance.Search`` online lookup with an on-disk cache. Opt-out via
     the SYMBOL_RESOLVER_NETWORK env-flag or when yfinance is unavailable.

The resolver is intentionally conservative: when it cannot find a
confident match it returns the original input unchanged so the existing
``normalize_ticker`` behaviour is preserved.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

# Project root (two parents up from src/config/symbol_resolver.py).
_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_FILE = _ROOT / "stocks-names.txt"
_CACHE_DIR = _ROOT / ".cache" / "symbol_resolver"


# Hard-coded aliases for common user inputs that don't match any NSE symbol.
# Keep short and high-confidence. Anything else should rely on the catalog
# or yf.Search. Keys are compared case-insensitively after stripping spaces.
_ALIASES: dict[str, str] = {
    # user-typed nickname -> canonical NSE symbol
    "NATCO": "NATCOPHARM",
    "INFOSYS": "INFY",
    "BAJAJAUTO": "BAJAJ-AUTO",
    "RELIANCEIND": "RELIANCE",
    "RELIANCEINDUSTRIES": "RELIANCE",
    "TATAMOTORS": "TATAMOTORS",
    "HDFC": "HDFCBANK",  # HDFC Ltd merged into HDFC Bank (Jul-2023)
    "LARSEN": "LT",
    "LARSENTOUBRO": "LT",
    "LARSENANDTOUBRO": "LT",
    "HEROMOTO": "HEROMOTOCO",
    "MUTHOOT": "MUTHOOTFIN",
    "TITANCO": "TITAN",
}


def _norm_key(s: str) -> str:
    """Normalise a free-form user input for lookup: upper-case, remove
    spaces / punctuation / 'ltd'/'limited' suffixes."""
    s = s.upper().strip()
    s = re.sub(r"\b(LIMITED|LTD|INC|CORP|COMPANY|CO)\.?\b", "", s)
    s = re.sub(r"[\s\.,\-_]+", "", s)
    return s


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[set[str], dict[str, str]]:
    """Return (valid_symbols, name_key -> symbol) from ``stocks-names.txt``.

    File format is a tabular dump with a header::

        #    Company Name                                              NSE Symbol
        ---  --------------------------------------------------------  -----------
        1    Amara Raja Energy & Mobility Limited                      ARE&M
        ...

    NSE symbols never contain whitespace, so the symbol is reliably the
    last whitespace-separated token on each data row.
    """
    valid: set[str] = set()
    name_map: dict[str, str] = {}

    if not _CATALOG_FILE.exists():
        logger.warning("symbol-catalog file missing: %s", _CATALOG_FILE)
        return valid, name_map

    for raw in _CATALOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        tokens = line.split()
        if len(tokens) < 3:
            continue
        # First token = serial number (must be digits), last token = symbol.
        if not tokens[0].rstrip(".").isdigit():
            continue
        symbol = tokens[-1]
        name = " ".join(tokens[1:-1])
        if not symbol or not name:
            continue
        valid.add(symbol.upper())
        name_map[_norm_key(name)] = symbol

    logger.info(
        "symbol-resolver catalog loaded: %d symbols, %d name-keys from %s",
        len(valid), len(name_map), _CATALOG_FILE.name,
    )
    return valid, name_map


def _cache_path(key: str, exchange: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_&\-]", "_", key)[:64]
    return _CACHE_DIR / exchange / f"{safe}.json"


def _cache_read(key: str, exchange: str) -> str | None:
    p = _cache_path(key, exchange)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
        return payload.get("symbol") or None
    except Exception:
        return None


def _cache_write(key: str, exchange: str, symbol: str) -> None:
    try:
        p = _cache_path(key, exchange)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": key, "exchange": exchange, "symbol": symbol}), encoding="utf-8")
    except Exception as e:
        logger.debug("symbol-resolver cache write failed: %s", e)


def _network_enabled() -> bool:
    raw = os.environ.get("SYMBOL_RESOLVER_NETWORK", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _search_yfinance(query: str, exchange: str) -> str | None:
    """Use yfinance Search to resolve a free-form query to a symbol on the
    requested exchange. Returns the *display* symbol (no suffix) for NSE/BSE
    and the raw symbol for NASDAQ, or None on any failure.

    Exchange codes reported by yfinance quotes:
      NSE -> exchange == 'NSI'   (symbol ends with '.NS')
      BSE -> exchange == 'BSE'   (symbol ends with '.BO')
      NASDAQ -> exchange == 'NMS' / 'NGM' / 'NCM'
    """
    try:
        import yfinance as yf  # lazy import so tests don't need network
    except Exception:
        return None

    want = exchange.upper()
    try:
        s = yf.Search(query, max_results=8, news_count=0)
        quotes: Iterable[dict] = getattr(s, "quotes", None) or []
    except Exception as e:
        logger.debug("yf.Search failed for %r: %s", query, e)
        return None

    def pick(cond) -> str | None:
        for q in quotes:
            sym = str(q.get("symbol") or "").strip()
            if not sym:
                continue
            if cond(q, sym):
                return sym
        return None

    if want == "NSE":
        sym = pick(lambda q, sym: sym.upper().endswith(".NS"))
        if sym:
            return sym[:-3]  # strip .NS for display
    elif want == "BSE":
        sym = pick(lambda q, sym: sym.upper().endswith(".BO"))
        if sym:
            return sym[:-3]
    elif want == "NASDAQ":
        nasdaq_codes = {"NMS", "NGM", "NCM", "NASDAQ"}
        sym = pick(lambda q, sym: str(q.get("exchange", "")).upper() in nasdaq_codes)
        if sym:
            return sym
    return None


def resolve_symbol(user_input: str, exchange: str) -> str:
    """Return the canonical exchange symbol for a free-form ``user_input``.

    Never raises. When no confident match is found, returns ``user_input``
    stripped of whitespace so the caller can fall back to the existing
    normalisation path.
    """
    raw = (user_input or "").strip()
    if not raw:
        return raw

    exchange = exchange.upper()

    # 1. Already suffixed for this exchange -> strip the suffix for
    #    consistent downstream handling (normalize_ticker re-adds it).
    upper = raw.upper()
    if exchange == "NSE" and upper.endswith(".NS"):
        return raw[:-3]
    if exchange == "BSE" and upper.endswith(".BO"):
        return raw[:-3]

    # 2. Numeric BSE scrip codes pass through unchanged.
    if exchange == "BSE" and raw.isdigit():
        return raw

    # 3. Catalog fast-path for Indian exchanges.
    valid, name_map = _load_catalog()
    if exchange in {"NSE", "BSE"}:
        # Exact catalog symbol -> return canonical (upper-case) form
        # (covers ARE&M, BAJAJ-AUTO, GVT&D, and case variants like "infy").
        if upper in valid:
            return upper

        # Alias hit.
        key = _norm_key(raw)
        if key in _ALIASES:
            return _ALIASES[key]

        # Name-match (handles "Infosys Limited", "Natco Pharma", ...).
        if key in name_map:
            return name_map[key]

    # 4. On-disk cache (covers previous yf.Search resolutions).
    cache_key = raw.upper()
    cached = _cache_read(cache_key, exchange)
    if cached:
        return cached

    # 5. Network fallback via yf.Search. Opt-out via env flag or when
    #    the input already looks like a valid symbol (avoid wasting calls).
    if _network_enabled() and re.fullmatch(r"[A-Za-z0-9&\-_.]+", raw):
        resolved = _search_yfinance(raw, exchange)
        if resolved and resolved.upper() != upper:
            _cache_write(cache_key, exchange, resolved)
            logger.info("symbol-resolver yf.Search: %r (%s) -> %s", raw, exchange, resolved)
            return resolved

    # 6. Give up and return the original (upper-cased for NSE/BSE since
    #    nsetools / BSE quote APIs are case-sensitive). NASDAQ keeps case
    #    in case a class-share suffix matters. normalize_ticker will then
    #    attach the usual suffix and the caller will see a clean 404 if
    #    the symbol genuinely does not exist.
    if exchange in {"NSE", "BSE"}:
        return raw.upper()
    return raw
