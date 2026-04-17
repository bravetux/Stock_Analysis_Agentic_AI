# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Tests for deterministic StockThesis -> Markdown/XLSX rendering."""

from __future__ import annotations

from src.agents.evidence import Evidence, ScenarioCase, Signal, StockThesis
from src.reports.render import (
    consolidated_markdown_table,
    consolidated_rows,
    consolidated_xlsx_bytes,
    render_thesis_markdown,
)


def _make_thesis(ticker: str, signal: Signal, conviction: float) -> StockThesis:
    return StockThesis(
        ticker=ticker,
        exchange="NSE",
        signal=signal,
        conviction=conviction,
        headline=f"{ticker} headline",
        scenarios=[
            ScenarioCase(name="base", probability=0.5, price_target=100.0),
            ScenarioCase(name="bull", probability=0.3, price_target=120.0),
            ScenarioCase(name="bear", probability=0.2, price_target=80.0),
        ],
        key_levels={"current_price": 95.0, "support": 85.0, "resistance": 110.0, "dma_200": 90.0},
        top_evidence=[
            Evidence(thread_id="technical", claim="MACD bullish", signal=Signal.BULLISH, confidence=0.7),
        ],
        data_quality_flags=["no options data for NSE"],
    )


def test_render_includes_all_major_sections():
    t = _make_thesis("RELIANCE", Signal.BULLISH, 0.68)
    md = render_thesis_markdown(t)
    assert "# Stock Analysis — RELIANCE (NSE)" in md
    assert "BULLISH" in md
    assert "## Scenarios" in md
    assert "## Key Levels" in md
    assert "## Top Evidence" in md
    assert "## Data Quality Notes" in md
    assert "no options data" in md


def test_render_hides_citations_when_requested():
    t = _make_thesis("X", Signal.NEUTRAL, 0.3)
    md = render_thesis_markdown(t, include_citations=False)
    assert "## Top Evidence" not in md


def test_consolidated_rows_shape():
    theses = [
        _make_thesis("A", Signal.BULLISH, 0.6),
        _make_thesis("B", Signal.BEARISH, 0.4),
    ]
    headers, rows = consolidated_rows(theses)
    assert headers[0] == "S.No"
    assert headers[1] == "Ticker"
    assert len(rows) == 2
    assert rows[0][1] == "A"
    assert rows[1][1] == "B"
    assert rows[0][3] == "bullish"


def test_consolidated_markdown_table_is_parseable():
    theses = [_make_thesis("A", Signal.BULLISH, 0.6)]
    md = consolidated_markdown_table(theses)
    lines = [l for l in md.splitlines() if l.strip().startswith("|")]
    # header + divider + 1 data row
    assert len(lines) == 3
    assert "A" in lines[2]


def test_consolidated_xlsx_bytes_returns_bytes():
    theses = [_make_thesis("A", Signal.BULLISH, 0.6), _make_thesis("B", Signal.BEARISH, 0.5)]
    data = consolidated_xlsx_bytes(theses)
    assert isinstance(data, bytes)
    assert len(data) > 0
    # XLSX files start with PK (zip magic)
    assert data[:2] == b"PK"
