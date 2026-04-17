# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Investigator wrapper: turns any toolset into an Evidence-emitting sub-agent.

Given a set of tools and a thread_id, build a single-purpose Strands agent
whose system prompt forces it to answer ONE question and return a JSON array
of Evidence objects. Parse, validate, return list[Evidence].

This is what the research-agent pattern really needs. The existing
create_technical_agent / create_news_agent / etc. factories produce
markdown-emitting agents — this file produces evidence-emitting ones.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable

from pydantic import ValidationError
from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager

from src.agents.evidence import Evidence, ThreadSpec
from src.config.aws_client import get_bedrock_session
from src.config.prompts import INVESTIGATOR_TEMPLATE
from src.config.settings import settings

logger = logging.getLogger(__name__)


_JSON_ARRAY_RE = re.compile(r"\[\s*\{.*?\}\s*\]", re.DOTALL)


def _extract_json_array(text: str) -> list[dict] | None:
    """Pull the first JSON array of objects out of a string.

    Tolerant of markdown fences and surrounding prose — we try the obvious
    shape first, then fall back to regex.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    m = _JSON_ARRAY_RE.search(text)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _parse_evidence(text: str, thread_id: str) -> list[Evidence]:
    """Parse raw LLM output into validated Evidence, dropping malformed entries."""
    raw = _extract_json_array(text)
    if raw is None:
        logger.warning("Investigator %s produced no parseable JSON array", thread_id)
        return []

    result: list[Evidence] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        item.setdefault("thread_id", thread_id)
        try:
            result.append(Evidence.model_validate(item))
        except ValidationError as e:
            logger.warning(
                "Investigator %s evidence[%d] failed validation: %s", thread_id, idx, e
            )
    return result


def build_investigator_agent(
    tools: list[Callable],
    thread_id: str,
    spec: ThreadSpec,
    ticker: str,
    exchange: str,
) -> Agent:
    """Assemble a single-objective agent for one investigation thread."""
    system_prompt = INVESTIGATOR_TEMPLATE.format(
        thread_id=thread_id,
        objective=spec.objective,
        budget=spec.budget_tool_calls,
        ticker=ticker,
        exchange=exchange,
    )

    model = BedrockModel(
        boto_session=get_bedrock_session(),
        model_id=settings.bedrock_model_id,
        temperature=settings.agent_temperature,
        top_p=settings.agent_top_p,
        max_tokens=settings.agent_max_tokens,
    )

    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        conversation_manager=SlidingWindowConversationManager(window_size=8),
    )


def run_investigator(
    tools: list[Callable],
    spec: ThreadSpec,
    ticker: str,
    exchange: str,
    on_tool_start: Callable[[str], None] | None = None,
    on_tool_end: Callable[[str, float], None] | None = None,
) -> list[Evidence]:
    """Run one investigation thread and return validated Evidence.

    Synchronous. The caller is expected to wrap this in asyncio.to_thread for
    parallel dispatch.
    """
    import time
    from strands.hooks import BeforeToolCallEvent, AfterToolCallEvent

    agent = build_investigator_agent(tools, spec.thread_id, spec, ticker, exchange)
    query = f"Investigate {ticker} on {exchange}. Objective: {spec.objective}"

    _starts: dict[str, float] = {}

    def _name(tu):
        if tu is None:
            return "unknown"
        if isinstance(tu, dict):
            return tu.get("name", "unknown")
        return getattr(tu, "name", "unknown")

    def _before(event):
        n = _name(event.tool_use)
        _starts[n] = time.time()
        if on_tool_start:
            on_tool_start(f"[{spec.thread_id}] {n}")

    def _after(event):
        n = _name(event.tool_use)
        elapsed = time.time() - _starts.pop(n, time.time())
        if on_tool_end:
            on_tool_end(f"[{spec.thread_id}] {n}", elapsed)

    try:
        agent.add_hook(_before, BeforeToolCallEvent)
        agent.add_hook(_after, AfterToolCallEvent)
    except (AttributeError, TypeError):
        pass

    try:
        response = agent(query)
    except Exception as e:
        logger.exception("Investigator %s failed: %s", spec.thread_id, e)
        return [
            Evidence(
                thread_id=spec.thread_id,
                claim=f"Investigator failed: {e}",
                signal="inconclusive",  # type: ignore[arg-type]
                confidence=0.0,
                weight=0.0,
                source_tool="investigator_error",
                caveats=[str(e)],
            )
        ]

    text = str(response)
    evidence = _parse_evidence(text, spec.thread_id)
    if not evidence:
        logger.warning(
            "Investigator %s produced no evidence. Raw output head: %s",
            spec.thread_id,
            text[:300],
        )
        return [
            Evidence(
                thread_id=spec.thread_id,
                claim=f"Investigator {spec.thread_id} returned no parseable evidence",
                signal="inconclusive",  # type: ignore[arg-type]
                confidence=0.0,
                weight=0.0,
                source_tool="investigator_parse_failure",
                caveats=["response was not a JSON array of Evidence objects"],
                data={"raw_head": text[:500]},
            )
        ]

    return evidence
