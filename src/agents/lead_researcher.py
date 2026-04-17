# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""LeadResearcher: orchestrates the Claude-style investigation loop.

Flow:
  1. plan(ticker, exchange)               -> ResearchPlan
  2. gather(plan)                          -> list[Evidence]   (parallel)
  3. synthesize(evidence)                  -> StockThesis
  4. critique(thesis)                      -> CritiqueReport
  5. if follow_up requested and budget left:
       run that one narrow investigator, re-synthesize, return
  6. return StockThesis

The critical design choice: every downstream consumer (UI, PDF, SQLite cache,
batch XLSX) reads StockThesis, not markdown. This kills the
LLM-parses-its-own-output anti-pattern that the current batch path depends on.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Callable

from pydantic import ValidationError

from src.agents.bedrock_call import converse_json
from src.agents.evidence import (
    CritiqueReport,
    Evidence,
    ResearchPlan,
    StockThesis,
    ThreadSpec,
)
from src.agents.fundamental_agent import emit_analyst_evidence
from src.agents.investigator import run_investigator
from src.agents.macro_evidence_agent import emit_macro_evidence
from src.agents.self_critic import critique
from src.agents.synthesizer import synthesize
from src.agents.thread_registry import (
    ALLOWED_THREAD_IDS,
    get_tools_for_thread,
)
from src.config.prompts import PLANNER_PROMPT
from src.config.settings import settings
from src.tools.macro_tools import MacroSnapshot, fetch_macro_snapshot

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Plan
# ----------------------------------------------------------------------------

_DEFAULT_PLAN_THREADS: list[dict] = [
    {"thread_id": "technical", "objective": "What is the current trend, momentum, and where are the key price levels?", "priority": "high", "budget_tool_calls": 6},
    {"thread_id": "fundamental", "objective": "Is the stock cheap, fair, or expensive relative to its growth and balance sheet quality?", "priority": "high", "budget_tool_calls": 4},
    {"thread_id": "news", "objective": "What recent events or catalysts matter for this stock over the next 1-3 months?", "priority": "medium", "budget_tool_calls": 3},
    {"thread_id": "institutional", "objective": "Are insiders and institutions accumulating or distributing?", "priority": "medium", "budget_tool_calls": 3},
    {"thread_id": "macro_sector", "objective": "Is the sector in favor and does this stock lead or lag its peers?", "priority": "medium", "budget_tool_calls": 3},
    {"thread_id": "risk_options", "objective": "What is the risk profile (drawdown, beta, VaR) and what is options market sentiment if available?", "priority": "low", "budget_tool_calls": 3},
]


def _default_plan(ticker: str, exchange: str) -> ResearchPlan:
    return ResearchPlan(
        ticker=ticker,
        exchange=exchange,
        horizon="medium",
        framing="Default plan: full six-thread sweep. Used when the planner call fails or is skipped.",
        threads=[ThreadSpec.model_validate(t) for t in _DEFAULT_PLAN_THREADS],
    )


def plan_research(ticker: str, exchange: str) -> ResearchPlan:
    """Ask the planner to decompose the stock into investigation threads."""
    system = "You are a senior equity research lead. Return only the requested JSON object."
    user = PLANNER_PROMPT.format(ticker=ticker, exchange=exchange)

    parsed = converse_json(system, user, temperature=settings.lead_temperature)
    if not isinstance(parsed, dict):
        logger.info("Planner returned non-dict; using default plan")
        return _default_plan(ticker, exchange)

    parsed.setdefault("ticker", ticker)
    parsed.setdefault("exchange", exchange)

    try:
        plan = ResearchPlan.model_validate(parsed)
    except ValidationError as e:
        logger.warning("Planner JSON failed validation (%s); using default plan", e)
        return _default_plan(ticker, exchange)

    # Drop threads the registry doesn't know how to run.
    good_threads = [t for t in plan.threads if t.thread_id in ALLOWED_THREAD_IDS]
    if not good_threads:
        logger.warning("Planner produced zero valid threads; using default plan")
        return _default_plan(ticker, exchange)

    if len(good_threads) > settings.research_max_threads:
        # Prefer higher priority.
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        good_threads.sort(key=lambda t: priority_rank.get(t.priority, 3))
        good_threads = good_threads[: settings.research_max_threads]

    plan.threads = good_threads
    return plan


# ----------------------------------------------------------------------------
# Gather
# ----------------------------------------------------------------------------


async def _gather_async(
    plan: ResearchPlan,
    on_tool_start: Callable[[str], None] | None,
    on_tool_end: Callable[[str, float], None] | None,
    on_thread_done: Callable[[str, int], None] | None,
) -> list[Evidence]:
    """Run all investigators concurrently via asyncio.to_thread."""
    timeout = settings.investigator_timeout_s

    async def _one(spec: ThreadSpec) -> list[Evidence]:
        tools = get_tools_for_thread(spec.thread_id)
        if not tools:
            logger.warning("No tools registered for thread %s", spec.thread_id)
            return []
        try:
            ev = await asyncio.wait_for(
                asyncio.to_thread(
                    run_investigator,
                    tools,
                    spec,
                    plan.ticker,
                    plan.exchange,
                    on_tool_start,
                    on_tool_end,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Investigator %s timed out after %ds", spec.thread_id, timeout)
            ev = []
        except Exception as e:
            logger.exception("Investigator %s raised: %s", spec.thread_id, e)
            ev = []

        if on_thread_done:
            try:
                on_thread_done(spec.thread_id, len(ev))
            except Exception:
                pass
        return ev

    results = await asyncio.gather(*(_one(t) for t in plan.threads))
    flat: list[Evidence] = []
    for r in results:
        flat.extend(r)
    return flat


def gather(
    plan: ResearchPlan,
    on_tool_start: Callable[[str], None] | None = None,
    on_tool_end: Callable[[str, float], None] | None = None,
    on_thread_done: Callable[[str, int], None] | None = None,
) -> list[Evidence]:
    """Synchronous wrapper around the async gather loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    coro = _gather_async(plan, on_tool_start, on_tool_end, on_thread_done)

    if loop is None:
        return asyncio.run(coro)

    # If we are already inside an event loop (unlikely in Streamlit but possible
    # in notebooks), run the coroutine on a fresh loop in another thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


# ----------------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------------


def get_snapshot_or_empty() -> MacroSnapshot:
    """Fetch macro snapshot if feature flag enabled; else return an empty one.
    Never raises."""
    from datetime import datetime, timezone
    if not settings.enable_macro_context:
        return MacroSnapshot(as_of=datetime.now(timezone.utc), indicators={}, missing=[])
    try:
        return fetch_macro_snapshot(use_cache=True)
    except Exception:
        return MacroSnapshot(
            as_of=datetime.now(timezone.utc),
            indicators={},
            missing=["__fetch_failed__"],
        )


def render_market_regime_block(snapshot: MacroSnapshot) -> str:
    """Render the Lead Researcher 'Market Regime' context block.
    The final guardrail line is load-bearing — do NOT remove."""
    if not snapshot.indicators:
        return (
            "## Market Regime\n\n"
            "*Macro context unavailable for this run. Proceed with stock-level evidence only.*\n"
        )
    lines = [f"## Market Regime (as of {snapshot.as_of:%Y-%m-%d %H:%M UTC})", ""]
    order = ["NIFTY50", "SENSEX", "INDIAVIX", "USDINR", "BRENT", "DXY",
             "BANKNIFTY", "GOLD_INR", "INDIA10Y", "FEDFUNDS"]
    for code in order:
        r = snapshot.indicators.get(code)
        if r is None:
            continue
        deltas = []
        if r.d1_pct is not None:
            deltas.append(f"{r.d1_pct:+.2f}% 1D")
        if r.w1_pct is not None:
            deltas.append(f"{r.w1_pct:+.2f}% 1W")
        if r.m1_pct is not None:
            deltas.append(f"{r.m1_pct:+.2f}% 1M")
        delta_str = f" ({', '.join(deltas)})" if deltas else ""
        regime_str = f" — {r.regime.replace('_', ' ')}" if r.regime else ""
        lines.append(f"- **{r.label}:** {r.value:,.2f}{delta_str}{regime_str}")
    if snapshot.missing:
        lines.append("")
        lines.append(f"[MISSING: {', '.join(snapshot.missing)}]")
    lines.append("")
    lines.append(
        "Use this context ONLY when sector-relevant. Do NOT cite macro as "
        "a thesis driver unless the stock is demonstrably sensitive to it."
    )
    return "\n".join(lines)


def research_stock(
    ticker: str,
    exchange: str,
    *,
    on_plan: Callable[[ResearchPlan], None] | None = None,
    on_tool_start: Callable[[str], None] | None = None,
    on_tool_end: Callable[[str, float], None] | None = None,
    on_thread_done: Callable[[str, int], None] | None = None,
    on_synthesize_start: Callable[[], None] | None = None,
    on_critique_start: Callable[[], None] | None = None,
    on_followup: Callable[[str, str], None] | None = None,
) -> tuple[StockThesis, ResearchPlan, list[Evidence], CritiqueReport, MacroSnapshot]:
    """Run the full research loop and return (thesis, plan, evidence, critique, macro_snapshot).

    All callbacks are optional; they exist so the UI can show live progress.
    The returned MacroSnapshot may have empty indicators if flag is disabled
    or fetching failed — callers should treat it defensively.
    """
    t0 = time.time()
    macro_snapshot = get_snapshot_or_empty()
    plan = plan_research(ticker, exchange)
    if on_plan:
        on_plan(plan)
    logger.info("Plan built for %s:%s with %d threads in %.2fs", exchange, ticker, len(plan.threads), time.time() - t0)

    evidence = gather(plan, on_tool_start, on_tool_end, on_thread_done)
    # Append deterministic macro + analyst-consensus evidence (flag-gated, never raises).
    try:
        evidence = evidence + emit_macro_evidence(macro_snapshot)
    except Exception as e:
        logger.warning("emit_macro_evidence failed: %s", e)
    try:
        evidence = evidence + emit_analyst_evidence(ticker, exchange)
    except Exception as e:
        logger.warning("emit_analyst_evidence failed: %s", e)
    logger.info("Gathered %d evidence items for %s:%s", len(evidence), exchange, ticker)

    if on_synthesize_start:
        on_synthesize_start()
    thesis = synthesize(ticker, exchange, evidence)

    if on_critique_start:
        on_critique_start()
    critique_report = critique(thesis)

    # Follow-up loop (at most settings.max_followup_loops).
    if (
        settings.max_followup_loops > 0
        and critique_report.follow_up.needs_followup
        and critique_report.follow_up.thread_id in ALLOWED_THREAD_IDS
        and critique_report.follow_up.objective
    ):
        fu_thread = critique_report.follow_up.thread_id
        fu_objective = critique_report.follow_up.objective
        if on_followup:
            on_followup(fu_thread, fu_objective)
        logger.info("Running follow-up investigation: %s — %s", fu_thread, fu_objective)

        spec = ThreadSpec(
            thread_id=fu_thread,
            objective=fu_objective,
            priority="high",
            budget_tool_calls=4,
        )
        tools = get_tools_for_thread(fu_thread)
        try:
            extra = run_investigator(tools, spec, ticker, exchange, on_tool_start, on_tool_end)
            if extra:
                evidence = evidence + extra
                thesis = synthesize(ticker, exchange, evidence)
        except Exception as e:
            logger.exception("Follow-up investigator failed: %s", e)

    return thesis, plan, evidence, critique_report, macro_snapshot


def thesis_to_dict(thesis: StockThesis) -> dict:
    """Convenience: JSON-safe dict of a StockThesis (dates as ISO strings)."""
    return json.loads(thesis.model_dump_json())
