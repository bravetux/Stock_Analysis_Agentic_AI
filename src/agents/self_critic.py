# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Self-Critic: StockThesis -> CritiqueReport (+ optional FollowUpRequest).

Single Claude call. Tries to break the thesis and, if a specific data gap
would meaningfully change the signal, requests one targeted follow-up
investigation (hard-capped by settings.max_followup_loops).
"""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from src.agents.bedrock_call import converse_json
from src.agents.evidence import CritiqueReport, FollowUpRequest, StockThesis
from src.agents.thread_registry import ALLOWED_THREAD_IDS
from src.config.prompts import SELF_CRITIC_PROMPT
from src.config.settings import settings

logger = logging.getLogger(__name__)


def critique(thesis: StockThesis) -> CritiqueReport:
    thesis_json = json.dumps(thesis.model_dump(mode="json"), ensure_ascii=False, default=str)
    system = "You are a skeptical equity analyst who stress-tests theses. Return only the requested JSON."
    user = SELF_CRITIC_PROMPT.format(thesis_json=thesis_json)

    parsed = converse_json(system, user, temperature=settings.synthesizer_temperature)
    if not isinstance(parsed, dict):
        return CritiqueReport()

    try:
        report = CritiqueReport.model_validate(parsed)
    except ValidationError as e:
        logger.warning("Self-critic JSON failed validation: %s", e)
        return CritiqueReport()

    # Sanitize follow-up: thread_id must be one we know how to run.
    fu = report.follow_up
    if fu.needs_followup and (
        fu.thread_id not in ALLOWED_THREAD_IDS or not fu.objective
    ):
        logger.info(
            "Self-critic requested invalid follow-up (thread_id=%s); ignoring", fu.thread_id
        )
        report.follow_up = FollowUpRequest(needs_followup=False)

    return report
