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

from src.config.exchanges import ExchangeEnum
from src.config.search_queries import generate_search_queries


class TestGenerateSearchQueries:
    def test_generates_100_queries(self):
        queries = generate_search_queries("RELIANCE", "Reliance Industries", ExchangeEnum.NSE)
        assert len(queries) == 100

    def test_stock_name_substituted(self):
        queries = generate_search_queries("AAPL", "Apple Inc", ExchangeEnum.NASDAQ)
        # At least some queries should contain the stock name
        stock_queries = [q for q in queries if "AAPL" in q]
        assert len(stock_queries) > 0

    def test_company_name_substituted(self):
        queries = generate_search_queries("TCS", "Tata Consultancy Services", ExchangeEnum.NSE)
        company_queries = [q for q in queries if "Tata Consultancy Services" in q]
        assert len(company_queries) > 0

    def test_india_location_queries(self):
        queries = generate_search_queries("RELIANCE", "Reliance Industries", ExchangeEnum.NSE)
        # Should contain India-specific sources
        india_sources = [q for q in queries if any(s in q for s in ["moneycontrol", "economic times", "livemint", "business standard", "CNBC TV18"])]
        assert len(india_sources) > 0

    def test_us_location_queries(self):
        queries = generate_search_queries("AAPL", "Apple Inc", ExchangeEnum.NASDAQ)
        # Should contain US-specific sources
        us_sources = [q for q in queries if any(s in q for s in ["seeking alpha", "motley fool", "barrons", "bloomberg", "CNBC news"])]
        assert len(us_sources) > 0

    def test_year_substituted(self):
        queries = generate_search_queries("TCS", "TCS Ltd", ExchangeEnum.NSE)
        from datetime import datetime
        year = str(datetime.now().year)
        year_queries = [q for q in queries if year in q]
        assert len(year_queries) > 0

    def test_no_empty_queries(self):
        queries = generate_search_queries("INFY", "Infosys", ExchangeEnum.NSE)
        for q in queries:
            assert q.strip() != ""

    def test_all_queries_unique(self):
        queries = generate_search_queries("MSFT", "Microsoft", ExchangeEnum.NASDAQ)
        assert len(queries) == len(set(queries))
