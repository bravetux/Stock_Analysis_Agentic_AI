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
# Developed: 17th April 2026

"""Phase 2a — macro snapshot and analyst consensus fetchers.

This module holds the data contracts (IndicatorReading, MacroSnapshot,
AnalystConsensus) and every external fetcher used by the macro
investigator. All fetch failures are swallowed into MacroSnapshot.missing
so that a partial outage of any single source cannot break the pipeline.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
import re
import requests
import yfinance as yf
from bs4 import BeautifulSoup

from src.config.settings import settings


@dataclass
class IndicatorReading:
    code: str
    label: str
    value: float
    d1_pct: Optional[float]
    w1_pct: Optional[float]
    m1_pct: Optional[float]
    regime: Optional[str]
    source: str
    as_of: datetime


@dataclass
class MacroSnapshot:
    as_of: datetime
    indicators: dict[str, IndicatorReading] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


@dataclass
class AnalystConsensus:
    mean_target: Optional[float]
    median_target: Optional[float]
    current_price: float
    implied_upside_pct: Optional[float]
    buy: int
    hold: int
    sell: int
    total_analysts: int
    revision_30d: dict  # {"raised": int, "cut": int, "net": int}
    recommendation_trend: str  # strengthening_buy | cooling | stable | weakening


def classify_regime(
    code: str,
    d1_pct: Optional[float] = None,
    w1_pct: Optional[float] = None,
    m1_pct: Optional[float] = None,
    value: Optional[float] = None,
) -> Optional[str]:
    """Map (indicator, deltas, level) → regime label. Pure function, no I/O.

    Thresholds mirror the rule table in the design spec §4.3.
    """
    c = code.upper()
    if c == "USDINR":
        if d1_pct is not None and d1_pct >= 1.0:
            return "weakening_rupee"
        if d1_pct is not None and d1_pct <= -1.0:
            return "strengthening_rupee"
        return "neutral"
    if c == "INDIAVIX":
        if value is None:
            return None
        return "risk_off" if value >= 20.0 else "low_vol"
    if c == "BRENT":
        if w1_pct is not None and w1_pct >= 5.0:
            return "oil_spike"
        if w1_pct is not None and w1_pct <= -5.0:
            return "oil_slump"
        return "neutral"
    if c == "NIFTY50":
        if m1_pct is not None and m1_pct <= -5.0:
            return "correction"
        if m1_pct is not None and m1_pct >= 5.0:
            return "rally"
        return "neutral"
    if c == "DXY":
        if m1_pct is not None and m1_pct >= 3.0:
            return "strong_dollar"
        if m1_pct is not None and m1_pct <= -3.0:
            return "weak_dollar"
        return "neutral"
    if c == "GIFTNIFTY":
        if d1_pct is not None and d1_pct >= 0.5:
            return "positive_pre_open"
        if d1_pct is not None and d1_pct <= -0.5:
            return "negative_pre_open"
        return "neutral"
    # Indicators without explicit regime rules (BANKNIFTY, GOLD_INR,
    # FEDFUNDS, INDIA10Y) are informational only.
    if c in {"BANKNIFTY", "SENSEX", "GOLD_INR", "FEDFUNDS", "INDIA10Y"}:
        return None
    return None


class FetchError(RuntimeError):
    """Raised when a single-indicator fetch fails. Callers catch and record
    the indicator code in MacroSnapshot.missing."""


def _pct_change(df_close, lookback_days: int) -> Optional[float]:
    if df_close is None or len(df_close) <= lookback_days:
        return None
    try:
        latest = float(df_close.iloc[-1])
        past = float(df_close.iloc[-1 - lookback_days])
    except Exception:
        return None
    if past == 0:
        return None
    return (latest / past - 1.0) * 100.0


def fetch_yf_indicator(code: str, yf_ticker: str, label: str) -> IndicatorReading:
    """Fetch one yfinance-backed indicator. Returns IndicatorReading or raises FetchError."""
    try:
        ticker = yf.Ticker(yf_ticker)
        hist = ticker.history(period="3mo", auto_adjust=False)
    except Exception as e:
        raise FetchError(f"{code}: yfinance exception: {e}") from e
    if hist is None or len(hist) == 0 or "Close" not in hist.columns:
        raise FetchError(f"{code}: empty history")
    close = hist["Close"].dropna()
    if len(close) == 0:
        raise FetchError(f"{code}: no close data")
    value = float(close.iloc[-1])
    d1 = _pct_change(close, 1)
    w1 = _pct_change(close, 5)   # 5 business days ≈ 1 week
    m1 = _pct_change(close, 21)  # 21 business days ≈ 1 month
    regime = classify_regime(code, d1_pct=d1, w1_pct=w1, m1_pct=m1, value=value)
    return IndicatorReading(
        code=code, label=label, value=value,
        d1_pct=d1, w1_pct=w1, m1_pct=m1,
        regime=regime, source="yfinance",
        as_of=datetime.now(timezone.utc),
    )


# Per-indicator ticker map for yfinance-backed fetches
YF_INDICATOR_MAP: dict[str, tuple[str, str]] = {
    "USDINR":    ("INR=X",     "USD/INR"),
    "BRENT":     ("BZ=F",      "Brent crude (USD/bbl)"),
    "NIFTY50":   ("^NSEI",     "Nifty 50"),
    "SENSEX":    ("^BSESN",    "BSE Sensex"),
    "INDIAVIX":  ("^INDIAVIX", "India VIX"),
    "DXY":       ("DX-Y.NYB",  "Dollar Index (DXY)"),
    "BANKNIFTY": ("^NSEBANK",  "Bank Nifty"),
}


_GRAMS_PER_OZ = 31.1035


def fetch_gold_inr(
    *,
    usdinr_reading: IndicatorReading,
    gold_usd_reading: IndicatorReading,
) -> IndicatorReading:
    """Derived: USD/oz × INR/USD → ₹ per 10g."""
    value = gold_usd_reading.value * usdinr_reading.value / _GRAMS_PER_OZ * 10.0
    return IndicatorReading(
        code="GOLD_INR", label="Gold (₹ / 10g)", value=value,
        d1_pct=gold_usd_reading.d1_pct, w1_pct=gold_usd_reading.w1_pct,
        m1_pct=gold_usd_reading.m1_pct,
        regime=None, source="derived",
        as_of=datetime.now(timezone.utc),
    )


_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockAnalysisBot/1.0)",
}


def _http_get(url: str) -> str:
    try:
        resp = requests.get(
            url,
            timeout=settings.macro_fetch_timeout_seconds,
            headers=_HTTP_HEADERS,
        )
    except Exception as e:
        raise FetchError(f"GET {url}: {e}") from e
    if resp.status_code != 200:
        raise FetchError(f"GET {url}: status {resp.status_code}")
    return resp.text


def fetch_india_10y() -> IndicatorReading:
    """Scrape investing.com for India 10Y yield. Single-source, no fallback
    (the yfinance ^TNX fallback is US, not India, so we flag as missing
    instead of returning wrong data)."""
    html = _http_get("https://www.investing.com/rates-bonds/india-10-year-bond-yield")
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find(attrs={"data-test": "instrument-price-last"})
    try:
        if node is None:
            m = re.search(r'instrument-price-last[^>]*>([\d.,]+)<', html)
            if not m:
                raise FetchError("INDIA10Y: price node not found")
            val = float(m.group(1).replace(",", ""))
        else:
            val = float(node.get_text(strip=True).replace(",", ""))
    except ValueError as e:
        raise FetchError(f"INDIA10Y: invalid yield value: {e}") from e
    return IndicatorReading(
        code="INDIA10Y", label="India 10Y yield (%)", value=val,
        d1_pct=None, w1_pct=None, m1_pct=None,
        regime=None, source="investing.com",
        as_of=datetime.now(timezone.utc),
    )


def fetch_fedfunds() -> IndicatorReading:
    """Try FRED CSV first, fall back to yfinance ^IRX (13w T-bill)."""
    try:
        csv = _http_get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
        )
        lines = [line for line in csv.splitlines() if "," in line]
        if len(lines) < 2:
            raise FetchError("FEDFUNDS: empty FRED CSV")
        last = lines[-1].split(",")
        value = float(last[1])
        return IndicatorReading(
            code="FEDFUNDS", label="Fed Funds Rate (%)", value=value,
            d1_pct=None, w1_pct=None, m1_pct=None,
            regime=None, source="fred",
            as_of=datetime.now(timezone.utc),
        )
    except (FetchError, ValueError, IndexError):
        pass
    reading = fetch_yf_indicator("FEDFUNDS_PROXY", "^IRX", "Fed Funds proxy (^IRX)")
    reading.code = "FEDFUNDS"
    reading.source = "yfinance_irx"
    return reading


def fetch_giftnifty() -> IndicatorReading:
    """Best-effort scrape of GIFT Nifty (post-SGX, now NSE IFSC).
    Investing.com page: nifty-50-futures. Parse last price and daily change."""
    html = _http_get("https://www.investing.com/indices/nifty-futures")
    soup = BeautifulSoup(html, "html.parser")
    price_node = soup.find(attrs={"data-test": "instrument-price-last"})
    chg_node = soup.find(attrs={"data-test": "instrument-price-change-percent"})
    if price_node is None:
        raise FetchError("GIFTNIFTY: price node not found")
    try:
        value = float(price_node.get_text(strip=True).replace(",", ""))
    except ValueError as e:
        raise FetchError(f"GIFTNIFTY: invalid price value: {e}") from e
    d1_pct = None
    if chg_node is not None:
        txt = chg_node.get_text(strip=True).replace("%", "").replace("(", "").replace(")", "")
        try:
            d1_pct = float(txt)
        except ValueError:
            d1_pct = None
    regime = classify_regime("GIFTNIFTY", d1_pct=d1_pct, w1_pct=None, m1_pct=None)
    return IndicatorReading(
        code="GIFTNIFTY", label="GIFT Nifty", value=value,
        d1_pct=d1_pct, w1_pct=None, m1_pct=None,
        regime=regime, source="investing.com",
        as_of=datetime.now(timezone.utc),
    )


def _build_fetcher_registry() -> dict[str, Callable[[], IndicatorReading]]:
    """Code → zero-arg callable returning IndicatorReading."""
    registry: dict[str, Callable[[], IndicatorReading]] = {}
    for code, (yf_ticker, label) in YF_INDICATOR_MAP.items():
        registry[code] = (lambda c=code, t=yf_ticker, l=label:
                          fetch_yf_indicator(c, t, l))
    registry["INDIA10Y"]  = fetch_india_10y
    registry["FEDFUNDS"]  = fetch_fedfunds
    # GIFTNIFTY intentionally disabled — scrape source is unreliable and
    # constantly shows up as "missing". Fetcher is preserved for tests.
    return registry


def _fetch_gold_usd() -> IndicatorReading:
    return fetch_yf_indicator("GOLD_USD", "GC=F", "Gold (USD/oz)")


def _run_all_fetchers() -> tuple[dict[str, IndicatorReading], list[str]]:
    """Run all single-indicator fetchers in parallel, then derive GOLD_INR.
    Returns (ok_readings, missing_codes)."""
    registry = _build_fetcher_registry()
    ok: dict[str, IndicatorReading] = {}
    missing: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_code = {pool.submit(fn): code for code, fn in registry.items()}
        future_gold = pool.submit(_fetch_gold_usd)
        for fut in as_completed(list(future_to_code.keys()) + [future_gold]):
            if fut is future_gold:
                try:
                    ok["_GOLD_USD"] = fut.result()
                except FetchError:
                    missing.append("GOLD_INR")
                continue
            code = future_to_code[fut]
            try:
                ok[code] = fut.result()
            except FetchError:
                missing.append(code)
    if "_GOLD_USD" in ok and "USDINR" in ok:
        ok["GOLD_INR"] = fetch_gold_inr(
            usdinr_reading=ok["USDINR"],
            gold_usd_reading=ok["_GOLD_USD"],
        )
    elif "GOLD_INR" not in missing:
        missing.append("GOLD_INR")
    ok.pop("_GOLD_USD", None)
    return ok, missing


_ALL_CODES = [
    "USDINR", "BRENT", "INDIA10Y", "NIFTY50", "SENSEX", "INDIAVIX",
    "DXY", "BANKNIFTY", "GOLD_INR", "FEDFUNDS",
]


def _all_fresh(store) -> bool:
    """Cache signal: snapshot is fresh iff USDINR is within the cache window
    AND every code in _ALL_CODES has at least one historical row. The second
    check handles newly-added indicators: when a code is added to _ALL_CODES,
    the store won't have any row for it yet — we must force a fresh fetch so
    the new code gets populated rather than living in `missing` forever."""
    if not store.is_fresh("USDINR", settings.macro_snapshot_cache_minutes):
        return False
    for code in _ALL_CODES:
        if store.get_latest(code) is None:
            return False
    return True


def _snapshot_from_store(store) -> MacroSnapshot:
    indicators: dict[str, IndicatorReading] = {}
    missing: list[str] = []
    for code in _ALL_CODES:
        latest = store.get_latest(code)
        if latest is None:
            missing.append(code)
        else:
            indicators[code] = latest
    return MacroSnapshot(
        as_of=datetime.now(timezone.utc),
        indicators=indicators,
        missing=missing,
    )


def fetch_macro_snapshot(
    use_cache: bool = True,
    store=None,
    use_store: bool = True,
) -> MacroSnapshot:
    """Fetch all 10 indicators (or return cached snapshot if fresh).

    - use_cache: check store.is_fresh() before fetching
    - store: MacroStore instance; if None, constructed from settings.db_path
    - use_store: disable store entirely (tests only)
    """
    if use_store and store is None:
        from src.db.macro_store import MacroStore
        store = MacroStore(db_path=settings.db_path)

    if use_cache and store is not None and _all_fresh(store):
        return _snapshot_from_store(store)

    ok, missing = _run_all_fetchers()
    snap = MacroSnapshot(
        as_of=datetime.now(timezone.utc),
        indicators=ok,
        missing=missing,
    )
    if use_store and store is not None:
        try:
            store.insert_snapshot(snap)
            store.prune(settings.macro_history_retention_days)
        except Exception:
            pass  # persistence is best-effort
    return snap


def _classify_trend(raised: int, cut: int) -> str:
    net = raised - cut
    if net >= 2:
        return "strengthening_buy"
    if net <= -2:
        return "weakening"
    if raised == 0 and cut == 0:
        return "stable"
    return "cooling" if net < 0 else "stable"


def _ticker_symbol_for_exchange(ticker: str, exchange: str) -> str:
    ex = (exchange or "").upper()
    if ex == "NSE":
        return f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
    if ex == "BSE":
        return f"{ticker}.BO" if not ticker.endswith(".BO") else ticker
    return ticker


def fetch_analyst_consensus(ticker: str, exchange: str) -> AnalystConsensus:
    """yfinance-backed consensus: targets, buy/hold/sell counts, 30d revisions."""
    empty = AnalystConsensus(
        mean_target=None, median_target=None, current_price=0.0,
        implied_upside_pct=None,
        buy=0, hold=0, sell=0, total_analysts=0,
        revision_30d={"raised": 0, "cut": 0, "net": 0},
        recommendation_trend="stable",
    )
    try:
        tk = yf.Ticker(_ticker_symbol_for_exchange(ticker, exchange))
        current_price = 0.0
        try:
            current_price = float(tk.fast_info.get("last_price", 0) or 0)
        except Exception:
            pass
        targets = {}
        try:
            targets = tk.analyst_price_targets or {}
        except Exception:
            targets = {}
        mean_t = float(targets.get("mean")) if targets.get("mean") else None
        med_t = float(targets.get("median")) if targets.get("median") else None
        upside = None
        if mean_t is not None and current_price:
            upside = (mean_t / current_price - 1) * 100.0

        buy = hold = sell = 0
        raised = cut = 0
        try:
            recs = tk.recommendations
        except Exception:
            recs = pd.DataFrame()
        if recs is not None and len(recs) > 0:
            cutoff = datetime.now() - timedelta(days=30)
            recent = recs[recs.index >= cutoff] if hasattr(recs.index, "__ge__") else recs
            for _, row in recent.iterrows():
                grade = str(row.get("To Grade", row.get("toGrade", ""))).lower()
                action = str(row.get("Action", "")).lower()
                if "buy" in grade or "outperform" in grade or "overweight" in grade:
                    buy += 1
                elif "sell" in grade or "underperform" in grade or "underweight" in grade:
                    sell += 1
                else:
                    hold += 1
                if action in {"up", "upgrade"}:
                    raised += 1
                elif action in {"down", "downgrade"}:
                    cut += 1

        total = buy + hold + sell
        return AnalystConsensus(
            mean_target=mean_t, median_target=med_t,
            current_price=current_price, implied_upside_pct=upside,
            buy=buy, hold=hold, sell=sell, total_analysts=total,
            revision_30d={"raised": raised, "cut": cut, "net": raised - cut},
            recommendation_trend=_classify_trend(raised, cut),
        )
    except Exception:
        return empty
