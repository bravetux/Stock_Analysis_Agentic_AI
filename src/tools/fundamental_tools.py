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

import logging
import yfinance as yf
import pandas as pd
from strands import tool
from src.config.exchanges import ExchangeEnum, normalize_ticker, get_display_ticker

logger = logging.getLogger(__name__)


@tool
def get_insider_transactions(ticker: str, exchange: str) -> dict:
    """Get recent insider buy/sell transactions for a stock.
    Returns last 10 transactions and net sentiment (net buying vs selling)."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)

    try:
        insider_df = stock.insider_transactions
    except Exception:
        insider_df = None

    if insider_df is None or (isinstance(insider_df, pd.DataFrame) and insider_df.empty):
        return {"ticker": get_display_ticker(ticker), "message": "No insider transaction data available"}

    transactions = []
    buy_count = 0
    sell_count = 0
    for _, row in insider_df.head(10).iterrows():
        txn_type = str(row.get("Transaction", "")).lower()
        is_buy = "purchase" in txn_type or "buy" in txn_type
        if is_buy:
            buy_count += 1
        else:
            sell_count += 1
        transactions.append({
            "insider": str(row.get("Insider", "N/A")),
            "date": str(row.get("Start Date", "N/A")),
            "type": "BUY" if is_buy else "SELL",
            "shares": int(row["Shares"]) if pd.notna(row.get("Shares")) else None,
            "value": float(row["Value"]) if pd.notna(row.get("Value")) else None,
        })

    if buy_count > sell_count:
        net_sentiment = "NET_BUYING"
    elif sell_count > buy_count:
        net_sentiment = "NET_SELLING"
    else:
        net_sentiment = "NEUTRAL"

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "transactions": transactions,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "net_sentiment": net_sentiment,
    }


@tool
def get_mutual_fund_holdings(ticker: str, exchange: str) -> dict:
    """Get institutional and mutual fund holders for a stock.
    Returns top holders and total institutional ownership percentage."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)

    try:
        inst_df = stock.institutional_holders
    except Exception:
        inst_df = None

    try:
        mf_df = stock.mutualfund_holders
    except Exception:
        mf_df = None

    if (inst_df is None or (isinstance(inst_df, pd.DataFrame) and inst_df.empty)) and \
       (mf_df is None or (isinstance(mf_df, pd.DataFrame) and mf_df.empty)):
        return {"ticker": get_display_ticker(ticker), "message": "No institutional/MF holdings data available"}

    institutional_holders = []
    total_pct = 0.0
    if inst_df is not None and isinstance(inst_df, pd.DataFrame) and not inst_df.empty:
        for _, row in inst_df.head(10).iterrows():
            pct = float(row["% Out"]) if pd.notna(row.get("% Out")) else 0
            total_pct += pct
            institutional_holders.append({
                "holder": str(row.get("Holder", "N/A")),
                "shares": int(row["Shares"]) if pd.notna(row.get("Shares")) else None,
                "pct_held": round(pct, 2),
                "date_reported": str(row.get("Date Reported", "N/A")),
            })

    mf_holders = []
    if mf_df is not None and isinstance(mf_df, pd.DataFrame) and not mf_df.empty:
        for _, row in mf_df.head(10).iterrows():
            mf_holders.append({
                "fund": str(row.get("Holder", "N/A")),
                "shares": int(row["Shares"]) if pd.notna(row.get("Shares")) else None,
                "pct_held": round(float(row["% Out"]), 2) if pd.notna(row.get("% Out")) else None,
            })

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "institutional_holders": institutional_holders,
        "mutual_fund_holders": mf_holders,
        "total_institutional_pct": round(total_pct, 2),
    }


@tool
def get_earnings_calendar(ticker: str, exchange: str) -> dict:
    """Get earnings calendar: next earnings date and last 4 quarters history with surprise %.
    Useful for timing trades around earnings events."""
    ex = ExchangeEnum(exchange.upper())
    yf_ticker = normalize_ticker(ticker, ex)
    stock = yf.Ticker(yf_ticker)

    try:
        earnings_df = stock.earnings_dates
    except Exception:
        earnings_df = None

    if earnings_df is None or (isinstance(earnings_df, pd.DataFrame) and earnings_df.empty):
        return {"ticker": get_display_ticker(ticker), "message": "No earnings calendar data available"}

    now = pd.Timestamp.now()

    future_dates = earnings_df.index[earnings_df.index > now]
    next_earnings = future_dates.min().strftime("%Y-%m-%d") if len(future_dates) > 0 else None

    past = earnings_df[earnings_df.index <= now].head(4)
    history = []
    for date, row in past.iterrows():
        estimate = float(row["EPS Estimate"]) if pd.notna(row.get("EPS Estimate")) else None
        actual = float(row["Reported EPS"]) if pd.notna(row.get("Reported EPS")) else None
        surprise = float(row["Surprise(%)"]) if pd.notna(row.get("Surprise(%)")) else None
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "eps_estimate": estimate,
            "eps_actual": actual,
            "surprise_pct": surprise,
        })

    surprises = [h["surprise_pct"] for h in history if h["surprise_pct"] is not None]
    avg_surprise = round(sum(surprises) / len(surprises), 2) if surprises else None

    return {
        "ticker": get_display_ticker(ticker),
        "exchange": exchange,
        "next_earnings_date": next_earnings,
        "earnings_history": history,
        "avg_surprise_pct": avg_surprise,
        "beat_rate": f"{sum(1 for s in surprises if s > 0)}/{len(surprises)}" if surprises else None,
    }
