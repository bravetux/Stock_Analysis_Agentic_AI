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
        ),
        news_queries=10,
        prompt_instructions=(
            "Provide a BEGINNER-FRIENDLY analysis. Keep language simple, avoid jargon.\n"
            "Include only:\n"
            "- Current price and basic market data (price, volume, 52-week range)\n"
            "- 200-Day Moving Average: is the stock above or below? Explain what this means simply\n"
            "- Top 5 recent news headlines with a one-line sentiment summary\n"
            "- A simple verdict: is the stock trending UP, DOWN, or SIDEWAYS?\n"
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
            "news_basic", "news_batch", "fundamentals",
            "scraping_basic", "batch",
        ),
        news_queries=25,
        prompt_instructions=(
            "Provide a NOVICE-LEVEL analysis with clear explanations.\n"
            "Include:\n"
            "- Market Data: current price, volume, 52-week range, market cap\n"
            "- 200DMA Analysis: trend direction, recent breakpoints, what they signal\n"
            "- MACD Signals: current crossover status, momentum direction\n"
            "- News Sentiment: overall sentiment (positive/negative/neutral %), top 5 headlines\n"
            "- Key Fundamentals: PE ratio, ROE, debt-to-equity (with brief explanations of each)\n"
            "- Overall Assessment: BUY / HOLD / SELL with simple reasoning\n"
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
            "news_basic", "news_batch", "news_location",
            "fundamentals",
            "scraping_basic", "scraping_advanced", "scraping_chartink",
            "batch",
        ),
        news_queries=50,
        prompt_instructions=(
            "Provide an INTERMEDIATE-LEVEL analysis with detailed data.\n"
            "Include:\n"
            "- Market Data: full quote with price, volume, market cap, 52-week context\n"
            "- Technical Analysis:\n"
            "  - 200DMA: breakpoints, trend direction, distance from DMA\n"
            "  - MACD: signal line crossovers, histogram trend, recent crossover dates\n"
            "  - Support & Resistance: pivot levels, key price zones\n"
            "  - Price Estimates: short-term (ATR-based) and medium-term (Bollinger) targets\n"
            "- News Intelligence: sentiment breakdown, top 10 headlines, risk/catalyst alerts\n"
            "- Fundamental Analysis: PE, PB, ROE, ROCE, growth rates, debt ratios, "
            "shareholding pattern\n"
            "- Web Data: cross-reference from Google Finance, MoneyControl, Chartink scans\n"
            "- Overall Assessment: STRONG BUY / BUY / HOLD / SELL / STRONG SELL with reasoning"
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
            "- Market Data: full quote, historical context, market index comparison\n"
            "- Technical Analysis (ALL indicators):\n"
            "  - 200DMA with breakpoint history and trend analysis\n"
            "  - MACD with full crossover history and histogram analysis\n"
            "  - Support & Resistance levels (pivot points + local extremes)\n"
            "  - Price Estimates (ATR short-term + Bollinger medium-term)\n"
            "  - Technical Dashboard: RSI, Stochastic K/D, ADX trend strength, volume analysis\n"
            "- News Intelligence (use all 100 query types):\n"
            "  - Full sentiment analysis with source breakdown\n"
            "  - Top headlines across all 10 categories\n"
            "  - Location-specific news sources\n"
            "  - Risk alerts, catalyst alerts, insider activity mentions\n"
            "- Fundamental Analysis (full depth):\n"
            "  - Valuation: PE, PB, EV/EBITDA\n"
            "  - Profitability: ROE, ROCE, margins\n"
            "  - Growth: revenue and profit growth trends\n"
            "  - Balance Sheet: debt-to-equity, current ratio\n"
            "  - Shareholding: promoter, FII, DII changes\n"
            "  - Quarterly results trends\n"
            "- Web Scraping (all sources): Google Finance, Yahoo Finance, MoneyControl, "
            "Chartink screener scans (200DMA breakout, MACD crossover, volume breakout)\n"
            "- Overall Assessment: STRONG BUY / BUY / HOLD / SELL / STRONG SELL\n"
            "  - Multi-factor convergence analysis\n"
            "  - Key risks and catalysts\n"
            "  - Suggested entry/exit levels"
        ),
    ),
}

PROFILE_ORDER = ["beginner", "novice", "intermediate", "expert"]
DEFAULT_PROFILE = "novice"
