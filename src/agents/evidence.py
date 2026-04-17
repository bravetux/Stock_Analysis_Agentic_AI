# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Evidence contract for the research-agent pattern.

Every investigator returns list[Evidence] instead of free-text markdown.
Synthesizer reads evidence and produces a StockThesis. Reports are rendered
deterministically from StockThesis, not parsed back from LLM output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Signal(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    INCONCLUSIVE = "inconclusive"


class Evidence(BaseModel):
    """A single atomic finding from an investigator.

    Evidence is the unit of exchange between investigators and the synthesizer.
    Each piece carries its own signal, confidence, and citation so the
    synthesizer can reconcile disagreement without losing provenance.
    """

    thread_id: str = Field(description="Investigator that produced this evidence, e.g. 'technical'")
    claim: str = Field(description="One-sentence factual statement")
    signal: Signal = Signal.NEUTRAL
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    weight: float = Field(ge=0.0, le=1.0, default=0.5, description="Importance within the thread")
    source_tool: str = Field(default="", description="Tool name, URL, or 'reasoning'")
    source_args: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict, description="Raw numeric payload")
    caveats: list[str] = Field(default_factory=list)

    @field_validator("claim")
    @classmethod
    def _claim_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("claim must not be empty")
        return v.strip()


class ThreadSpec(BaseModel):
    """One investigation thread the planner wants run."""

    thread_id: str
    objective: str = Field(description="A single question the investigator must answer")
    priority: Literal["high", "medium", "low"] = "medium"
    budget_tool_calls: int = Field(default=5, ge=1, le=20)


class ResearchPlan(BaseModel):
    """Planner output — decomposition of the stock analysis into threads."""

    ticker: str
    exchange: str
    horizon: Literal["short", "medium", "long"] = "medium"
    framing: str = Field(description="What the user is really asking and what would change the answer")
    threads: list[ThreadSpec]


class ScenarioCase(BaseModel):
    name: Literal["base", "bull", "bear"]
    probability: float = Field(ge=0.0, le=1.0)
    price_target: float | None = None
    time_horizon_days: int = 90
    catalysts: list[str] = Field(default_factory=list)
    invalidators: list[str] = Field(default_factory=list, description="What would kill this scenario")


class StockThesis(BaseModel):
    """Synthesizer output — the full, structured thesis on a stock."""

    ticker: str
    exchange: str
    signal: Signal
    conviction: float = Field(ge=0.0, le=1.0, description="Confidence-weighted composite")
    headline: str = Field(description="One-line summary of the thesis")
    scenarios: list[ScenarioCase]
    key_levels: dict[str, float | None] = Field(
        default_factory=dict,
        description="support, resistance, fib_618, vwap, dma_200, current_price",
    )
    contradictions_resolved: list[str] = Field(
        default_factory=list,
        description="Explicit reasoning where evidence disagreed",
    )
    top_evidence: list[Evidence] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FollowUpRequest(BaseModel):
    """Self-critic output when it finds a gap worth a follow-up investigation."""

    needs_followup: bool
    thread_id: str | None = None
    objective: str | None = None
    reason: str = ""


class CritiqueReport(BaseModel):
    """Self-critic summary returned alongside any FollowUpRequest."""

    strongest_claims: list[str] = Field(default_factory=list)
    biggest_risks: list[str] = Field(default_factory=list)
    follow_up: FollowUpRequest = Field(default_factory=lambda: FollowUpRequest(needs_followup=False))
