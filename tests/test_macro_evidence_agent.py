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

"""Tests for deterministic macro_evidence_agent."""

from datetime import datetime, timezone
from src.tools.macro_tools import IndicatorReading, MacroSnapshot
from src.agents.macro_evidence_agent import emit_macro_evidence
from src.agents.evidence import Signal


def _r(code, value, d1=None, w1=None, m1=None):
    return IndicatorReading(
        code=code, label=code, value=value,
        d1_pct=d1, w1_pct=w1, m1_pct=m1,
        regime=None, source="test",
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )


def _snap(readings):
    return MacroSnapshot(
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
        indicators={r.code: r for r in readings},
        missing=[],
    )


def test_empty_snapshot_yields_no_evidence():
    ev = emit_macro_evidence(_snap([]))
    assert ev == []


def test_usdinr_weakening_emits_bearish():
    ev = emit_macro_evidence(_snap([_r("USDINR", 86.15, d1=1.2)]))
    usdinr_ev = [e for e in ev if "USDINR" in e.claim or "rupee" in e.claim.lower()]
    assert any(e.signal == Signal.BEARISH for e in usdinr_ev)


def test_vix_above_20_emits_bearish_risk_off():
    ev = emit_macro_evidence(_snap([_r("INDIAVIX", 22.0)]))
    vix_ev = [e for e in ev if "VIX" in e.claim or "risk" in e.claim.lower()]
    assert any(e.signal == Signal.BEARISH for e in vix_ev)


def test_vix_at_19_9_emits_no_risk_off_evidence():
    ev = emit_macro_evidence(_snap([_r("INDIAVIX", 19.9)]))
    risk_off = [e for e in ev if "risk" in e.claim.lower() or "risk_off" in (e.data or {}).get("regime", "")]
    assert risk_off == []


def test_brent_weekly_spike_emits_bearish_for_sector_headwinds():
    ev = emit_macro_evidence(_snap([_r("BRENT", 92.0, w1=6.0)]))
    assert any(e.signal == Signal.BEARISH for e in ev)


def test_every_emitted_evidence_has_thread_id_macro_and_source_tool():
    ev = emit_macro_evidence(_snap([
        _r("USDINR", 86.0, d1=1.5),
        _r("INDIAVIX", 22.0),
        _r("BRENT", 90.0, w1=6.0),
    ]))
    assert all(e.thread_id == "macro" for e in ev)
    assert all(e.source_tool == "macro_snapshot" for e in ev)
