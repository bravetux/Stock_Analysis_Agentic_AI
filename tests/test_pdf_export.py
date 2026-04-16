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

from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk, save_md_to_disk, build_tool_log_markdown


def test_markdown_to_pdf_returns_bytes():
    md = "# Test Report\n\nThis is a **test** report.\n\n| Col1 | Col2 |\n|------|------|\n| A | B |"
    result = markdown_to_pdf(md, "RELIANCE", "NSE", "beginner")
    assert isinstance(result, bytes)
    assert len(result) > 0
    # PDF magic bytes
    assert result[:5] == b"%PDF-"


def test_markdown_to_pdf_with_empty_content():
    result = markdown_to_pdf("", "AAPL", "NASDAQ", "expert")
    assert isinstance(result, bytes)
    assert result[:5] == b"%PDF-"


def test_save_pdf_to_disk(tmp_path):
    md = "# Test\nContent"
    pdf_bytes = markdown_to_pdf(md, "RELIANCE", "NSE", "beginner")
    path = save_pdf_to_disk(pdf_bytes, "RELIANCE", "NSE", reports_dir=str(tmp_path))
    assert path.endswith(".pdf")
    assert "NSE_RELIANCE_" in path
    with open(path, "rb") as f:
        assert f.read()[:5] == b"%PDF-"


def test_save_md_to_disk(tmp_path):
    md = "# Test\nContent here"
    path = save_md_to_disk(md, "RELIANCE", "NSE", reports_dir=str(tmp_path))
    assert path.endswith(".md")
    assert "NSE_RELIANCE_" in path
    with open(path, "r", encoding="utf-8") as f:
        assert f.read() == md


def test_build_tool_log_markdown_with_entries():
    entries = [
        {"Tool": "get_stock_quote", "Started": "14:00:01", "Completed": "14:00:03", "Duration (s)": 1.82},
        {"Tool": "calculate_200dma", "Started": "14:00:03", "Completed": "14:00:05", "Duration (s)": 2.14},
    ]
    result = build_tool_log_markdown(entries)
    assert "## Tool Execution Log" in result
    assert "get_stock_quote" in result
    assert "calculate_200dma" in result
    assert "**3.96**" in result  # total


def test_build_tool_log_markdown_empty():
    assert build_tool_log_markdown([]) == ""


def test_pdf_includes_tool_log():
    md = "# Report\nAnalysis content"
    entries = [
        {"Tool": "get_stock_quote", "Started": "14:00:01", "Completed": "14:00:03", "Duration (s)": 1.82},
    ]
    tool_log = build_tool_log_markdown(entries)
    full_report = md + tool_log
    pdf_bytes = markdown_to_pdf(full_report, "RELIANCE", "NSE", "beginner")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes[:5] == b"%PDF-"
