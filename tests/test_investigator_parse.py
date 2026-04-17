# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Tests for the investigator response parser — no Bedrock calls."""

from __future__ import annotations

from src.agents.evidence import Signal
from src.agents.investigator import _extract_json_array, _parse_evidence


def test_extract_plain_json_array():
    raw = '[{"thread_id": "technical", "claim": "MACD bullish"}]'
    arr = _extract_json_array(raw)
    assert arr == [{"thread_id": "technical", "claim": "MACD bullish"}]


def test_extract_fenced_json_array():
    raw = '```json\n[{"thread_id": "news", "claim": "Positive Q4"}]\n```'
    arr = _extract_json_array(raw)
    assert arr is not None
    assert arr[0]["claim"] == "Positive Q4"


def test_extract_json_array_embedded_in_prose():
    raw = (
        "Here are my findings.\n"
        '[{"thread_id": "t", "claim": "a"}, {"thread_id": "t", "claim": "b"}]\n'
        "Hope that helps."
    )
    arr = _extract_json_array(raw)
    assert arr is not None
    assert len(arr) == 2


def test_extract_json_array_returns_none_on_garbage():
    assert _extract_json_array("no JSON here, just prose") is None


def test_parse_evidence_fills_thread_id_default():
    raw = '[{"claim": "x", "confidence": 0.8}]'
    items = _parse_evidence(raw, thread_id="fundamental")
    assert len(items) == 1
    assert items[0].thread_id == "fundamental"
    assert items[0].confidence == 0.8


def test_parse_evidence_drops_malformed_entries():
    raw = '[{"claim": "good", "signal": "bullish"}, {"claim": ""}, {"not_evidence": true}]'
    items = _parse_evidence(raw, thread_id="technical")
    # The empty-claim entry is dropped; the shapeless entry is dropped too.
    assert len(items) == 1
    assert items[0].signal == Signal.BULLISH
