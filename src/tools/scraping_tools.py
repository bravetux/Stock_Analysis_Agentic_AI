# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
import time
import httpx
from bs4 import BeautifulSoup
from strands import tool
from src.config.exchanges import ExchangeEnum, get_display_ticker
from src.config.settings import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _safe_get(url: str, timeout: int = 15) -> httpx.Response | None:
    """Make a rate-limited HTTP GET request."""
    try:
        time.sleep(settings.scrape_delay_seconds)
        resp = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.warning("HTTP GET failed for %s: %s", url, e)
        return None


@tool
def scrape_google_finance(ticker: str, exchange: str) -> dict:
    """Scrape Google Finance page for a stock. Returns price, stats, and related news."""
    ex = ExchangeEnum(exchange.upper())
    display = get_display_ticker(ticker)

    # Google Finance uses exchange codes
    gf_exchange_map = {
        ExchangeEnum.NSE: "NSE",
        ExchangeEnum.BSE: "BOM",
        ExchangeEnum.NASDAQ: "NASDAQ",
    }
    gf_ex = gf_exchange_map.get(ex, ex.value)
    url = f"https://www.google.com/finance/quote/{display}:{gf_ex}"

    resp = _safe_get(url)
    if not resp:
        return {"error": f"Failed to fetch Google Finance for {display}", "url": url}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"ticker": display, "exchange": exchange, "url": url, "source": "Google Finance"}

    # Current price from data-last-price or fin-streamer
    price_el = soup.find("div", class_="YMlKec fxKbKc")
    if price_el:
        result["current_price"] = price_el.get_text(strip=True)

    # Key stats table
    stats = {}
    stat_rows = soup.find_all("div", class_="P6K39c")
    for row in stat_rows:
        label_el = row.find("div", class_="mfs7Fc")
        value_el = row.find("div", class_="YMlKec")
        if label_el and value_el:
            stats[label_el.get_text(strip=True)] = value_el.get_text(strip=True)
    result["stats"] = stats

    # About section
    about_el = soup.find("div", class_="bLLb2d")
    if about_el:
        result["about"] = about_el.get_text(strip=True)[:500]

    # Related news headlines
    news_items = []
    news_els = soup.find_all("div", class_="Yfwt5")
    for el in news_els[:10]:
        headline = el.get_text(strip=True)
        if headline:
            news_items.append(headline)
    result["news_headlines"] = news_items

    return result


@tool
def scrape_yahoo_finance_page(ticker: str, exchange: str) -> dict:
    """Scrape Yahoo Finance summary page for additional stats and analyst recommendations."""
    ex = ExchangeEnum(exchange.upper())
    display = get_display_ticker(ticker)

    # Yahoo Finance ticker format
    yf_map = {ExchangeEnum.NSE: f"{display}.NS", ExchangeEnum.BSE: f"{display}.BO"}
    yf_ticker = yf_map.get(ex, display)
    url = f"https://finance.yahoo.com/quote/{yf_ticker}/"

    resp = _safe_get(url)
    if not resp:
        return {"error": f"Failed to fetch Yahoo Finance for {yf_ticker}", "url": url}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"ticker": display, "exchange": exchange, "url": url, "source": "Yahoo Finance"}

    # Summary stats from the data table
    stats = {}
    table_rows = soup.find_all("tr")
    for row in table_rows:
        cells = row.find_all("td")
        if len(cells) == 2:
            label = cells[0].get_text(strip=True)
            value = cells[1].get_text(strip=True)
            if label and value:
                stats[label] = value
    result["summary_stats"] = stats

    # Try to get analyst recommendation
    recs = soup.find_all("div", {"data-testid": "rec-rating"})
    if recs:
        result["analyst_recommendation"] = recs[0].get_text(strip=True)

    return result


@tool
def scrape_moneycontrol(ticker: str) -> dict:
    """Scrape MoneyControl for Indian stock data — fundamentals, news, and analyst views."""
    display = get_display_ticker(ticker)
    search_url = f"https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={display}&cid=&mbession_id=&tession_id=&search_page=&search_type="

    resp = _safe_get(search_url)
    if not resp:
        return {"error": f"Failed to search MoneyControl for {display}"}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"ticker": display, "source": "MoneyControl"}

    # Extract any table data found
    tables = soup.find_all("table")
    if tables:
        for table in tables[:2]:
            rows = table.find_all("tr")
            for row in rows[:20]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if label and value:
                        result[label] = value

    # News headlines
    news = []
    news_links = soup.find_all("a", href=True)
    for link in news_links:
        text = link.get_text(strip=True)
        href = link["href"]
        if text and len(text) > 20 and "news" in href.lower():
            news.append({"title": text, "link": href})
    result["news"] = news[:10]

    return result
