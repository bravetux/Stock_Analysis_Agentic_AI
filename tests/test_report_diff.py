# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Tests for src.reports.diff — field extraction, field comparison,
heading-based section parsing, section comparison."""

from __future__ import annotations

from src.reports.diff import (
    FieldChange,
    SectionChange,
    compare_fields,
    compare_sections,
    extract_fields,
    split_by_heading,
    summarise_section_changes,
)


RESEARCH_MD_A = """\
# Stock Analysis — NATCOPHARM (NSE)

*Generated 2026-04-15 10:00 UTC*

**Signal:** 🟢 BULLISH
**Conviction:** 68.0%
**Headline:** Momentum building after breakout above 200DMA.

## Scenarios

| Case | Probability | Price Target | Horizon (d) | Catalysts | Invalidators |
|---|---|---|---|---|---|
| base | 50.0% | 1,200.00 | 90 | Q4 results | Regulatory setback |
| bull | 30.0% | 1,350.00 | 90 | USFDA clearance | — |
| bear | 20.0% | 1,050.00 | 90 | — | Pricing pressure |

## Key Levels

| Level | Value |
|---|---|
| current_price | 1,086.80 |
| support | 1,020.00 |
| resistance | 1,150.00 |
| dma_200 | 1,010.00 |

## Top Evidence

- Technical thread: MACD crossed bullish on 2026-04-12.
"""

RESEARCH_MD_B = """\
# Stock Analysis — NATCOPHARM (NSE)

*Generated 2026-04-17 10:00 UTC*

**Signal:** ⚪ NEUTRAL
**Conviction:** 42.0%
**Headline:** Rally stalled; watch for retest of support.

## Scenarios

| Case | Probability | Price Target | Horizon (d) | Catalysts | Invalidators |
|---|---|---|---|---|---|
| base | 55.0% | 1,120.00 | 90 | — | — |
| bull | 20.0% | 1,280.00 | 90 | USFDA clearance | — |
| bear | 25.0% | 980.00 | 90 | — | Pricing pressure |

## Key Levels

| Level | Value |
|---|---|
| current_price | 1,060.00 |
| support | 1,020.00 |
| resistance | 1,150.00 |
| dma_200 | 1,015.00 |

## Top Evidence

- Technical thread: MACD histogram flattening.

## New Risks

- Competing generic launch flagged in filings.
"""


class TestExtractFields:
    def test_signal_and_conviction_from_research_format(self):
        f = extract_fields(RESEARCH_MD_A)
        assert f["Signal"] == ("enum", "BULLISH")
        assert f["Conviction"] == ("pct", 68.0)

    def test_current_price_and_dma(self):
        f = extract_fields(RESEARCH_MD_A)
        assert f["Current Price"] == ("num", 1086.80)
        assert f["200DMA"] == ("num", 1010.00)

    def test_scenario_targets(self):
        f = extract_fields(RESEARCH_MD_A)
        assert f["Base Target"] == ("num", 1200.00)
        assert f["Bull Target"] == ("num", 1350.00)
        assert f["Bear Target"] == ("num", 1050.00)

    def test_headline_text(self):
        f = extract_fields(RESEARCH_MD_A)
        assert f["Headline"][0] == "text"
        assert "Momentum building" in f["Headline"][1]


class TestCompareFields:
    def test_signal_transition(self):
        changes = {c.field: c for c in compare_fields(RESEARCH_MD_A, RESEARCH_MD_B)}
        sig = changes["Signal"]
        assert sig.direction == "changed"
        assert sig.before == "BULLISH" and sig.after == "NEUTRAL"

    def test_conviction_delta_downward(self):
        changes = {c.field: c for c in compare_fields(RESEARCH_MD_A, RESEARCH_MD_B)}
        conv = changes["Conviction"]
        assert conv.direction == "down"
        assert conv.delta == -26.0

    def test_price_delta_has_percent(self):
        changes = {c.field: c for c in compare_fields(RESEARCH_MD_A, RESEARCH_MD_B)}
        cp = changes["Current Price"]
        assert cp.direction == "down"
        assert cp.delta is not None and cp.delta < 0
        assert cp.delta_pct is not None
        # -2.47% move
        assert -3 < cp.delta_pct < -2

    def test_unchanged_field_marked_same(self):
        changes = {c.field: c for c in compare_fields(RESEARCH_MD_A, RESEARCH_MD_B)}
        supp = changes["Support"]
        assert supp.direction == "same"
        assert supp.delta == 0.0


class TestSplitByHeading:
    def test_sections_parsed_with_hierarchy(self):
        md = """\
# Top
intro

## Alpha
body-a

### A1
a1 body

## Beta
body-b
"""
        sections = split_by_heading(md)
        assert [(s.level, s.title) for s in sections] == [
            (1, "Top"),
            (2, "Alpha"),
            (3, "A1"),
            (2, "Beta"),
        ]
        # Path for "A1" should include both ancestors.
        a1 = next(s for s in sections if s.title == "A1")
        assert a1.path == ("top", "alpha", "a1")

    def test_heading_normalisation_strips_emoji_and_bold(self):
        md = "## 📈 **200-DAY MOVING AVERAGE ANALYSIS**\nbody"
        sec = split_by_heading(md)[0]
        assert sec.key == "200-day moving average analysis"

    def test_bodies_captured(self):
        sections = split_by_heading(RESEARCH_MD_A)
        scen = next(s for s in sections if s.title == "Scenarios")
        assert "| base | 50.0% | 1,200.00" in scen.body


class TestCompareSections:
    def test_added_section_detected(self):
        changes = compare_sections(RESEARCH_MD_A, RESEARCH_MD_B)
        added = [c for c in changes if c.status == "added"]
        assert any(c.shown_title.lower() == "new risks" for c in added)

    def test_unchanged_vs_changed_classification(self):
        changes = compare_sections(RESEARCH_MD_A, RESEARCH_MD_B)
        by_path = {c.path: c for c in changes}
        # Scenarios body changed.
        scen_path = next(p for p in by_path if p[-1] == "scenarios")
        assert by_path[scen_path].status == "changed"
        # Top Evidence body changed.
        te_path = next(p for p in by_path if p[-1] == "top evidence")
        assert by_path[te_path].status == "changed"

    def test_removed_section_detected(self):
        md_before = "## Only Here\nfoo body\n"
        md_after = "## Other\nbar body\n"
        changes = compare_sections(md_before, md_after)
        removed = [c for c in changes if c.status == "removed"]
        assert any(c.shown_title.lower() == "only here" for c in removed)

    def test_summary_counts(self):
        changes = compare_sections(RESEARCH_MD_A, RESEARCH_MD_B)
        counts = summarise_section_changes(changes)
        # At minimum: at least one added, at least one changed.
        assert counts["added"] >= 1
        assert counts["changed"] >= 1
        assert counts.get("unchanged", 0) + counts["added"] + counts["changed"] + counts.get("removed", 0) == len(changes)


class TestClassicFormat:
    """Smoke-test that the old LLM-narrative format still yields some fields."""

    def test_extracts_price_and_dma(self):
        md = (
            "## Analysis\n"
            "- **Current Price**: ₹741.40\n"
            "- **200DMA Level**: ₹922.75\n"
            "### **Risk Level**: **MODERATE-HIGH** (7.0/10)\n"
            "### **Composite Score Signal: 7.8/10 (BUY)**\n"
        )
        f = extract_fields(md)
        assert f["Current Price"][1] == 741.40
        assert f["200DMA"][1] == 922.75
        assert f["Signal"][1] == "BUY"
        assert f["Risk Level"][1] == "MODERATE-HIGH"
