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

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.tools.fundamental_tools import (
    get_insider_transactions,
    get_mutual_fund_holdings,
    get_earnings_calendar,
)


class TestGetInsiderTransactions:
    @patch("src.tools.fundamental_tools.yf")
    def test_returns_insider_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = pd.DataFrame({
            "Insider": ["John CEO", "Jane CFO"],
            "Start Date": ["2026-03-01", "2026-03-15"],
            "Transaction": ["Sale", "Purchase"],
            "Shares": [10000, 5000],
            "Value": [500000, 250000],
        })
        mock_yf.Ticker.return_value = mock_ticker
        result = get_insider_transactions.__wrapped__("AAPL", "NASDAQ")
        assert "transactions" in result
        assert "net_sentiment" in result
        assert len(result["transactions"]) == 2

    @patch("src.tools.fundamental_tools.yf")
    def test_empty_insider_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.insider_transactions = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker
        result = get_insider_transactions.__wrapped__("SMALLCAP", "NSE")
        assert "message" in result


class TestGetMutualFundHoldings:
    @patch("src.tools.fundamental_tools.yf")
    def test_returns_holdings(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.institutional_holders = pd.DataFrame({
            "Holder": ["Vanguard", "BlackRock"],
            "Shares": [1000000, 800000],
            "Date Reported": ["2026-03-31", "2026-03-31"],
            "% Out": [5.0, 4.0],
            "Value": [100000000, 80000000],
        })
        mock_ticker.mutualfund_holders = pd.DataFrame({
            "Holder": ["Fidelity Growth Fund"],
            "Shares": [500000],
            "Date Reported": ["2026-03-31"],
            "% Out": [2.5],
            "Value": [50000000],
        })
        mock_yf.Ticker.return_value = mock_ticker
        result = get_mutual_fund_holdings.__wrapped__("AAPL", "NASDAQ")
        assert "institutional_holders" in result
        assert "total_institutional_pct" in result
        assert result["total_institutional_pct"] == 9.0

    @patch("src.tools.fundamental_tools.yf")
    def test_no_holdings_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.institutional_holders = None
        mock_ticker.mutualfund_holders = None
        mock_yf.Ticker.return_value = mock_ticker
        result = get_mutual_fund_holdings.__wrapped__("SMALLCAP", "NSE")
        assert "message" in result


class TestGetEarningsCalendar:
    @patch("src.tools.fundamental_tools.yf")
    def test_returns_earnings_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.earnings_dates = pd.DataFrame({
            "EPS Estimate": [1.50, 1.40, 1.30, 1.20],
            "Reported EPS": [None, 1.55, 1.35, 1.25],
            "Surprise(%)": [None, 10.7, 3.8, 4.2],
        }, index=pd.DatetimeIndex([
            "2026-07-15", "2026-04-01", "2026-01-15", "2025-10-15"
        ]))
        mock_yf.Ticker.return_value = mock_ticker
        result = get_earnings_calendar.__wrapped__("AAPL", "NASDAQ")
        assert "next_earnings_date" in result
        assert "earnings_history" in result

    @patch("src.tools.fundamental_tools.yf")
    def test_no_earnings_data(self, mock_yf):
        mock_ticker = MagicMock()
        mock_ticker.earnings_dates = None
        mock_yf.Ticker.return_value = mock_ticker
        result = get_earnings_calendar.__wrapped__("SMALLCAP", "NSE")
        assert "message" in result
