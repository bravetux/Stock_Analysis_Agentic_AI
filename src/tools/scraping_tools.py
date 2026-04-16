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
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup
from strands import tool
from src.config.exchanges import ExchangeEnum, get_display_ticker, url_encode_ticker
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
    url = f"https://www.google.com/finance/quote/{url_encode_ticker(ticker)}:{gf_ex}"

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
    url = f"https://finance.yahoo.com/quote/{quote(yf_ticker, safe='')}/"

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
    search_url = f"https://www.moneycontrol.com/stocks/cptmarket/compsearchnew.php?search_data={quote(display, safe='')}&cid=&mbession_id=&tession_id=&search_page=&search_type="

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


@tool
def scrape_trendlyne(ticker: str) -> dict:
    """Scrape Trendlyne.com for DMA analysis, momentum score, and forecast data.
    Indian stocks only."""
    display = get_display_ticker(ticker)
    url = f"https://trendlyne.com/equity/{url_encode_ticker(ticker)}/"
    time.sleep(settings.scrape_delay_seconds)

    resp = _safe_get(url)
    if resp is None:
        return {"ticker": display, "error": "Could not fetch Trendlyne data", "source": "trendlyne"}

    soup = BeautifulSoup(resp.text, "lxml")

    data = {}
    tables = soup.find_all("table")
    for table in tables[:5]:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key:
                    data[key] = val

    score_divs = soup.find_all(["div", "span"], class_=lambda c: c and "score" in c.lower() if c else False)
    for div in score_divs[:3]:
        text = div.get_text(strip=True)
        if text:
            data["score_info"] = text

    return {
        "ticker": display,
        "source": "trendlyne",
        "url": url,
        "data": data,
    }


@tool
def scrape_tickertape(ticker: str) -> dict:
    """Scrape Tickertape.in for valuation scores, peer comparison, and checklists.
    Indian stocks only."""
    display = get_display_ticker(ticker)
    url = f"https://www.tickertape.in/stocks/{url_encode_ticker(ticker)}"
    time.sleep(settings.scrape_delay_seconds)

    resp = _safe_get(url)
    if resp is None:
        return {"ticker": display, "error": "Could not fetch Tickertape data", "source": "tickertape"}

    soup = BeautifulSoup(resp.text, "lxml")

    data = {}
    tables = soup.find_all("table")
    for idx, table in enumerate(tables[:5]):
        rows = table.find_all("tr")
        table_data = []
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells:
                table_data.append(cells)
        if table_data:
            data[f"table_{idx}"] = table_data

    checklists = soup.find_all(["div", "li"], class_=lambda c: c and "checklist" in c.lower() if c else False)
    checklist_items = [item.get_text(strip=True) for item in checklists[:10]]
    if checklist_items:
        data["checklist"] = checklist_items

    return {
        "ticker": display,
        "source": "tickertape",
        "url": url,
        "data": data,
    }
