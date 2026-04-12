# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
import time
import httpx
from bs4 import BeautifulSoup
from strands import tool
from src.config.exchanges import get_display_ticker, url_encode_ticker
from src.config.settings import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

CHARTINK_SCREENER_URL = "https://chartink.com/screener/process"


@tool
def scrape_chartink_screener(scan_clause: str) -> dict:
    """Run a Chartink screener scan. scan_clause is the Chartink scan query.
    Example: '( {cash} ( latest close > latest sma( close,200 ) ) )'
    Returns list of matching stocks with name, symbol, close, volume, etc."""
    time.sleep(settings.scrape_delay_seconds)

    # First get CSRF token
    try:
        session_resp = httpx.get("https://chartink.com/screener", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(session_resp.text, "lxml")
        csrf_token = None
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta:
            csrf_token = meta.get("content")
    except Exception as e:
        return {"error": f"Failed to get Chartink CSRF token: {e}"}

    if not csrf_token:
        return {"error": "Could not extract CSRF token from Chartink"}

    # Execute screener query
    payload = {"scan_clause": scan_clause}
    post_headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-CSRF-TOKEN": csrf_token,
        "Referer": "https://chartink.com/screener",
    }

    # Pass cookies from the session response
    cookies = dict(session_resp.cookies)

    try:
        resp = httpx.post(
            CHARTINK_SCREENER_URL,
            data=payload,
            headers=post_headers,
            cookies=cookies,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"Chartink screener request failed: {e}"}

    stocks = []
    for item in data.get("data", []):
        stocks.append({
            "name": item.get("nsecode", ""),
            "bsecode": item.get("bsecode", ""),
            "per_change": item.get("per_chg", ""),
            "close": item.get("close", ""),
            "volume": item.get("volume", ""),
        })

    return {
        "scan_clause": scan_clause,
        "total_matches": len(stocks),
        "stocks": stocks,
        "source": "Chartink",
    }


@tool
def get_chartink_stock_data(ticker: str) -> dict:
    """Get Chartink technical data page for a specific stock.
    Returns available technical indicators and chart data."""
    display = get_display_ticker(ticker)
    url = f"https://chartink.com/stocks/{url_encode_ticker(ticker)}.html"

    time.sleep(settings.scrape_delay_seconds)
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch Chartink for {display}: {e}", "url": url}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"ticker": display, "source": "Chartink", "url": url}

    # Extract any available data tables
    tables = soup.find_all("table")
    for table in tables[:3]:
        caption = table.find("caption")
        table_name = caption.get_text(strip=True) if caption else "data"

        rows = []
        for tr in table.find_all("tr")[:15]:
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            result[table_name] = rows

    # Common Chartink scan results
    result["common_scans"] = {
        "200dma_breakout": "( {cash} ( latest close > latest sma( close,200 ) and 1 day ago close < 1 day ago sma( close,200 ) ) )",
        "macd_bullish": "( {cash} ( latest macd line( 26,12,9 ) > latest macd signal( 26,12,9 ) and 1 day ago macd line( 26,12,9 ) < 1 day ago macd signal( 26,12,9 ) ) )",
        "volume_breakout": "( {cash} ( latest volume > 2 * latest sma( volume,20 ) ) )",
    }

    return result
