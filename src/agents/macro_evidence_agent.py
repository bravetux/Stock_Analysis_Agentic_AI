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
# Developed: 17th April 2026

"""Deterministic (no-LLM) agent: MacroSnapshot → list[Evidence].

Rule thresholds mirror §4.3 of the Phase 2a spec. Zero marginal cost per
ticker — safe to run on every stock in a batch."""

from __future__ import annotations

from datetime import datetime, timezone
from src.agents.evidence import Evidence, Signal
from src.tools.macro_tools import MacroSnapshot


def _ev(claim: str, signal: Signal, confidence: float, code: str, data: dict) -> Evidence:
    return Evidence(
        thread_id="macro",
        claim=claim,
        signal=signal,
        confidence=confidence,
        weight=1.0,
        source_tool="macro_snapshot",
        source_args={"indicator": code},
        observed_at=datetime.now(timezone.utc),
        data=data,
        caveats=[],
    )


def emit_macro_evidence(snapshot: MacroSnapshot) -> list[Evidence]:
    """Apply the rule table and produce zero or more Evidence records."""
    out: list[Evidence] = []
    ind = snapshot.indicators

    if "USDINR" in ind:
        r = ind["USDINR"]
        if r.d1_pct is not None and r.d1_pct >= 1.0:
            out.append(_ev(
                f"Rupee weakening: USDINR +{r.d1_pct:.2f}% in 1 day (₹{r.value:.2f})",
                Signal.BEARISH, 0.55, "USDINR",
                {"value": r.value, "d1_pct": r.d1_pct, "regime": "weakening_rupee"},
            ))
        elif r.d1_pct is not None and r.d1_pct <= -1.0:
            out.append(_ev(
                f"Rupee strengthening: USDINR {r.d1_pct:.2f}% in 1 day (₹{r.value:.2f})",
                Signal.BULLISH, 0.5, "USDINR",
                {"value": r.value, "d1_pct": r.d1_pct, "regime": "strengthening_rupee"},
            ))

    if "INDIAVIX" in ind:
        r = ind["INDIAVIX"]
        if r.value >= 20.0:
            out.append(_ev(
                f"Risk-off regime: India VIX at {r.value:.1f} (>=20)",
                Signal.BEARISH, 0.6, "INDIAVIX",
                {"value": r.value, "regime": "risk_off"},
            ))

    if "BRENT" in ind:
        r = ind["BRENT"]
        if r.w1_pct is not None and r.w1_pct >= 5.0:
            out.append(_ev(
                f"Oil spike: Brent +{r.w1_pct:.1f}% WoW (${r.value:.2f}) — headwind for OMCs / aviation / paints",
                Signal.BEARISH, 0.55, "BRENT",
                {"value": r.value, "w1_pct": r.w1_pct, "regime": "oil_spike"},
            ))
        elif r.w1_pct is not None and r.w1_pct <= -5.0:
            out.append(_ev(
                f"Oil slump: Brent {r.w1_pct:.1f}% WoW (${r.value:.2f}) — tailwind for OMCs / aviation",
                Signal.BULLISH, 0.5, "BRENT",
                {"value": r.value, "w1_pct": r.w1_pct, "regime": "oil_slump"},
            ))

    if "NIFTY50" in ind:
        r = ind["NIFTY50"]
        if r.m1_pct is not None and r.m1_pct <= -5.0:
            out.append(_ev(
                f"Market correction: Nifty 50 {r.m1_pct:.1f}% MoM",
                Signal.BEARISH, 0.55, "NIFTY50",
                {"value": r.value, "m1_pct": r.m1_pct, "regime": "correction"},
            ))

    if "DXY" in ind:
        r = ind["DXY"]
        if r.m1_pct is not None and r.m1_pct >= 3.0:
            out.append(_ev(
                f"Strong dollar: DXY +{r.m1_pct:.1f}% MoM — EM outflow risk",
                Signal.BEARISH, 0.45, "DXY",
                {"value": r.value, "m1_pct": r.m1_pct, "regime": "strong_dollar"},
            ))

    return out
