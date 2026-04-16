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
import time
import pandas as pd
from pytrends.request import TrendReq
from strands import tool
from src.config.exchanges import ExchangeEnum, get_location
from src.config.search_queries import generate_search_queries
from src.config.settings import settings
from src.config.news_sources import get_location_search_sources

logger = logging.getLogger(__name__)


@tool
def search_google_news(query: str, period: str = "1m") -> list:
    """Search Google News for a query. Period: 1d, 1w, 1m.
    Returns list of {title, date, source, link, description}."""
    from GoogleNews import GoogleNews

    gn = GoogleNews(lang="en", period=period)
    gn.clear()
    gn.search(query)
    results = gn.results()

    articles = []
    for item in results:
        articles.append({
            "title": item.get("title", ""),
            "date": item.get("date", ""),
            "source": item.get("media", ""),
            "link": item.get("link", ""),
            "description": item.get("desc", ""),
        })

    gn.clear()
    return articles


@tool
def search_news_batch(
    ticker: str,
    company_name: str,
    exchange: str,
    max_queries: int = 100,
) -> dict:
    """Execute up to 100 different news search queries for comprehensive stock coverage.
    Searches in batches of 10 with rate limiting. Deduplicates results by URL."""
    ex = ExchangeEnum(exchange.upper())
    queries = generate_search_queries(ticker, company_name, ex)
    queries = queries[:max_queries]

    from GoogleNews import GoogleNews
    gn = GoogleNews(lang="en", period="1m")

    all_articles = []
    seen_urls = set()
    batch_size = 10

    for i in range(0, len(queries), batch_size):
        batch = queries[i : i + batch_size]
        for query in batch:
            try:
                gn.clear()
                gn.search(query)
                for item in gn.results():
                    url = item.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append({
                            "title": item.get("title", ""),
                            "date": item.get("date", ""),
                            "source": item.get("media", ""),
                            "link": url,
                            "description": item.get("desc", ""),
                            "query_category": _get_query_category(i + batch.index(query)),
                        })
            except Exception as e:
                logger.warning("News search failed for query '%s': %s", query, e)

            time.sleep(settings.news_api_delay)

        # Longer pause between batches
        time.sleep(settings.scrape_delay_seconds)

    gn.clear()
    return {
        "ticker": ticker,
        "company_name": company_name,
        "exchange": exchange,
        "queries_executed": min(len(queries), max_queries),
        "total_articles": len(all_articles),
        "unique_sources": len(set(a["source"] for a in all_articles if a["source"])),
        "articles": all_articles,
    }


@tool
def extract_article_content(url: str) -> dict:
    """Extract full article text from a news URL using newspaper3k."""
    from newspaper import Article

    try:
        article = Article(url)
        article.download()
        article.parse()
        return {
            "title": article.title,
            "text": article.text[:5000],  # Limit to 5000 chars
            "authors": article.authors,
            "publish_date": str(article.publish_date) if article.publish_date else None,
            "top_image": article.top_image,
            "url": url,
        }
    except Exception as e:
        return {"error": str(e), "url": url}


@tool
def search_location_news(ticker: str, exchange: str) -> dict:
    """Search leading news websites based on stock's exchange location.
    Sources are loaded from news_sources.yaml — edit that file to add/remove sites."""
    ex = ExchangeEnum(exchange.upper())
    location = get_location(ex)
    region = "india" if location == "India" else "us"

    source_defs = get_location_search_sources(region)
    sources = [
        {"name": s["name"], "query": s["query_template"].format(ticker=ticker)}
        for s in source_defs
    ]

    from GoogleNews import GoogleNews
    gn = GoogleNews(lang="en", period="1m")
    all_results = []

    for source in sources:
        try:
            gn.clear()
            gn.search(source["query"])
            results = gn.results()
            for item in results[:5]:  # Top 5 per source
                all_results.append({
                    "title": item.get("title", ""),
                    "date": item.get("date", ""),
                    "source_name": source["name"],
                    "media": item.get("media", ""),
                    "link": item.get("link", ""),
                    "description": item.get("desc", ""),
                })
        except Exception as e:
            logger.warning("Location news search failed for %s: %s", source["name"], e)
        time.sleep(settings.news_api_delay)

    gn.clear()
    return {
        "ticker": ticker,
        "location": location,
        "sources_searched": len(sources),
        "total_articles": len(all_results),
        "articles": all_results,
    }


@tool
def get_google_trends(ticker: str, company_name: str) -> dict:
    """Get Google Trends search interest for a stock/company over 90 days.
    Returns trend direction, current vs average interest, and rising related queries."""
    try:
        pytrends = TrendReq(hl="en-US", tz=330)
        kw = company_name if company_name else ticker
        pytrends.build_payload([kw], timeframe=settings.trends_timeframe)

        interest_df = pytrends.interest_over_time()
        if interest_df.empty:
            return {"ticker": ticker, "message": "No Google Trends data available"}

        values = interest_df[kw].tolist()
        current = values[-1]
        avg = sum(values) / len(values)

        third = max(1, len(values) // 3)
        first_avg = sum(values[:third]) / third
        last_avg = sum(values[-third:]) / third

        if last_avg > first_avg * 1.15:
            trend = "RISING"
        elif last_avg < first_avg * 0.85:
            trend = "FALLING"
        else:
            trend = "STABLE"

        related = pytrends.related_queries()
        rising_queries = []
        if kw in related and related[kw].get("rising") is not None:
            rising_df = related[kw]["rising"]
            if isinstance(rising_df, pd.DataFrame) and not rising_df.empty:
                rising_queries = rising_df.head(5)["query"].tolist()

        return {
            "ticker": ticker,
            "keyword": kw,
            "current_interest": int(current),
            "average_interest": round(avg, 1),
            "current_vs_average": round((current / avg - 1) * 100, 1) if avg > 0 else 0,
            "trend": trend,
            "rising_queries": rising_queries,
        }
    except Exception as e:
        logger.warning("Google Trends failed for %s: %s", ticker, e)
        return {"ticker": ticker, "message": f"Google Trends unavailable: {e}"}


def _get_query_category(index: int) -> str:
    """Map query index to category name."""
    categories = [
        (15, "Earnings & Financials"),
        (25, "Analyst & Ratings"),
        (35, "Insider & Institutional"),
        (45, "Dividends & Corporate Actions"),
        (55, "Management & Governance"),
        (65, "Sector & Competition"),
        (75, "Technical & Price"),
        (85, "Macro & Regulatory"),
        (95, "Sentiment & Social"),
        (100, "Location-Specific"),
    ]
    for threshold, name in categories:
        if index < threshold:
            return name
    return "Other"
