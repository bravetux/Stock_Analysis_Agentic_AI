"""One-off driver: run the research-agent pipeline on NATCO Pharma."""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("run_research")

# Ensure project root on path when run via `uv run python scripts/...`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents.lead_researcher import research_stock  # noqa: E402
from src.reports.render import render_thesis_markdown  # noqa: E402

TICKER = "NATCOPHARM"
EXCHANGE = "NSE"

out_dir = ROOT / "reports"
out_dir.mkdir(parents=True, exist_ok=True)


def _tool_start(name: str) -> None:
    logger.info("TOOL_START %s", name)


def _tool_end(name: str, elapsed: float) -> None:
    logger.info("TOOL_END   %s (%.2fs)", name, elapsed)


def _thread_done(tid: str, count: int) -> None:
    logger.info("THREAD_DONE %s -> %d evidence", tid, count)


def _plan(plan) -> None:
    logger.info(
        "PLAN framing=%r threads=%s",
        plan.framing[:120],
        [(t.thread_id, t.priority, t.budget_tool_calls) for t in plan.threads],
    )


def _synth() -> None:
    logger.info("SYNTHESIZE")


def _crit() -> None:
    logger.info("CRITIQUE")


def _fu(tid: str, obj: str) -> None:
    logger.info("FOLLOW_UP %s -> %s", tid, obj)


def main() -> int:
    t0 = time.time()
    try:
        thesis, plan, evidence, critique, _macro = research_stock(
            TICKER,
            EXCHANGE,
            on_plan=_plan,
            on_tool_start=_tool_start,
            on_tool_end=_tool_end,
            on_thread_done=_thread_done,
            on_synthesize_start=_synth,
            on_critique_start=_crit,
            on_followup=_fu,
        )
    except Exception:
        logger.exception("research_stock failed")
        return 1

    elapsed = time.time() - t0
    logger.info("DONE in %.1fs: signal=%s conviction=%.2f evidence_count=%d", elapsed, thesis.signal.value, thesis.conviction, len(evidence))

    md = render_thesis_markdown(thesis, plan=plan, evidence=evidence, include_citations=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    md_path = out_dir / f"{EXCHANGE}_{TICKER}_{ts}_research.md"
    md_path.write_text(md, encoding="utf-8")

    thesis_path = out_dir / f"{EXCHANGE}_{TICKER}_{ts}_thesis.json"
    thesis_path.write_text(thesis.model_dump_json(indent=2), encoding="utf-8")

    evidence_path = out_dir / f"{EXCHANGE}_{TICKER}_{ts}_evidence.json"
    evidence_path.write_text(
        json.dumps([e.model_dump(mode="json") for e in evidence], indent=2, default=str),
        encoding="utf-8",
    )

    critique_path = out_dir / f"{EXCHANGE}_{TICKER}_{ts}_critique.json"
    critique_path.write_text(critique.model_dump_json(indent=2), encoding="utf-8")

    logger.info("Artifacts: %s, %s, %s, %s", md_path, thesis_path, evidence_path, critique_path)

    # Emit the markdown summary to stdout for easy tail/display.
    print("\n" + "=" * 80)
    print("STOCK THESIS — MARKDOWN")
    print("=" * 80 + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
