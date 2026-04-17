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

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest


def _fake_recs(rows):
    """Build a DataFrame that mimics yfinance Ticker.recommendations.
    rows: list of (days_ago, firm, to_grade)"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {"Firm": [], "To Grade": [], "Action": []}
    idx = []
    for days_ago, firm, grade in rows:
        idx.append(now - timedelta(days=days_ago))
        data["Firm"].append(firm)
        data["To Grade"].append(grade)
        data["Action"].append("up" if "Buy" in grade or "Outperform" in grade else "down")
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx))


@patch("src.tools.macro_tools.yf.Ticker")
def test_analyst_consensus_happy_path(mock_tk):
    tk = MagicMock()
    tk.recommendations = _fake_recs([
        (5, "FirmA", "Buy"), (10, "FirmB", "Hold"), (20, "FirmC", "Buy"),
        (40, "FirmD", "Sell"),
    ])
    tk.analyst_price_targets = {
        "mean": 1500.0, "median": 1480.0, "low": 1200.0, "high": 1800.0,
    }
    tk.fast_info = {"last_price": 1300.0}
    mock_tk.return_value = tk

    from src.tools.macro_tools import fetch_analyst_consensus
    c = fetch_analyst_consensus("RELIANCE", "NSE")
    assert c.mean_target == 1500.0
    assert c.current_price == 1300.0
    assert abs(c.implied_upside_pct - ((1500/1300 - 1) * 100)) < 1e-6
    assert c.buy >= 2
    assert c.total_analysts >= 3
    assert c.revision_30d["net"] >= 0


@patch("src.tools.macro_tools.yf.Ticker")
def test_analyst_consensus_no_recommendations(mock_tk):
    tk = MagicMock()
    tk.recommendations = pd.DataFrame()
    tk.analyst_price_targets = {}
    tk.fast_info = {"last_price": 1300.0}
    mock_tk.return_value = tk
    from src.tools.macro_tools import fetch_analyst_consensus
    c = fetch_analyst_consensus("RELIANCE", "NSE")
    assert c.total_analysts == 0
    assert c.mean_target is None
    assert c.recommendation_trend == "stable"


@patch("src.tools.macro_tools.yf.Ticker")
def test_analyst_consensus_yfinance_error_returns_empty(mock_tk):
    mock_tk.side_effect = Exception("boom")
    from src.tools.macro_tools import fetch_analyst_consensus
    c = fetch_analyst_consensus("RELIANCE", "NSE")
    assert c.total_analysts == 0
    assert c.mean_target is None


from src.agents.evidence import Signal


@patch("src.agents.fundamental_agent.fetch_analyst_consensus")
def test_fundamental_agent_emits_analyst_evidence(mock_fetch):
    from src.tools.macro_tools import AnalystConsensus
    mock_fetch.return_value = AnalystConsensus(
        mean_target=1500.0, median_target=1480.0, current_price=1300.0,
        implied_upside_pct=15.38,
        buy=12, hold=4, sell=1, total_analysts=17,
        revision_30d={"raised": 3, "cut": 1, "net": 2},
        recommendation_trend="strengthening_buy",
    )
    from src.agents.fundamental_agent import emit_analyst_evidence
    ev = emit_analyst_evidence("RELIANCE", "NSE")
    assert len(ev) >= 2
    assert all(e.thread_id == "fundamental" for e in ev)
    assert all(e.source_tool == "analyst_consensus" for e in ev)
    assert any(e.signal == Signal.BULLISH for e in ev)


@patch("src.agents.fundamental_agent.fetch_analyst_consensus")
def test_fundamental_agent_no_coverage_emits_caveat(mock_fetch):
    from src.tools.macro_tools import AnalystConsensus
    mock_fetch.return_value = AnalystConsensus(
        mean_target=None, median_target=None, current_price=0.0,
        implied_upside_pct=None,
        buy=0, hold=0, sell=0, total_analysts=0,
        revision_30d={"raised": 0, "cut": 0, "net": 0},
        recommendation_trend="stable",
    )
    from src.agents.fundamental_agent import emit_analyst_evidence
    ev = emit_analyst_evidence("RELIANCE", "NSE")
    assert len(ev) == 1
    assert "unavailable" in ev[0].claim.lower()


def test_emit_analyst_evidence_flag_off_returns_empty(monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "enable_analyst_consensus", False)
    from src.agents.fundamental_agent import emit_analyst_evidence
    assert emit_analyst_evidence("RELIANCE", "NSE") == []
