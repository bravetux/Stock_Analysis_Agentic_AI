# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import logging
import time
import httpx
from bs4 import BeautifulSoup
from strands import tool
from src.config.exchanges import get_display_ticker
from src.config.settings import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


@tool
def scrape_screener_in(ticker: str) -> dict:
    """Scrape Screener.in for Indian stock fundamentals.
    Returns PE, market cap, book value, dividend yield, ROCE, ROE,
    sales growth, profit growth, debt-to-equity, promoter holding."""
    display = get_display_ticker(ticker)
    url = f"https://www.screener.in/company/{display}/consolidated/"

    time.sleep(settings.scrape_delay_seconds)
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        if resp.status_code == 404:
            # Try standalone instead of consolidated
            url = f"https://www.screener.in/company/{display}/"
            resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        return {"error": f"Failed to fetch Screener.in for {display}: {e}", "url": url}

    soup = BeautifulSoup(resp.text, "lxml")
    result = {"ticker": display, "source": "Screener.in", "url": url}

    # Top-level ratios (displayed in the header section)
    ratio_list = soup.find("ul", id="top-ratios")
    if ratio_list:
        items = ratio_list.find_all("li")
        for item in items:
            name_el = item.find("span", class_="name")
            value_el = item.find("span", class_="number") or item.find("span", class_="value")
            if name_el and value_el:
                name = name_el.get_text(strip=True)
                value = value_el.get_text(strip=True)
                result[_clean_key(name)] = value

    # Quarterly results table
    quarters_table = soup.find("section", id="quarters")
    if quarters_table:
        result["quarterly_results"] = _extract_table(quarters_table)

    # Profit & Loss
    pl_table = soup.find("section", id="profit-loss")
    if pl_table:
        result["profit_loss"] = _extract_table(pl_table)

    # Shareholding pattern
    sh_table = soup.find("section", id="shareholding")
    if sh_table:
        result["shareholding"] = _extract_table(sh_table)

    # Pros and Cons
    for section_class in ["pros", "cons"]:
        section = soup.find("div", class_=section_class)
        if section:
            items = section.find_all("li")
            result[section_class] = [li.get_text(strip=True) for li in items]

    return result


def _clean_key(text: str) -> str:
    """Convert label text to a clean dict key."""
    return text.lower().strip().replace(" ", "_").replace("/", "_").replace(".", "").replace("(", "").replace(")", "")


def _extract_table(section) -> list[dict]:
    """Extract table data from a Screener.in section."""
    table = section.find("table")
    if not table:
        return []

    headers_row = table.find("thead")
    if not headers_row:
        return []

    headers = [th.get_text(strip=True) for th in headers_row.find_all("th")]
    rows = []

    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr")[:10]:  # Limit rows
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                row_dict = {}
                # First cell is usually the label
                for i, val in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_dict[key] = val
                rows.append(row_dict)

    return rows
