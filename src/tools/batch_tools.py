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
from pathlib import Path
from strands import tool
from src.config.exchanges import detect_exchange, strip_prefix, get_display_ticker

logger = logging.getLogger(__name__)


@tool
def read_stocks_file(file_path: str) -> list:
    """Read a stock list file. Supports EXCHANGE:TICKER and plain ticker formats.
    Lines starting with # are comments. Blank lines are skipped.
    Returns list of {ticker, exchange, raw_line}."""
    path = Path(file_path)
    if not path.exists():
        return [{"error": f"File not found: {file_path}"}]

    stocks = []
    seen = set()

    for line_num, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()

        # Skip comments and blank lines
        if not line or line.startswith("#"):
            continue

        exchange = detect_exchange(line)
        ticker = strip_prefix(line).strip()
        display = get_display_ticker(ticker)

        # Deduplicate
        key = f"{exchange.value}:{display}"
        if key in seen:
            logger.info("Skipping duplicate: %s (line %d)", line, line_num)
            continue
        seen.add(key)

        stocks.append({
            "ticker": display,
            "exchange": exchange.value,
            "raw_line": raw_line.strip(),
            "line_number": line_num,
        })

    logger.info("Loaded %d unique stocks from %s", len(stocks), file_path)
    return stocks
