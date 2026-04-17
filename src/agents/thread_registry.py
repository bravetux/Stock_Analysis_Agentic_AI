# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Maps thread_id -> toolset for investigators.

The planner chooses a thread_id; this registry decides which tools are in
that investigator's sandbox. Keeping it in one file makes it trivial to see
who has access to what, and to prune/extend without digging into agent code.
"""

from __future__ import annotations

from typing import Callable

from src.tools.chartink_tools import get_chartink_stock_data, scrape_chartink_screener
from src.tools.fundamental_tools import (
    get_earnings_calendar,
    get_insider_transactions,
    get_mutual_fund_holdings,
)
from src.tools.market_data_tools import (
    detect_exchange_for_ticker,
    get_historical_data,
    get_market_overview,
    get_options_chain,
    get_sector_performance,
    get_stock_quote,
)
from src.tools.news_tools import (
    extract_article_content,
    get_google_trends,
    search_google_news,
    search_location_news,
    search_news_batch,
)
from src.tools.scraping_tools import (
    scrape_google_finance,
    scrape_moneycontrol,
    scrape_tickertape,
    scrape_trendlyne,
    scrape_yahoo_finance_page,
)
from src.tools.screener_tools import scrape_screener_in
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_adx_directional,
    calculate_ema_crossovers,
    calculate_fibonacci_levels,
    calculate_ichimoku,
    calculate_macd,
    calculate_obv,
    calculate_relative_strength,
    calculate_risk_metrics,
    calculate_support_resistance,
    calculate_trend_strength,
    calculate_vwap,
    calculate_williams_r,
    detect_chart_patterns,
    detect_golden_death_cross,
    estimate_next_high_low,
    get_technical_summary,
)

# Each value is a plain list of @tool-decorated callables.
THREAD_TOOLS: dict[str, list[Callable]] = {
    "technical": [
        get_stock_quote,
        get_historical_data,
        calculate_200dma,
        calculate_macd,
        calculate_ema_crossovers,
        detect_golden_death_cross,
        calculate_support_resistance,
        calculate_fibonacci_levels,
        calculate_vwap,
        calculate_obv,
        calculate_ichimoku,
        calculate_williams_r,
        calculate_adx_directional,
        calculate_trend_strength,
        detect_chart_patterns,
        estimate_next_high_low,
        get_technical_summary,
    ],
    "fundamental": [
        get_stock_quote,
        get_historical_data,
        scrape_screener_in,
        scrape_moneycontrol,
        scrape_tickertape,
        scrape_yahoo_finance_page,
        get_earnings_calendar,
    ],
    "news": [
        search_news_batch,
        search_google_news,
        search_location_news,
        get_google_trends,
        extract_article_content,
    ],
    "institutional": [
        get_insider_transactions,
        get_mutual_fund_holdings,
        scrape_screener_in,  # shareholding pattern section (Indian stocks)
        scrape_moneycontrol,
        search_news_batch,  # for FII/DII flow news
    ],
    "macro_sector": [
        get_market_overview,
        get_sector_performance,
        calculate_relative_strength,
        scrape_chartink_screener,
        get_chartink_stock_data,
    ],
    "risk_options": [
        get_historical_data,
        calculate_risk_metrics,
        get_options_chain,
        scrape_trendlyne,
    ],
}


ALLOWED_THREAD_IDS = frozenset(THREAD_TOOLS.keys())


def get_tools_for_thread(thread_id: str) -> list[Callable]:
    return THREAD_TOOLS.get(thread_id, [])
