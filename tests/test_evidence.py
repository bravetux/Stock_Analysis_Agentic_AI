# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Unit tests for the Evidence contract and its validators."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.agents.evidence import (
    CritiqueReport,
    Evidence,
    FollowUpRequest,
    ResearchPlan,
    ScenarioCase,
    Signal,
    StockThesis,
    ThreadSpec,
)


def test_evidence_minimal():
    ev = Evidence(thread_id="technical", claim="MACD turned bullish on 2026-04-12")
    assert ev.signal == Signal.NEUTRAL
    assert ev.confidence == 0.5
    assert ev.weight == 0.5
    assert ev.caveats == []


def test_evidence_rejects_empty_claim():
    with pytest.raises(ValidationError):
        Evidence(thread_id="technical", claim="   ")


def test_evidence_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        Evidence(thread_id="x", claim="y", confidence=1.5)


def test_evidence_round_trips_json():
    original = Evidence(
        thread_id="news",
        claim="Q4 beat expectations",
        signal=Signal.BULLISH,
        confidence=0.8,
        weight=0.7,
        source_tool="search_news_batch",
        data={"surprise_pct": 12.4},
        caveats=["sample size small"],
    )
    raw = original.model_dump_json()
    restored = Evidence.model_validate_json(raw)
    assert restored.thread_id == original.thread_id
    assert restored.signal == Signal.BULLISH
    assert restored.data["surprise_pct"] == 12.4


def test_thread_spec_budget_bounds():
    with pytest.raises(ValidationError):
        ThreadSpec(thread_id="x", objective="y", budget_tool_calls=0)
    with pytest.raises(ValidationError):
        ThreadSpec(thread_id="x", objective="y", budget_tool_calls=99)


def test_research_plan_round_trip():
    plan = ResearchPlan(
        ticker="RELIANCE",
        exchange="NSE",
        horizon="medium",
        framing="Can the stock break resistance on Q4 results?",
        threads=[
            ThreadSpec(thread_id="technical", objective="Where's resistance?", priority="high", budget_tool_calls=5),
            ThreadSpec(thread_id="news", objective="Any catalysts?", priority="medium", budget_tool_calls=3),
        ],
    )
    raw = plan.model_dump_json()
    restored = ResearchPlan.model_validate_json(raw)
    assert restored.ticker == "RELIANCE"
    assert len(restored.threads) == 2
    assert restored.threads[0].priority == "high"


def test_stock_thesis_round_trip():
    thesis = StockThesis(
        ticker="AAPL",
        exchange="NASDAQ",
        signal=Signal.BULLISH,
        conviction=0.72,
        headline="Strong guidance with expanding margins",
        scenarios=[
            ScenarioCase(name="base", probability=0.55, price_target=210.0, catalysts=["iPhone cycle"]),
            ScenarioCase(name="bull", probability=0.25, price_target=235.0, catalysts=["services"]),
            ScenarioCase(name="bear", probability=0.20, price_target=175.0, invalidators=["demand shock"]),
        ],
        key_levels={"current_price": 195.0, "support": 180.0, "resistance": 210.0, "dma_200": 188.0},
        contradictions_resolved=["Valuation stretched but growth sustains"],
        top_evidence=[
            Evidence(thread_id="fundamental", claim="Revenue growth 8% yoy", signal=Signal.BULLISH, confidence=0.7),
        ],
        data_quality_flags=["insider_data_us_only"],
    )
    raw = thesis.model_dump_json()
    restored = StockThesis.model_validate_json(raw)
    assert restored.signal == Signal.BULLISH
    assert len(restored.scenarios) == 3
    assert restored.key_levels["current_price"] == 195.0
    assert restored.top_evidence[0].thread_id == "fundamental"


def test_follow_up_request_defaults_to_no_followup():
    rep = CritiqueReport()
    assert rep.follow_up.needs_followup is False
    assert rep.strongest_claims == []


def test_signal_enum_parses_from_string():
    data = json.loads(json.dumps({"thread_id": "x", "claim": "y", "signal": "bearish"}))
    ev = Evidence.model_validate(data)
    assert ev.signal == Signal.BEARISH
