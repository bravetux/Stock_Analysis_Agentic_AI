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

"""
100 search query templates for comprehensive stock news intelligence.
Organized into 10 categories of 10 queries each.
"""

from datetime import datetime
from src.config.exchanges import ExchangeEnum
from src.config.news_sources import get_location_query_templates


# ---------------------------------------------------------------------------
# Category 1: Earnings & Financials (1-15)
# ---------------------------------------------------------------------------
EARNINGS_QUERIES = [
    "{company} quarterly results {year}",
    "{company} annual report {year}",
    "{company} revenue growth",
    "{company} profit margin analysis",
    "{company} earnings per share EPS",
    "{company} balance sheet analysis",
    "{company} cash flow statement",
    "{company} debt to equity ratio",
    "{company} return on equity ROE",
    "{company} operating income trend",
    "{company} EBITDA analysis",
    "{company} quarterly earnings surprise",
    "{company} revenue forecast",
    "{company} earnings call transcript",
    "{company} financial health assessment",
]

# ---------------------------------------------------------------------------
# Category 2: Analyst & Ratings (16-25)
# ---------------------------------------------------------------------------
ANALYST_QUERIES = [
    "{stock} analyst rating",
    "{stock} target price",
    "{stock} buy sell recommendation",
    "{stock} broker research report",
    "{stock} consensus estimate",
    "{stock} analyst upgrade downgrade",
    "{stock} price forecast {year}",
    "{stock} investment thesis",
    "{stock} valuation analysis",
    "{stock} fair value estimate",
]

# ---------------------------------------------------------------------------
# Category 3: Insider & Institutional (26-35)
# ---------------------------------------------------------------------------
INSIDER_QUERIES = [
    "{company} insider trading activity",
    "{company} promoter holding change",
    "{company} institutional investor holding",
    "{company} mutual fund holding",
    "{company} FII DII activity",
    "{company} bulk deal block deal",
    "{company} share buyback",
    "{company} promoter pledge",
    "{company} ESOP employee stock",
    "{company} stake sale acquisition",
]

# ---------------------------------------------------------------------------
# Category 4: Dividends & Corporate Actions (36-45)
# ---------------------------------------------------------------------------
DIVIDEND_QUERIES = [
    "{company} dividend history",
    "{company} dividend yield",
    "{company} stock split bonus",
    "{company} rights issue",
    "{company} merger acquisition news",
    "{company} demerger spin off",
    "{company} delisting news",
    "{company} IPO review listing",
    "{company} QIP FPO fundraising",
    "{company} corporate action upcoming",
]

# ---------------------------------------------------------------------------
# Category 5: Management & Governance (46-55)
# ---------------------------------------------------------------------------
MANAGEMENT_QUERIES = [
    "{company} management changes CEO",
    "{company} board of directors update",
    "{company} corporate governance rating",
    "{company} management commentary outlook",
    "{company} AGM annual general meeting",
    "{company} related party transactions",
    "{company} audit report observations",
    "{company} management interview",
    "{company} succession planning",
    "{company} whistleblower complaints",
]

# ---------------------------------------------------------------------------
# Category 6: Sector & Competition (56-65)
# ---------------------------------------------------------------------------
SECTOR_QUERIES = [
    "{company} competition analysis",
    "{company} market share industry",
    "{company} sector outlook",
    "{company} peer comparison",
    "{company} industry trends",
    "{company} competitive advantage moat",
    "{company} industry headwinds tailwinds",
    "{company} new product launch",
    "{company} expansion plans",
    "{company} order book pipeline",
]

# ---------------------------------------------------------------------------
# Category 7: Technical & Price (66-75)
# ---------------------------------------------------------------------------
TECHNICAL_QUERIES = [
    "{stock} technical analysis today",
    "{stock} support resistance levels",
    "{stock} moving average crossover",
    "{stock} breakout pattern",
    "{stock} chart pattern",
    "{stock} volume analysis unusual",
    "{stock} 52 week high low",
    "{stock} options chain open interest",
    "{stock} short selling data",
    "{stock} delivery percentage",
]

# ---------------------------------------------------------------------------
# Category 8: Macro & Regulatory (76-85)
# ---------------------------------------------------------------------------
MACRO_QUERIES_INDIA = [
    "{company} RBI SEBI regulatory",
    "{company} government policy impact India",
    "{company} GST tax impact",
    "{company} import export tariff India",
    "{company} forex rupee impact",
    "{company} interest rate sensitivity India",
    "{company} inflation impact India",
    "{company} geopolitical risk exposure",
    "{company} ESG sustainability rating",
    "{company} regulatory approval India",
]

MACRO_QUERIES_US = [
    "{company} SEC FDA regulatory",
    "{company} government policy impact US",
    "{company} tax reform impact",
    "{company} import export tariff US",
    "{company} forex dollar impact",
    "{company} interest rate sensitivity Fed",
    "{company} inflation impact US",
    "{company} geopolitical risk exposure",
    "{company} ESG sustainability rating",
    "{company} regulatory approval US",
]

# ---------------------------------------------------------------------------
# Category 9: Sentiment & Social (86-95)
# ---------------------------------------------------------------------------
SENTIMENT_QUERIES = [
    "{stock} social media sentiment",
    "{company} customer reviews satisfaction",
    "{company} employee reviews glassdoor",
    "{stock} retail investor sentiment",
    "{company} brand perception",
    "{company} controversy scandal news",
    "{company} lawsuit legal proceedings",
    "{company} credit rating change",
    "{company} supply chain disruption",
    "{company} cybersecurity data breach",
]

# ---------------------------------------------------------------------------
# Category 10: Location-Specific News Sources (96-100)
# Loaded dynamically from news_sources.yaml
# ---------------------------------------------------------------------------


def generate_search_queries(
    stock_name: str,
    company_name: str,
    exchange: ExchangeEnum,
) -> list[str]:
    """
    Generate up to 100 search queries for a stock.

    Args:
        stock_name: Ticker symbol (e.g., "RELIANCE", "AAPL")
        company_name: Full company name (e.g., "Reliance Industries")
        exchange: The exchange enum

    Returns:
        List of formatted search query strings.
    """
    year = str(datetime.now().year)
    is_india = exchange in (ExchangeEnum.NSE, ExchangeEnum.BSE)

    macro_queries = MACRO_QUERIES_INDIA if is_india else MACRO_QUERIES_US
    region = "india" if is_india else "us"
    location_queries = get_location_query_templates(region, limit=5)

    all_templates = (
        EARNINGS_QUERIES
        + ANALYST_QUERIES
        + INSIDER_QUERIES
        + DIVIDEND_QUERIES
        + MANAGEMENT_QUERIES
        + SECTOR_QUERIES
        + TECHNICAL_QUERIES
        + macro_queries
        + SENTIMENT_QUERIES
        + location_queries
    )

    queries = []
    for template in all_templates:
        query = template.format(
            company=company_name,
            stock=stock_name,
            year=year,
        )
        queries.append(query)

    return queries
