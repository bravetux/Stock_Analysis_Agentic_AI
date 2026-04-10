# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
import time
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
