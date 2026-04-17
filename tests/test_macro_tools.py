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

from datetime import datetime, timezone
from src.tools.macro_tools import (
    IndicatorReading, MacroSnapshot, AnalystConsensus, classify_regime
)


def _reading(**kwargs):
    base = dict(
        code="USDINR", label="USD/INR", value=86.15,
        d1_pct=1.2, w1_pct=1.1, m1_pct=0.8,
        regime=None, source="yfinance",
        as_of=datetime.now(timezone.utc),  # Current time for fresh cache hits
    )
    base.update(kwargs)
    return IndicatorReading(**base)


def test_indicator_reading_roundtrip():
    r = _reading()
    assert r.code == "USDINR"
    assert r.value == 86.15


def test_macro_snapshot_holds_indicators_and_missing():
    snap = MacroSnapshot(
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
        indicators={"USDINR": _reading()},
        missing=["FEDFUNDS"],
    )
    assert "USDINR" in snap.indicators
    assert snap.missing == ["FEDFUNDS"]


def test_analyst_consensus_roundtrip():
    c = AnalystConsensus(
        mean_target=1500.0, median_target=1480.0, current_price=1300.0,
        implied_upside_pct=15.38,
        buy=12, hold=4, sell=1, total_analysts=17,
        revision_30d={"raised": 3, "cut": 1, "net": 2},
        recommendation_trend="strengthening_buy",
    )
    assert c.total_analysts == 17
    assert c.revision_30d["net"] == 2


def test_classify_regime_usdinr_weakening():
    assert classify_regime("USDINR", d1_pct=1.2, w1_pct=None, m1_pct=None) == "weakening_rupee"


def test_classify_regime_usdinr_strengthening():
    assert classify_regime("USDINR", d1_pct=-1.5, w1_pct=None, m1_pct=None) == "strengthening_rupee"


def test_classify_regime_vix_risk_off():
    assert classify_regime("INDIAVIX", d1_pct=None, w1_pct=None, m1_pct=None, value=21.0) == "risk_off"


def test_classify_regime_vix_boundary_at_20():
    # 19.9 → low vol, 20.0 → risk_off (inclusive boundary)
    assert classify_regime("INDIAVIX", d1_pct=None, w1_pct=None, m1_pct=None, value=19.9) == "low_vol"
    assert classify_regime("INDIAVIX", d1_pct=None, w1_pct=None, m1_pct=None, value=20.0) == "risk_off"


def test_classify_regime_brent_oil_spike():
    assert classify_regime("BRENT", d1_pct=None, w1_pct=5.5, m1_pct=None) == "oil_spike"


def test_classify_regime_returns_none_for_unknown_code():
    assert classify_regime("MYSTERY", d1_pct=99, w1_pct=99, m1_pct=99) is None


from unittest.mock import patch, MagicMock
import pandas as pd
import pytest


def _fake_history_df(prices: list[float]):
    """Return a DataFrame mimicking yf.Ticker(...).history(period=...)."""
    idx = pd.date_range("2026-03-15", periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=idx)


@patch("src.tools.macro_tools.yf.Ticker")
def test_fetch_yf_indicator_happy_path(mock_ticker):
    mock_ticker.return_value.history.return_value = _fake_history_df(
        [82.0] * 19 + [86.0, 86.15]
    )
    from src.tools.macro_tools import fetch_yf_indicator
    r = fetch_yf_indicator("USDINR", "INR=X", "USD/INR")
    assert r.code == "USDINR"
    assert r.value == 86.15
    assert r.d1_pct is not None and abs(r.d1_pct - (86.15 / 86.0 - 1) * 100) < 1e-6
    assert r.w1_pct is not None  # we have 21 business days of history
    assert r.source == "yfinance"


@patch("src.tools.macro_tools.yf.Ticker")
def test_fetch_yf_indicator_empty_history_raises(mock_ticker):
    mock_ticker.return_value.history.return_value = pd.DataFrame()
    from src.tools.macro_tools import fetch_yf_indicator, FetchError
    with pytest.raises(FetchError):
        fetch_yf_indicator("USDINR", "INR=X", "USD/INR")


@patch("src.tools.macro_tools.yf.Ticker")
def test_fetch_yf_indicator_http_exception_raises(mock_ticker):
    mock_ticker.return_value.history.side_effect = Exception("boom")
    from src.tools.macro_tools import fetch_yf_indicator, FetchError
    with pytest.raises(FetchError):
        fetch_yf_indicator("USDINR", "INR=X", "USD/INR")


def test_fetch_gold_inr_multiplies_usd_gold_by_usdinr():
    from src.tools.macro_tools import fetch_gold_inr
    fake_gold = IndicatorReading(
        code="GOLD_USD", label="Gold USD/oz", value=2400.0,
        d1_pct=0.5, w1_pct=2.0, m1_pct=5.0,
        regime=None, source="yfinance",
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    fake_usdinr = IndicatorReading(
        code="USDINR", label="USD/INR", value=86.0,
        d1_pct=0.0, w1_pct=0.0, m1_pct=0.0,
        regime=None, source="yfinance",
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    r = fetch_gold_inr(usdinr_reading=fake_usdinr, gold_usd_reading=fake_gold)
    # 2400 USD/oz × 86 INR/USD ÷ 31.1035 (g/oz) × 10 (g per '10g unit')
    expected = 2400.0 * 86.0 / 31.1035 * 10.0
    assert abs(r.value - expected) < 1.0
    assert r.source == "derived"


@patch("src.tools.macro_tools.requests.get")
def test_fetch_india_10y_scrape_happy(mock_get):
    html = '<span data-test="instrument-price-last">6.95</span>'
    mock_get.return_value = MagicMock(status_code=200, text=html)
    from src.tools.macro_tools import fetch_india_10y
    r = fetch_india_10y()
    assert r.code == "INDIA10Y"
    assert r.value == 6.95


@patch("src.tools.macro_tools.requests.get")
def test_fetch_india_10y_scrape_http_error_raises(mock_get):
    mock_get.return_value = MagicMock(status_code=500, text="")
    from src.tools.macro_tools import fetch_india_10y, FetchError
    with pytest.raises(FetchError):
        fetch_india_10y()


@patch("src.tools.macro_tools.requests.get")
def test_fetch_fedfunds_fred_happy(mock_get):
    csv = "DATE,FEDFUNDS\n2026-03-01,5.25\n2026-04-01,5.30\n"
    mock_get.return_value = MagicMock(status_code=200, text=csv)
    from src.tools.macro_tools import fetch_fedfunds
    r = fetch_fedfunds()
    assert r.code == "FEDFUNDS"
    assert r.value == 5.30
    assert r.source == "fred"


@patch("src.tools.macro_tools.requests.get")
def test_fetch_fedfunds_fallback_when_fred_fails(mock_get):
    mock_get.return_value = MagicMock(status_code=500, text="")
    from src.tools.macro_tools import fetch_fedfunds, FetchError
    with patch("src.tools.macro_tools.yf.Ticker") as mock_tk:
        mock_tk.return_value.history.return_value = _fake_history_df([5.0] * 22)
        r = fetch_fedfunds()
        assert r.source == "yfinance_irx"


@patch("src.tools.macro_tools.requests.get")
def test_fetch_giftnifty_scrape_empty_raises(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="<html/>")
    from src.tools.macro_tools import fetch_giftnifty, FetchError
    with pytest.raises(FetchError):
        fetch_giftnifty()


@patch("src.tools.macro_tools.requests.get")
def test_fetch_india_10y_invalid_value_raises_fetch_error(mock_get):
    html = '<span data-test="instrument-price-last">N/A</span>'
    mock_get.return_value = MagicMock(status_code=200, text=html)
    from src.tools.macro_tools import fetch_india_10y, FetchError
    with pytest.raises(FetchError):
        fetch_india_10y()


@patch("src.tools.macro_tools.requests.get")
def test_fetch_fedfunds_malformed_csv_falls_back(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="DATE,FEDFUNDS\n2026-04-01,NOT_A_NUMBER\n")
    from src.tools.macro_tools import fetch_fedfunds
    with patch("src.tools.macro_tools.yf.Ticker") as mock_tk:
        mock_tk.return_value.history.return_value = _fake_history_df([5.0] * 22)
        r = fetch_fedfunds()
        assert r.source == "yfinance_irx"


@patch("src.tools.macro_tools.requests.get")
def test_fetch_giftnifty_invalid_price_raises_fetch_error(mock_get):
    html = '<div data-test="instrument-price-last">--</div>'
    mock_get.return_value = MagicMock(status_code=200, text=html)
    from src.tools.macro_tools import fetch_giftnifty, FetchError
    with pytest.raises(FetchError):
        fetch_giftnifty()


@patch("src.tools.macro_tools._run_all_fetchers")
def test_fetch_macro_snapshot_partial_failure_populates_missing(mock_run):
    ok = {c: _reading(code=c) for c in
          ["USDINR", "BRENT", "NIFTY50", "INDIAVIX", "DXY",
           "BANKNIFTY", "GOLD_INR", "INDIA10Y"]}
    mock_run.return_value = (ok, ["FEDFUNDS", "GIFTNIFTY"])
    from src.tools.macro_tools import fetch_macro_snapshot
    snap = fetch_macro_snapshot(use_cache=False, use_store=False)
    assert set(snap.indicators.keys()) == set(ok.keys())
    assert snap.missing == ["FEDFUNDS", "GIFTNIFTY"]


@patch("src.tools.macro_tools._run_all_fetchers")
def test_fetch_macro_snapshot_writes_to_store(mock_run, tmp_path):
    from src.tools.macro_tools import fetch_macro_snapshot
    from src.db.macro_store import MacroStore
    ok = {"USDINR": _reading(code="USDINR", value=86.15)}
    mock_run.return_value = (ok, [])
    store = MacroStore(db_path=str(tmp_path / "m.db"))
    fetch_macro_snapshot(use_cache=False, store=store)
    assert store.get_latest("USDINR").value == 86.15


@patch("src.tools.macro_tools._run_all_fetchers")
def test_fetch_macro_snapshot_cache_hit_skips_network(mock_run, tmp_path):
    from src.tools.macro_tools import fetch_macro_snapshot, _ALL_CODES
    from src.db.macro_store import MacroStore
    # Seed every code in _ALL_CODES — the cache is only considered fresh when
    # every required code has at least one row (guards against newly-added
    # indicators silently staying in `missing` forever).
    mock_run.return_value = (
        {c: _reading(code=c, value=100.0) for c in _ALL_CODES},
        [],
    )
    store = MacroStore(db_path=str(tmp_path / "m.db"))
    fetch_macro_snapshot(use_cache=False, store=store)
    assert mock_run.call_count == 1
    fetch_macro_snapshot(use_cache=True, store=store)
    assert mock_run.call_count == 1
