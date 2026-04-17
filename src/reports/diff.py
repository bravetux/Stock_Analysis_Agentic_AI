# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
# Licensed under GNU GPL v3 or later.

"""Compute a structured, heading-aware diff between two stock-analysis
reports.

The old History-page Compare button dumped the two reports side by side
and left the reader to eyeball 5,000 words for differences. Blind
line-level diffs are just as noisy, because the LLM rewrites wording on
every run even when the substance is the same.

This module works at the level the user actually cares about:

  1. ``extract_fields``     — pull headline metrics (Signal, Conviction,
                              Current Price, 200DMA, PE, …) from either
                              engine's markdown.
  2. ``compare_fields``     — build a field-level change table with
                              numeric deltas and categorical transitions.
  3. ``split_by_heading``   — parse a markdown report into a hierarchical
                              list of sections keyed by heading path
                              (``"Technical / MACD"``).
  4. ``compare_sections``   — align sections by heading, classify each as
                              unchanged / changed / added / removed.
  5. ``build_ai_delta_prompt`` — optional LLM-narrated delta payload.

All computation is deterministic and offline. An AI summary is left to
the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------

# (canonical_name, [pattern, ...], kind)
#   num  -> float, rendered with commas; delta shown as ± absolute + ±%
#   pct  -> float already in percent; delta shown as ±pp
#   enum -> uppercased category (BULLISH / NEUTRAL / ...); equality only
#   text -> raw string, equality only
_FIELD_SPECS: list[tuple[str, list[str], str]] = [
    ("Signal", [
        r"\*\*Signal:\*\*\s*(?:[^\w\s]+\s*)?([A-Z]+)",
        r"Composite\s+Score\s+Signal[:\s]*\d+(?:\.\d+)?/\d+\s*\(([A-Z ]+)\)",
        r"Overall\s+Signal[:\s]*\**\s*([A-Z]+)",
    ], "enum"),
    ("Conviction", [
        r"\*\*Conviction:\*\*\s*([\d.]+)%",
    ], "pct"),
    ("Composite Score", [
        r"Composite\s+Score[^0-9]*([\d.]+)\s*/\s*10",
        r"Composite\s+Score[:\s|]*\**\s*([\d.]+)",
    ], "num"),
    ("Current Price", [
        r"current_price\s*\|\s*([\d,]+(?:\.\d+)?)",
        r"Current\s+Price[^\d₹$]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
        r"Stock\s+Price[^\d₹$]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
    ], "num"),
    ("200DMA", [
        r"dma_200\s*\|\s*([\d,]+(?:\.\d+)?)",
        r"200\s*DMA[^\d]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
        r"200[-\s]?Day\s+Moving\s+Average[^\d]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
    ], "num"),
    ("Support", [
        r"\|\s*support\s*\|\s*([\d,]+(?:\.\d+)?)",
        r"Support[^\d]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
    ], "num"),
    ("Resistance", [
        r"\|\s*resistance\s*\|\s*([\d,]+(?:\.\d+)?)",
        r"Resistance[^\d]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
    ], "num"),
    ("Base Target", [
        r"\|\s*base\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)",
        r"Target\s+Price[^\d]*[₹$]?\s*([\d,]+(?:\.\d+)?)",
    ], "num"),
    ("Bull Target", [r"\|\s*bull\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)"], "num"),
    ("Bear Target", [r"\|\s*bear\s*\|[^|]*\|\s*([\d,]+(?:\.\d+)?)"], "num"),
    ("MACD Status", [
        r"MACD[^\|]*\|\s*(BULLISH|BEARISH|NEUTRAL)",
        r"MACD[^:]*Status[:\s*]*\**\s*(BULLISH|BEARISH|NEUTRAL)",
    ], "enum"),
    ("EMA Trend", [
        r"EMA[^\|]*\|\s*(BULLISH|BEARISH|NEUTRAL)",
        r"Alignment\s+Status[:\s*]*\**\s*(BULLISH|BEARISH|NEUTRAL)",
    ], "enum"),
    ("News Sentiment", [
        r"Overall\s+Sentiment[:\s*]*\**\s*([A-Z][A-Z\s\-]+)",
        r"News\s+Sentiment[:\s*]*\**\s*([A-Z][A-Z\s\-]+)",
    ], "enum"),
    ("Risk Level", [r"Risk\s+Level[:\s*]*\**\s*([A-Z][A-Z\-]+)"], "enum"),
    ("PE Ratio", [
        r"P\.?E\s*Ratio[^\d]*([\d.]+)",
        r"P/E\s*(?:Ratio)?[^\d]*([\d.]+)",
    ], "num"),
    ("ROE", [r"ROE[^\d]*([\d.]+)"], "num"),
    ("Headline", [r"\*\*Headline:\*\*\s*(.+)"], "text"),
]


def _clean_enum(s: str) -> str:
    s = re.sub(r"\*+", "", s).strip().upper()
    parts = s.split()
    if parts and parts[0] in {"BULLISH", "BEARISH", "NEUTRAL", "POSITIVE", "NEGATIVE"}:
        return parts[0]
    return s


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def extract_fields(markdown: str) -> dict[str, tuple[str, object]]:
    """``{field: (kind, value)}`` for every spec that matched."""
    out: dict[str, tuple[str, object]] = {}
    text = markdown or ""
    for name, patterns, kind in _FIELD_SPECS:
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1).strip()
            if kind in ("num", "pct"):
                v = _to_float(raw)
                if v is None:
                    continue
                out[name] = (kind, v)
            elif kind == "enum":
                out[name] = (kind, _clean_enum(raw))
            else:
                out[name] = (kind, raw.strip())
            break
    return out


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldChange:
    field: str
    kind: str
    before: object | None
    after: object | None
    delta: float | None = None
    delta_pct: float | None = None
    direction: str = "—"            # up | down | same | changed | added | removed

    def fmt_before(self) -> str:
        return _fmt_value(self.before, self.kind)

    def fmt_after(self) -> str:
        return _fmt_value(self.after, self.kind)

    def fmt_delta(self) -> str:
        if self.kind in ("num", "pct") and self.delta is not None:
            arrow = {"up": "▲", "down": "▼", "same": "="}.get(self.direction, "")
            pct = f" ({self.delta_pct:+.1f}%)" if self.delta_pct is not None else ""
            sign = "+" if self.delta > 0 else ""
            suffix = "pp" if self.kind == "pct" else ""
            return f"{arrow} {sign}{self.delta:.2f}{suffix}{pct}".strip()
        if self.kind == "enum":
            if self.before == self.after:
                return "unchanged"
            return f"{self.before or '—'} → {self.after or '—'}"
        if self.kind == "text":
            return "changed" if self.before != self.after else "unchanged"
        return "—"


def _fmt_value(v: object | None, kind: str) -> str:
    if v is None:
        return "—"
    if kind == "pct":
        return f"{float(v):.1f}%"
    if kind == "num":
        return f"{float(v):,.2f}"
    return str(v)


def compare_fields(before_md: str, after_md: str) -> list[FieldChange]:
    bef = extract_fields(before_md)
    aft = extract_fields(after_md)

    changes: list[FieldChange] = []
    for name, _, kind in _FIELD_SPECS:
        has_b = name in bef
        has_a = name in aft
        if not (has_b or has_a):
            continue
        b_kind, b_val = bef.get(name, (kind, None))
        a_kind, a_val = aft.get(name, (kind, None))
        use_kind = b_kind if has_b else a_kind

        delta = None
        delta_pct = None
        if has_a and not has_b:
            direction = "added"
        elif has_b and not has_a:
            direction = "removed"
        elif use_kind in ("num", "pct") and isinstance(b_val, (int, float)) and isinstance(a_val, (int, float)):
            delta = float(a_val) - float(b_val)
            if abs(delta) < 1e-9:
                direction = "same"
            elif delta > 0:
                direction = "up"
            else:
                direction = "down"
            if use_kind == "num" and b_val != 0:
                delta_pct = (delta / float(b_val)) * 100.0
        else:
            direction = "same" if b_val == a_val else "changed"

        changes.append(FieldChange(
            field=name, kind=use_kind,
            before=b_val, after=a_val,
            delta=delta, delta_pct=delta_pct,
            direction=direction,
        ))
    return changes


# ---------------------------------------------------------------------------
# Heading-based section parsing and comparison
# ---------------------------------------------------------------------------


_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


def _normalise_heading(title: str) -> str:
    """Lower-case, strip emoji / bold markers / punctuation so that
    '📈 **200-DAY MOVING AVERAGE ANALYSIS**' and '200 day moving average'
    match on substance."""
    t = re.sub(r"\*+", "", title)
    # Drop non-letter/digit/space chars (kills emoji, ®, ©, etc.).
    t = re.sub(r"[^\w\s\-/&]", "", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


@dataclass
class Section:
    level: int                 # 1..6
    title: str                 # raw heading text
    key: str                   # normalised heading (used for matching)
    path: tuple[str, ...]      # ancestor chain + this heading
    body: str                  # lines between this heading and the next

    @property
    def display_path(self) -> str:
        return " / ".join(self.path)


def split_by_heading(markdown: str) -> list[Section]:
    """Parse a markdown doc into a flat list of Section objects whose
    ``path`` captures the heading hierarchy."""
    lines = (markdown or "").splitlines()
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []   # [(level, key), ...]
    cur_level: int | None = None
    cur_title = ""
    cur_key = ""
    cur_body: list[str] = []

    def _flush():
        if cur_level is None:
            return
        # Build path from stack.
        path = tuple(k for _, k in stack) or (cur_key,)
        sections.append(Section(
            level=cur_level,
            title=cur_title,
            key=cur_key,
            path=path,
            body="\n".join(cur_body).strip("\n"),
        ))

    for raw in lines:
        m = _HEADING_RE.match(raw)
        if m:
            _flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            key = _normalise_heading(title)
            # Pop stack to parent level.
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, key))
            cur_level = level
            cur_title = title
            cur_key = key
            cur_body = []
        else:
            if cur_level is None:
                # Pre-heading preamble. Attach to a virtual root section
                # so nothing is dropped silently.
                continue
            cur_body.append(raw)

    _flush()
    return sections


def _section_fingerprint(body: str) -> str:
    """Normalise a section body for equality checks: collapse whitespace,
    strip markdown emphasis markers and emoji so cosmetic re-wordings
    don't register as changes while substance changes still do."""
    if not body:
        return ""
    b = re.sub(r"\*+|_+|`+", "", body)
    b = re.sub(r"[^\w\s\-\|\.,:;/&%₹$+]", "", b, flags=re.UNICODE)
    b = re.sub(r"\s+", " ", b).strip().lower()
    return b


@dataclass(frozen=True)
class SectionChange:
    path: tuple[str, ...]
    status: str                        # unchanged | changed | added | removed
    level: int                         # min heading level seen for this path
    before_title: str | None
    after_title: str | None
    before_body: str | None
    after_body: str | None

    @property
    def display_path(self) -> str:
        return " / ".join(self.path)

    @property
    def shown_title(self) -> str:
        return self.after_title or self.before_title or self.display_path


def compare_sections(before_md: str, after_md: str) -> list[SectionChange]:
    """Align sections by heading path and classify each."""
    before = {s.path: s for s in split_by_heading(before_md)}
    after = {s.path: s for s in split_by_heading(after_md)}

    # Preserve the original (after-doc) ordering for anything shared or
    # added; append removed entries at the end.
    ordered_paths: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for s in split_by_heading(after_md):
        if s.path not in seen:
            ordered_paths.append(s.path)
            seen.add(s.path)
    for s in split_by_heading(before_md):
        if s.path not in seen:
            ordered_paths.append(s.path)
            seen.add(s.path)

    changes: list[SectionChange] = []
    for path in ordered_paths:
        b = before.get(path)
        a = after.get(path)
        if b and a:
            status = "unchanged" if _section_fingerprint(b.body) == _section_fingerprint(a.body) else "changed"
        elif a and not b:
            status = "added"
        else:
            status = "removed"
        changes.append(SectionChange(
            path=path,
            status=status,
            level=min(b.level if b else 99, a.level if a else 99),
            before_title=b.title if b else None,
            after_title=a.title if a else None,
            before_body=b.body if b else None,
            after_body=a.body if a else None,
        ))
    return changes


def summarise_section_changes(changes: Iterable[SectionChange]) -> dict[str, int]:
    counts = {"unchanged": 0, "changed": 0, "added": 0, "removed": 0}
    for c in changes:
        counts[c.status] = counts.get(c.status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Optional: prompt builder for an LLM-narrated delta
# ---------------------------------------------------------------------------


def build_ai_delta_prompt(
    ticker: str,
    exchange: str,
    before_md: str,
    after_md: str,
    *,
    before_label: str = "earlier report",
    after_label: str = "latest report",
) -> tuple[str, str]:
    """(system_prompt, user_prompt) for an LLM asked to summarise the
    *meaningful* changes between two reports on the same stock."""
    system = (
        "You are a financial analyst. Two stock-analysis reports for the "
        "same ticker are given. Your ONLY job is to summarise substantive "
        "changes between them — signal shifts, level moves, new risks, "
        "new catalysts, sentiment flips, resolved or emerged contradictions. "
        "Do NOT re-summarise each report; focus on the delta. "
        "Use crisp bullets, ≤10 total, ≤20 words each. "
        "If nothing material changed, say so in one sentence."
    )
    user = (
        f"Ticker: {exchange}:{ticker}\n\n"
        f"=== {before_label.upper()} ===\n{before_md.strip()}\n\n"
        f"=== {after_label.upper()} ===\n{after_md.strip()}\n\n"
        "Summarise what changed. Bullets only."
    )
    return system, user
