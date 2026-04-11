# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

"""
Analysis profiles that control which features are included based on user expertise.

Each profile defines:
- label: Display name for the UI
- description: What the user can expect
- tools: Which tool groups to enable
- news_queries: Max number of news search queries
- prompt_sections: What to request in the analysis prompt
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalysisProfile:
    label: str
    description: str
    tool_groups: tuple[str, ...]
    news_queries: int
    prompt_instructions: str


# Tool group definitions — maps group name to the tool function names it includes
TOOL_GROUPS: dict[str, list[str]] = {
    "core": ["think", "handoff_to_user", "detect_exchange_for_ticker", "get_stock_quote"],
    "market_data": ["get_historical_data", "get_market_overview"],
    "technical_basic": ["calculate_200dma"],
    "technical_momentum": ["calculate_macd"],
    "technical_levels": ["calculate_support_resistance", "estimate_next_high_low"],
    "technical_dashboard": ["get_technical_summary"],
    "news_basic": ["search_google_news"],
    "news_batch": ["search_news_batch", "extract_article_content"],
    "news_location": ["search_location_news"],
    "fundamentals": ["scrape_screener_in"],
    "scraping_basic": ["scrape_google_finance"],
    "scraping_advanced": ["scrape_yahoo_finance_page", "scrape_moneycontrol"],
    "scraping_chartink": ["scrape_chartink_screener", "get_chartink_stock_data"],
    "batch": ["read_stocks_file"],
    "technical_ema": ["calculate_ema_crossovers", "detect_golden_death_cross"],
    "technical_fibonacci": ["calculate_fibonacci_levels", "calculate_vwap", "calculate_obv"],
    "technical_advanced": ["calculate_ichimoku", "calculate_williams_r", "calculate_adx_directional"],
    "technical_analysis": ["calculate_trend_strength", "detect_chart_patterns", "calculate_risk_metrics", "calculate_relative_strength"],
    "market_options": ["get_options_chain", "get_sector_performance"],
    "fundamentals_advanced": ["get_insider_transactions", "get_mutual_fund_holdings", "get_earnings_calendar"],
    "news_trends": ["get_google_trends"],
    "scraping_india_advanced": ["scrape_trendlyne", "scrape_tickertape"],
    "scoring": ["calculate_composite_score"],
}

PROFILES: dict[str, AnalysisProfile] = {
    "beginner": AnalysisProfile(
        label="Beginner",
        description=(
            "Simple overview: current price, 200-day moving average trend, "
            "and top news headlines. Best for those new to stock analysis."
        ),
        tool_groups=(
            "core", "market_data", "technical_basic",
            "news_basic", "scraping_basic", "batch",
            "scoring",
        ),
        news_queries=10,
        prompt_instructions=(
            "Provide a BEGINNER-FRIENDLY analysis. Keep language simple, avoid jargon.\n"
            "Include only:\n"
            "- Current price and basic market data (price, volume, 52-week range)\n"
            "- 200-Day Moving Average: is the stock above or below? Explain what this means simply\n"
            "- Top 5 recent news headlines with a one-line sentiment summary\n"
            "- A simple verdict: is the stock trending UP, DOWN, or SIDEWAYS?\n"
            "- Composite Score: show the overall score (0-100) and signal (BUY/HOLD/SELL)\n"
            "Do NOT include MACD, RSI, support/resistance, fundamentals, or advanced metrics."
        ),
    ),
    "novice": AnalysisProfile(
        label="Novice",
        description=(
            "Core analysis: price data, 200DMA trend, MACD momentum signals, "
            "news sentiment, and key fundamental ratios. Good starting point for most users."
        ),
        tool_groups=(
            "core", "market_data", "technical_basic", "technical_momentum",
            "technical_ema",
            "news_basic", "news_batch", "fundamentals",
            "scraping_basic", "batch",
            "scoring",
        ),
        news_queries=25,
        prompt_instructions=(
            "Provide a NOVICE-LEVEL analysis with clear explanations.\n"
            "Include:\n"
            "- Score Dashboard: composite score with sub-scores\n"
            "- Market Data: current price, volume, 52-week range, market cap\n"
            "- 200DMA Analysis: trend direction, recent breakpoints, what they signal\n"
            "- MACD Signals: current crossover status, momentum direction\n"
            "- EMA Crossovers: 9/21/50 alignment and signals\n"
            "- News Sentiment: overall sentiment (positive/negative/neutral %), top 5 headlines\n"
            "- Key Fundamentals: PE ratio, ROE, debt-to-equity (with brief explanations)\n"
            "- Risk Assessment: basic risk metrics\n"
            "- Overall Assessment: composite score signal with simple reasoning\n"
            "Briefly explain technical terms when first used."
        ),
    ),
    "intermediate": AnalysisProfile(
        label="Intermediate",
        description=(
            "Detailed analysis: full technical indicators (200DMA, MACD, support/resistance, "
            "price estimates), comprehensive news, detailed fundamentals, and multi-source scraping."
        ),
        tool_groups=(
            "core", "market_data",
            "technical_basic", "technical_momentum", "technical_levels",
            "technical_ema", "technical_fibonacci",
            "news_basic", "news_batch", "news_location",
            "fundamentals", "fundamentals_advanced",
            "scraping_basic", "scraping_advanced", "scraping_chartink",
            "scraping_india_advanced",
            "batch", "scoring",
        ),
        news_queries=50,
        prompt_instructions=(
            "Provide an INTERMEDIATE-LEVEL analysis with detailed data.\n"
            "Include:\n"
            "- Score Dashboard: composite score, sub-scores, confidence level\n"
            "- Key Levels: support/resistance + Fibonacci levels consolidated\n"
            "- Bull/Bear Scenarios: price targets with reasoning\n"
            "- Technical Analysis:\n"
            "  - 200DMA, MACD, EMA crossovers, Golden/Death Cross\n"
            "  - Fibonacci levels, VWAP, support/resistance\n"
            "  - Price Estimates: ATR-based and Bollinger targets\n"
            "- News Intelligence: sentiment breakdown, top 10 headlines, risk/catalyst alerts\n"
            "- Fundamental Analysis: PE, PB, ROE, ROCE, growth rates, debt ratios,\n"
            "  insider activity, mutual fund holdings, earnings calendar\n"
            "- Web Data: Google Finance, MoneyControl, Chartink, Trendlyne, Tickertape\n"
            "- Overall Assessment: composite score signal with multi-factor reasoning"
        ),
    ),
    "expert": AnalysisProfile(
        label="Expert",
        description=(
            "Full comprehensive analysis: all technical indicators including RSI/ADX/Stochastic "
            "dashboard, 100 news query types, all fundamental metrics, all scraping sources, "
            "and Chartink screener scans."
        ),
        tool_groups=tuple(TOOL_GROUPS.keys()),  # everything
        news_queries=100,
        prompt_instructions=(
            "Provide a FULL EXPERT-LEVEL comprehensive analysis. No simplification needed.\n"
            "Include ALL available data:\n"
            "- Score Dashboard: composite score, all sub-scores with components, confidence, risk level\n"
            "- Key Levels Table: support/resistance + Fibonacci + VWAP in one table\n"
            "- Bull/Bear Scenarios: price targets with catalysts and risks\n"
            "- Technical Analysis (ALL indicators):\n"
            "  - 200DMA with breakpoint history and trend analysis\n"
            "  - MACD with full crossover history and histogram analysis\n"
            "  - EMA crossovers (9/21/50) and alignment status\n"
            "  - Golden/Death Cross detection\n"
            "  - Fibonacci retracement levels\n"
            "  - VWAP analysis, OBV accumulation/distribution\n"
            "  - Ichimoku Cloud, Williams %%R\n"
            "  - ADX with directional movement (+DI/-DI)\n"
            "  - Trend strength composite, chart pattern detection\n"
            "  - Support & Resistance levels, Price Estimates\n"
            "  - Technical Dashboard: RSI, Stochastic, volume analysis\n"
            "- Risk Assessment: Sharpe ratio, max drawdown, beta, VaR, volatility\n"
            "- Relative Strength vs market and sector\n"
            "- News Intelligence (use all 100 query types):\n"
            "  - Sentiment analysis, Google Trends momentum\n"
            "  - Top headlines across all categories\n"
            "  - Location-specific news, risk/catalyst alerts\n"
            "- Fundamental Analysis (full depth):\n"
            "  - Valuation, profitability, growth, balance sheet\n"
            "  - Shareholding, quarterly results, insider transactions\n"
            "  - Mutual fund holdings, earnings calendar with surprise history\n"
            "- Options Data: put/call ratio, max pain, implied volatility\n"
            "- Peer/Sector Comparison: relative performance\n"
            "- Web Scraping: all sources including Trendlyne, Tickertape\n"
            "- Overall Assessment: STRONG BUY / BUY / HOLD / SELL / STRONG SELL\n"
            "  - Multi-factor convergence analysis\n"
            "  - Key risks and catalysts\n"
            "  - Suggested entry/exit levels"
        ),
    ),
}

PROFILE_ORDER = ["beginner", "novice", "intermediate", "expert"]
DEFAULT_PROFILE = "novice"
