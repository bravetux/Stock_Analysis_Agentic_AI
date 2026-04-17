from datetime import datetime, timezone
from unittest.mock import patch

from src.tools.macro_tools import IndicatorReading, MacroSnapshot


def _r(code, value, d1=None, w1=None, m1=None, label=None):
    return IndicatorReading(
        code=code, label=label or code, value=value,
        d1_pct=d1, w1_pct=w1, m1_pct=m1,
        regime=None, source="test",
        as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )


def test_render_market_regime_block_includes_all_present_indicators():
    from src.agents.lead_researcher import render_market_regime_block
    snap = MacroSnapshot(
        as_of=datetime(2026, 4, 17, 14, 5, tzinfo=timezone.utc),
        indicators={
            "USDINR":   _r("USDINR",   86.15, d1=1.1, w1=1.1),
            "BRENT":    _r("BRENT",    82.4,  w1=4.8),
            "INDIAVIX": _r("INDIAVIX", 14.2),
            "NIFTY50":  _r("NIFTY50",  24150, d1=0.3, w1=-1.2),
        },
        missing=["FEDFUNDS"],
    )
    block = render_market_regime_block(snap)
    assert "Market Regime" in block
    assert "USDINR" in block or "USD/INR" in block
    assert "MISSING: FEDFUNDS" in block
    assert "Do NOT cite macro as a thesis driver" in block


def test_render_market_regime_block_empty_snapshot_returns_unavailable_notice():
    from src.agents.lead_researcher import render_market_regime_block
    snap = MacroSnapshot(
        as_of=datetime.now(timezone.utc), indicators={}, missing=[],
    )
    block = render_market_regime_block(snap)
    assert "unavailable" in block.lower()


@patch("src.agents.lead_researcher.fetch_macro_snapshot")
def test_lead_researcher_disabled_flag_skips_fetch(mock_fetch, monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "enable_macro_context", False)
    from src.agents.lead_researcher import get_snapshot_or_empty
    snap = get_snapshot_or_empty()
    mock_fetch.assert_not_called()
    assert snap.indicators == {}


@patch("src.agents.lead_researcher.fetch_macro_snapshot")
def test_get_snapshot_or_empty_swallows_fetch_exceptions(mock_fetch, monkeypatch):
    from src.config.settings import settings
    monkeypatch.setattr(settings, "enable_macro_context", True)
    mock_fetch.side_effect = RuntimeError("boom")
    from src.agents.lead_researcher import get_snapshot_or_empty
    snap = get_snapshot_or_empty()
    assert snap.indicators == {}
    assert "__fetch_failed__" in snap.missing
