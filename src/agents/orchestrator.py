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

import concurrent.futures
import logging
import pathlib
import time
from typing import Callable
from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.hooks import BeforeToolCallEvent, AfterToolCallEvent
from strands_tools.handoff_to_user import handoff_to_user
from strands_tools.think import think
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from src.config.analysis_profiles import PROFILES, DEFAULT_PROFILE, TOOL_GROUPS
from src.agents.technical_agent import create_technical_agent
from src.agents.news_agent import create_news_agent
from src.agents.fundamental_agent import create_fundamental_agent
from src.agents.market_data_agent import create_market_data_agent
from src.agents.web_scraping_agent import create_web_scraping_agent
from src.tools.market_data_tools import (
    detect_exchange_for_ticker,
    get_stock_quote,
    get_historical_data,
    get_market_overview,
)
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_macd,
    calculate_support_resistance,
    estimate_next_high_low,
    get_technical_summary,
    calculate_ema_crossovers,
    detect_golden_death_cross,
    calculate_fibonacci_levels,
    calculate_vwap,
    calculate_obv,
    calculate_ichimoku,
    calculate_williams_r,
    calculate_adx_directional,
    calculate_trend_strength,
    detect_chart_patterns,
    calculate_risk_metrics,
    calculate_relative_strength,
)
from src.tools.news_tools import (
    search_google_news,
    search_news_batch,
    extract_article_content,
    search_location_news,
)
from src.tools.scraping_tools import (
    scrape_google_finance,
    scrape_yahoo_finance_page,
    scrape_moneycontrol,
)
from src.tools.screener_tools import scrape_screener_in
from src.tools.chartink_tools import scrape_chartink_screener, get_chartink_stock_data
from src.tools.batch_tools import read_stocks_file
from src.tools.fundamental_tools import (
    get_insider_transactions,
    get_mutual_fund_holdings,
    get_earnings_calendar,
)
from src.tools.news_tools import get_google_trends
from src.tools.market_data_tools import get_options_chain, get_sector_performance
from src.tools.scraping_tools import scrape_trendlyne, scrape_tickertape
from src.tools.scoring_tools import calculate_composite_score

logger = logging.getLogger(__name__)

_DEFAULT_SESSION_ID = "orchestrator-default"


def get_session_manager(session_id: str = _DEFAULT_SESSION_ID):
    """Returns the appropriate session manager based on SESSION_BACKEND env var."""
    try:
        from strands.session.file_session_manager import FileSessionManager
        pathlib.Path(settings.session_dir).mkdir(parents=True, exist_ok=True)
        return FileSessionManager(session_id=session_id, storage_dir=settings.session_dir)
    except (ImportError, Exception) as e:
        logger.warning("FileSessionManager not available (%s), using no session manager", e)
        return None


def run_parallel_analysis(ticker: str, exchange: str) -> dict:
    """
    Runs all 5 specialist sub-agents in parallel threads.
    Returns dict with keys: technical, news, fundamental, market_data, web_scraping.
    """
    technical_agent = create_technical_agent()
    news_agent = create_news_agent()
    fundamental_agent = create_fundamental_agent()
    market_data_agent = create_market_data_agent()
    web_scraping_agent = create_web_scraping_agent()

    query = f"Analyze {ticker} on {exchange} exchange. Provide a comprehensive analysis."

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            "technical": executor.submit(technical_agent, query),
            "news": executor.submit(news_agent, query),
            "fundamental": executor.submit(fundamental_agent, query),
            "market_data": executor.submit(market_data_agent, query),
            "web_scraping": executor.submit(web_scraping_agent, query),
        }
        results = {}
        for key, future in futures.items():
            try:
                results[key] = str(future.result(timeout=180))
            except Exception as e:
                logger.error("Sub-agent %s failed for %s: %s", key, ticker, e)
                results[key] = f"Error: {e}"

    return results


def create_orchestrator(
    session_id: str | None = None,
    profile: str = DEFAULT_PROFILE,
    on_tool_start: Callable[[str], None] | None = None,
    on_tool_end: Callable[[str, float], None] | None = None,
) -> Agent:
    """
    Creates the Orchestrator Agent with tools filtered by the selected
    analysis profile, session persistence, conversation summarisation,
    and audit hooks.

    Args:
        on_tool_start: Optional callback(tool_name) called when a tool begins.
        on_tool_end: Optional callback(tool_name, elapsed_seconds) called when a tool finishes.
    """
    effective_session_id = session_id or _DEFAULT_SESSION_ID
    active_profile = PROFILES.get(profile, PROFILES[DEFAULT_PROFILE])

    model = BedrockModel(
        boto_session=get_bedrock_session(),
        model_id=settings.bedrock_model_id,
        temperature=settings.agent_temperature,
        top_p=settings.agent_top_p,
        max_tokens=settings.agent_max_tokens,
    )

    conversation_manager = SummarizingConversationManager(
        summary_ratio=0.4,
        summarization_system_prompt=(
            "Summarise stock analysis findings and data collected. "
            "Preserve: ticker names, prices, indicator values, signals, key headlines. "
            "Discard: raw HTML, intermediate scraping output, duplicate news items."
        ),
    )

    # All available tools, keyed by function name
    all_tools = {
        "think": think,
        "handoff_to_user": handoff_to_user,
        "detect_exchange_for_ticker": detect_exchange_for_ticker,
        "get_stock_quote": get_stock_quote,
        "get_historical_data": get_historical_data,
        "get_market_overview": get_market_overview,
        "calculate_200dma": calculate_200dma,
        "calculate_macd": calculate_macd,
        "calculate_support_resistance": calculate_support_resistance,
        "estimate_next_high_low": estimate_next_high_low,
        "get_technical_summary": get_technical_summary,
        "search_google_news": search_google_news,
        "search_news_batch": search_news_batch,
        "extract_article_content": extract_article_content,
        "search_location_news": search_location_news,
        "scrape_google_finance": scrape_google_finance,
        "scrape_yahoo_finance_page": scrape_yahoo_finance_page,
        "scrape_moneycontrol": scrape_moneycontrol,
        "scrape_screener_in": scrape_screener_in,
        "scrape_chartink_screener": scrape_chartink_screener,
        "get_chartink_stock_data": get_chartink_stock_data,
        "read_stocks_file": read_stocks_file,
        "calculate_ema_crossovers": calculate_ema_crossovers,
        "detect_golden_death_cross": detect_golden_death_cross,
        "calculate_fibonacci_levels": calculate_fibonacci_levels,
        "calculate_vwap": calculate_vwap,
        "calculate_obv": calculate_obv,
        "calculate_ichimoku": calculate_ichimoku,
        "calculate_williams_r": calculate_williams_r,
        "calculate_adx_directional": calculate_adx_directional,
        "calculate_trend_strength": calculate_trend_strength,
        "detect_chart_patterns": detect_chart_patterns,
        "calculate_risk_metrics": calculate_risk_metrics,
        "calculate_relative_strength": calculate_relative_strength,
        "get_insider_transactions": get_insider_transactions,
        "get_mutual_fund_holdings": get_mutual_fund_holdings,
        "get_earnings_calendar": get_earnings_calendar,
        "get_google_trends": get_google_trends,
        "get_options_chain": get_options_chain,
        "get_sector_performance": get_sector_performance,
        "scrape_trendlyne": scrape_trendlyne,
        "scrape_tickertape": scrape_tickertape,
        "calculate_composite_score": calculate_composite_score,
    }

    # Filter tools based on the profile's enabled tool groups
    enabled_tool_names: set[str] = set()
    for group in active_profile.tool_groups:
        enabled_tool_names.update(TOOL_GROUPS.get(group, []))

    tools = [fn for name, fn in all_tools.items() if name in enabled_tool_names]

    agent_kwargs: dict = {
        "model": model,
        "tools": tools,
        "conversation_manager": conversation_manager,
        "system_prompt": ORCHESTRATOR_SYSTEM_PROMPT,
    }

    session_manager = get_session_manager(effective_session_id)
    if session_manager is not None:
        agent_kwargs["session_manager"] = session_manager

    agent = Agent(**agent_kwargs)

    # Audit hooks with progress tracking
    _tool_start_times: dict[str, float] = {}

    def _get_tool_name(tool_use) -> str:
        if tool_use is None:
            return "unknown"
        if isinstance(tool_use, dict):
            return tool_use.get("name", "unknown")
        return getattr(tool_use, "name", "unknown")

    def _before_tool(event: BeforeToolCallEvent) -> None:
        tool_name = _get_tool_name(event.tool_use)
        _tool_start_times[tool_name] = time.time()
        logger.info("TOOL_CALL_START tool=%s", tool_name)
        if on_tool_start:
            on_tool_start(tool_name)

    def _after_tool(event: AfterToolCallEvent) -> None:
        tool_name = _get_tool_name(event.tool_use)
        elapsed = time.time() - _tool_start_times.pop(tool_name, time.time())
        logger.info("TOOL_CALL_END tool=%s elapsed=%.2fs", tool_name, elapsed)
        if on_tool_end:
            on_tool_end(tool_name, elapsed)

    try:
        agent.add_hook(_before_tool, BeforeToolCallEvent)
        agent.add_hook(_after_tool, AfterToolCallEvent)
    except (AttributeError, TypeError) as e:
        logger.warning("Hooks could not be registered: %s", e)

    return agent
