from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from src.db.macro_store import MacroStore
from src.tools.macro_tools import IndicatorReading, MacroSnapshot


def _reading(code="USDINR", value=86.0, as_of=None):
    if as_of is None:
        as_of = datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
    return IndicatorReading(
        code=code, label=code, value=value,
        d1_pct=0.0, w1_pct=0.0, m1_pct=0.0,
        regime=None, source="yfinance", as_of=as_of,
    )


@pytest.fixture
def store(tmp_path: Path):
    return MacroStore(db_path=str(tmp_path / "macro.db"))


def test_insert_and_get_latest(store):
    snap = MacroSnapshot(
        as_of=datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc),
        indicators={"USDINR": _reading(value=86.15)},
        missing=[],
    )
    store.insert_snapshot(snap)
    latest = store.get_latest("USDINR")
    assert latest is not None
    assert latest.value == 86.15


def test_get_latest_missing_indicator(store):
    assert store.get_latest("USDINR") is None


def test_get_value_n_days_ago_weekend_aware(store):
    # Insert readings Fri/Sat not inserted/Sun not inserted/Mon
    fri = datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc)  # Friday
    mon = datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc)  # Monday
    store.insert_snapshot(MacroSnapshot(
        as_of=fri, indicators={"USDINR": _reading(value=85.0, as_of=fri)}, missing=[],
    ))
    store.insert_snapshot(MacroSnapshot(
        as_of=mon, indicators={"USDINR": _reading(value=86.0, as_of=mon)}, missing=[],
    ))
    # "value 1 day ago" from Monday = nearest prior row = Friday's
    # (not None, because weekends have no rows)
    got = store.get_value_n_days_ago("USDINR", 1, reference=mon)
    assert got == 85.0


def test_get_value_n_days_ago_no_history(store):
    assert store.get_value_n_days_ago("USDINR", 1) is None


def test_prune_removes_old_rows(store):
    old = datetime.now(timezone.utc) - timedelta(days=200)
    recent = datetime.now(timezone.utc) - timedelta(days=3)
    store.insert_snapshot(MacroSnapshot(
        as_of=old, indicators={"USDINR": _reading(as_of=old)}, missing=[],
    ))
    store.insert_snapshot(MacroSnapshot(
        as_of=recent, indicators={"USDINR": _reading(as_of=recent)}, missing=[],
    ))
    removed = store.prune(retention_days=90)
    assert removed == 1
    latest = store.get_latest("USDINR")
    assert latest is not None
    assert abs((latest.as_of - recent).total_seconds()) < 60


def test_fresh_within_window(store):
    now = datetime.now(timezone.utc)
    store.insert_snapshot(MacroSnapshot(
        as_of=now, indicators={"USDINR": _reading(as_of=now)}, missing=[],
    ))
    assert store.is_fresh("USDINR", max_age_minutes=60) is True


def test_stale_beyond_window(store):
    old = datetime.now(timezone.utc) - timedelta(minutes=90)
    store.insert_snapshot(MacroSnapshot(
        as_of=old, indicators={"USDINR": _reading(as_of=old)}, missing=[],
    ))
    assert store.is_fresh("USDINR", max_age_minutes=60) is False
