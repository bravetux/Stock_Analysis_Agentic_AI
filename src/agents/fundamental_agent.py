# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Author: B.Vignesh Kumar aka Bravetux
# Email:  ic19939@gmail.com
# Developed: 10th April 2026

from datetime import datetime, timezone

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.agents.evidence import Evidence, Signal
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import FUNDAMENTAL_AGENT_PROMPT
from src.tools.screener_tools import scrape_screener_in
from src.tools.market_data_tools import get_stock_quote, get_historical_data
from src.tools.fundamental_tools import (
    get_insider_transactions,
    get_mutual_fund_holdings,
    get_earnings_calendar,
)
from src.tools.macro_tools import fetch_analyst_consensus


def create_fundamental_agent() -> Agent:
    """Create the Fundamental Analysis specialist agent."""
    model = BedrockModel(
        boto_session=get_bedrock_session(),
        model_id=settings.bedrock_model_id,
        temperature=settings.agent_temperature,
        top_p=settings.agent_top_p,
        max_tokens=settings.agent_max_tokens,
    )

    return Agent(
        model=model,
        tools=[
            scrape_screener_in,
            get_stock_quote,
            get_historical_data,
            get_insider_transactions,
            get_mutual_fund_holdings,
            get_earnings_calendar,
        ],
        system_prompt=FUNDAMENTAL_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )


def _analyst_ev(claim: str, signal: Signal, conf: float, data: dict) -> Evidence:
    return Evidence(
        thread_id="fundamental",
        claim=claim,
        signal=signal,
        confidence=conf,
        weight=1.0,
        source_tool="analyst_consensus",
        source_args={},
        observed_at=datetime.now(timezone.utc),
        data=data,
        caveats=[],
    )


def emit_analyst_evidence(ticker: str, exchange: str) -> list[Evidence]:
    """Deterministic analyst-consensus evidence. Flag-gated via settings.enable_analyst_consensus."""
    if not settings.enable_analyst_consensus:
        return []
    c = fetch_analyst_consensus(ticker, exchange)
    if c.total_analysts == 0 and c.mean_target is None:
        return [_analyst_ev(
            "Analyst consensus unavailable for this ticker",
            Signal.INCONCLUSIVE, 0.3,
            {"reason": "no_coverage"},
        )]
    out: list[Evidence] = []
    if c.mean_target is not None and c.current_price > 0 and c.implied_upside_pct is not None:
        sig = Signal.BULLISH if c.implied_upside_pct > 0 else Signal.BEARISH
        out.append(_analyst_ev(
            f"Street target ₹{c.mean_target:.2f} vs current ₹{c.current_price:.2f} "
            f"(implied upside {c.implied_upside_pct:+.2f}%)",
            sig, 0.55,
            {
                "mean_target": c.mean_target, "current_price": c.current_price,
                "implied_upside_pct": c.implied_upside_pct,
            },
        ))
    if c.total_analysts > 0:
        total = c.total_analysts
        if c.buy / total >= 0.6:
            sig = Signal.BULLISH
        elif c.sell / total >= 0.3:
            sig = Signal.BEARISH
        else:
            sig = Signal.NEUTRAL
        out.append(_analyst_ev(
            f"Analyst ratings: {c.buy} Buy / {c.hold} Hold / {c.sell} Sell "
            f"({total} analysts)",
            sig, 0.5,
            {"buy": c.buy, "hold": c.hold, "sell": c.sell, "total": total},
        ))
    if c.revision_30d["raised"] + c.revision_30d["cut"] > 0:
        trend = c.recommendation_trend
        sig = {
            "strengthening_buy": Signal.BULLISH,
            "cooling": Signal.BEARISH,
            "weakening": Signal.BEARISH,
            "stable": Signal.NEUTRAL,
        }.get(trend, Signal.NEUTRAL)
        out.append(_analyst_ev(
            f"Last 30d revisions: {c.revision_30d['raised']} raised / "
            f"{c.revision_30d['cut']} cut → {trend}",
            sig, 0.5,
            dict(c.revision_30d, trend=trend),
        ))
    return out
