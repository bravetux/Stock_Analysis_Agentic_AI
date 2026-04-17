# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Synthesizer: Evidence list -> StockThesis.

Single Claude call, no tools. Responsible for:
- Confidence-weighted aggregation (replaces fixed 40/35/25 composite weights)
- Explicit contradiction resolution
- Scenario generation (base/bull/bear with probabilities + invalidators)
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from src.agents.bedrock_call import converse_json
from src.agents.evidence import Evidence, Signal, StockThesis
from src.config.prompts import SYNTHESIZER_PROMPT
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _fallback_thesis(ticker: str, exchange: str, evidence: list[Evidence], reason: str) -> StockThesis:
    """Degrade gracefully when the synthesizer call fails — never lose the run."""
    # Heuristic: pick dominant signal by confidence-weighted count.
    score = 0.0
    for ev in evidence:
        s = 1.0 if ev.signal == Signal.BULLISH else -1.0 if ev.signal == Signal.BEARISH else 0.0
        score += s * ev.confidence * ev.weight
    if score > 0.2:
        signal = Signal.BULLISH
    elif score < -0.2:
        signal = Signal.BEARISH
    else:
        signal = Signal.NEUTRAL

    return StockThesis(
        ticker=ticker,
        exchange=exchange,
        signal=signal,
        conviction=min(abs(score), 1.0),
        headline=f"[Fallback synthesis — {reason}]",
        scenarios=[
            {"name": "base", "probability": 0.6, "time_horizon_days": 90, "catalysts": [], "invalidators": []},  # type: ignore[list-item]
            {"name": "bull", "probability": 0.2, "time_horizon_days": 90, "catalysts": [], "invalidators": []},  # type: ignore[list-item]
            {"name": "bear", "probability": 0.2, "time_horizon_days": 90, "catalysts": [], "invalidators": []},  # type: ignore[list-item]
        ],
        top_evidence=sorted(
            evidence,
            key=lambda e: e.confidence * e.weight,
            reverse=True,
        )[:8],
        data_quality_flags=[f"synthesizer_fallback: {reason}"],
    )


def synthesize(ticker: str, exchange: str, evidence: list[Evidence]) -> StockThesis:
    """Convert a list of Evidence into a StockThesis via one Claude call."""
    if not evidence:
        return _fallback_thesis(ticker, exchange, [], "no evidence collected")

    evidence_json = json.dumps(
        [e.model_dump(mode="json") for e in evidence],
        ensure_ascii=False,
        default=str,
    )

    system_prompt = "You are a disciplined equity analyst. Return only the requested JSON object."
    user_prompt = SYNTHESIZER_PROMPT.format(
        ticker=ticker,
        exchange=exchange,
        evidence_json=evidence_json,
    )

    parsed = converse_json(
        system_prompt,
        user_prompt,
        temperature=settings.synthesizer_temperature,
    )
    if not isinstance(parsed, dict):
        logger.warning("Synthesizer returned non-dict; falling back")
        return _fallback_thesis(ticker, exchange, evidence, "non-dict response")

    parsed.setdefault("ticker", ticker)
    parsed.setdefault("exchange", exchange)
    # Ensure the LLM didn't drop evidence — if it did, keep top items from input.
    if not parsed.get("top_evidence"):
        parsed["top_evidence"] = [
            e.model_dump(mode="json")
            for e in sorted(evidence, key=lambda x: x.confidence * x.weight, reverse=True)[:8]
        ]

    try:
        return StockThesis.model_validate(parsed)
    except ValidationError as e:
        logger.warning("Synthesizer JSON failed validation: %s", e)
        return _fallback_thesis(ticker, exchange, evidence, f"validation error: {e}")
