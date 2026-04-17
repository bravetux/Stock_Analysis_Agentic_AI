# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Tests for synthesizer fallback behaviour (no Bedrock calls)."""

from __future__ import annotations

from src.agents.evidence import Evidence, Signal
from src.agents.synthesizer import _fallback_thesis, synthesize


def test_fallback_thesis_flips_to_bullish_on_weighted_evidence():
    ev = [
        Evidence(thread_id="technical", claim="a", signal=Signal.BULLISH, confidence=0.9, weight=0.8),
        Evidence(thread_id="technical", claim="b", signal=Signal.BULLISH, confidence=0.7, weight=0.7),
        Evidence(thread_id="fundamental", claim="c", signal=Signal.BEARISH, confidence=0.4, weight=0.3),
    ]
    t = _fallback_thesis("X", "NSE", ev, "testing")
    assert t.signal == Signal.BULLISH
    assert t.conviction > 0.3
    assert any("synthesizer_fallback" in flag for flag in t.data_quality_flags)


def test_fallback_thesis_is_neutral_when_evidence_cancels():
    ev = [
        Evidence(thread_id="t", claim="a", signal=Signal.BULLISH, confidence=0.5, weight=0.5),
        Evidence(thread_id="t", claim="b", signal=Signal.BEARISH, confidence=0.5, weight=0.5),
    ]
    t = _fallback_thesis("X", "NSE", ev, "testing")
    assert t.signal == Signal.NEUTRAL


def test_synthesize_with_empty_evidence_returns_fallback():
    t = synthesize("ZZZ", "NSE", [])
    assert t.ticker == "ZZZ"
    assert t.exchange == "NSE"
    assert t.signal == Signal.NEUTRAL
    assert any("no evidence" in flag for flag in t.data_quality_flags)


def test_synthesize_falls_back_on_bedrock_failure(monkeypatch):
    # Monkeypatch converse_json to simulate Bedrock returning garbage.
    from src.agents import synthesizer as syn_mod

    monkeypatch.setattr(syn_mod, "converse_json", lambda *a, **kw: None)
    ev = [Evidence(thread_id="technical", claim="x", signal=Signal.BULLISH, confidence=0.8, weight=0.8)]
    t = syn_mod.synthesize("AAA", "NASDAQ", ev)
    assert t.signal == Signal.BULLISH
    assert any("synthesizer_fallback" in f for f in t.data_quality_flags)
