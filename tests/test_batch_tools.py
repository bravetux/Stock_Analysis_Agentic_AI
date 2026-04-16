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

import tempfile
import os
import pytest
from src.tools.batch_tools import read_stocks_file


class TestReadStocksFile:
    def _write_temp(self, content: str) -> str:
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        f.write(content)
        f.close()
        return f.name

    def test_basic_parsing(self):
        path = self._write_temp("NSE:RELIANCE\nNASDAQ:AAPL\n")
        try:
            result = read_stocks_file.__wrapped__(path)
            assert len(result) == 2
            assert result[0]["ticker"] == "RELIANCE"
            assert result[0]["exchange"] == "NSE"
            assert result[1]["ticker"] == "AAPL"
            assert result[1]["exchange"] == "NASDAQ"
        finally:
            os.unlink(path)

    def test_comments_skipped(self):
        path = self._write_temp("# This is a comment\nNSE:TCS\n# Another comment\n")
        try:
            result = read_stocks_file.__wrapped__(path)
            assert len(result) == 1
            assert result[0]["ticker"] == "TCS"
        finally:
            os.unlink(path)

    def test_blank_lines_skipped(self):
        path = self._write_temp("NSE:INFY\n\n\nNASDAQ:GOOGL\n")
        try:
            result = read_stocks_file.__wrapped__(path)
            assert len(result) == 2
        finally:
            os.unlink(path)

    def test_bse_scrip_code(self):
        path = self._write_temp("BSE:500325\n")
        try:
            result = read_stocks_file.__wrapped__(path)
            assert result[0]["exchange"] == "BSE"
            assert result[0]["ticker"] == "500325"
        finally:
            os.unlink(path)

    def test_deduplication(self):
        path = self._write_temp("NSE:RELIANCE\nNSE:RELIANCE\n")
        try:
            result = read_stocks_file.__wrapped__(path)
            assert len(result) == 1
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        result = read_stocks_file.__wrapped__("/nonexistent/file.txt")
        assert len(result) == 1
        assert "error" in result[0]

    def test_mixed_formats(self):
        content = """# Indian Markets
NSE:RELIANCE
BSE:500325
# US Market
NASDAQ:AAPL
"""
        path = self._write_temp(content)
        try:
            result = read_stocks_file.__wrapped__(path)
            assert len(result) == 3
            exchanges = [s["exchange"] for s in result]
            assert "NSE" in exchanges
            assert "BSE" in exchanges
            assert "NASDAQ" in exchanges
        finally:
            os.unlink(path)
