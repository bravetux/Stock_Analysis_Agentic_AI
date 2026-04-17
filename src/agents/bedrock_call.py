# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Thin boto3 Bedrock Converse wrapper for pure-reasoning Claude calls.

Planner, Synthesizer, and Self-Critic are tool-less — they just take structured
input and produce structured JSON. A Strands Agent is overkill for that; this
helper keeps those code paths short and lets us control temperature per role.
"""

from __future__ import annotations

import json
import logging
import re

from src.config.aws_client import get_bedrock_session
from src.config.settings import settings

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def converse(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Single-turn Claude call via Bedrock Converse.

    Returns the raw text content of the first message. Caller handles parsing.
    """
    session = get_bedrock_session()
    client = session.client("bedrock-runtime")

    inference_config = {
        "maxTokens": max_tokens or settings.agent_max_tokens,
        "temperature": temperature if temperature is not None else settings.agent_temperature,
        "topP": settings.agent_top_p,
    }

    response = client.converse(
        modelId=settings.bedrock_model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_prompt}]}],
        inferenceConfig=inference_config,
    )

    try:
        blocks = response["output"]["message"]["content"]
        parts = [b.get("text", "") for b in blocks if "text" in b]
        return "".join(parts)
    except (KeyError, TypeError) as e:
        logger.error("Unexpected Bedrock response shape: %s", e)
        return ""


def converse_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict | list | None:
    """Same as converse() but strips fences and parses JSON. Returns None on failure."""
    raw = converse(
        system_prompt,
        user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if not raw:
        return None
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        logger.warning("Bedrock returned non-JSON: %s. Head: %s", e, raw[:300])
        return None
