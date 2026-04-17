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

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

import streamlit as st
import logging
import time
import threading
import json as _json
from pathlib import Path
from datetime import datetime
from src.agents.orchestrator import create_orchestrator
from src.agents.lead_researcher import research_stock, thesis_to_dict
from src.agents.evidence import StockThesis
from src.reports.render import (
    render_thesis_markdown,
    consolidated_xlsx_bytes,
    consolidated_markdown_table,
)
from src.tools.batch_tools import read_stocks_file
from src.config.exchanges import detect_exchange, strip_prefix, get_display_ticker
from src.config.analysis_profiles import PROFILES, PROFILE_ORDER, DEFAULT_PROFILE
from src.config.settings import settings
from src.db.report_store import ReportStore
from src.ui.pdf_export import (
    markdown_to_pdf, save_pdf_to_disk, save_md_to_disk,
    batch_report_to_pdf, save_batch_pdf_to_disk, consolidated_table_to_xlsx,
)
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class AnalysisStopped(Exception):
    """Raised from a polling loop when the user clicks Stop."""


st.title("Stock Analysis Agent")
st.caption("Powered by Strands Agents + AWS Bedrock")


def _render_market_regime_panel():
    if not settings.enable_macro_context:
        return
    from src.tools.macro_tools import fetch_macro_snapshot as _fetch_macro

    # Scoped CSS: widens only the bordered container that contains the tag
    # div below, leaving every other st.container(border=True) untouched.
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"]:has(div.market-regime-tag) {
            width: 110%;
            max-width: 110%;
            margin-left: -5%;
            margin-right: -5%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            '<div class="market-regime-tag" style="display:none"></div>',
            unsafe_allow_html=True,
        )
        header_col, refresh_col = st.columns([6, 1])
        with header_col:
            st.markdown("**Market Regime**")
        with refresh_col:
            refresh = st.button("Refresh", key="macro_refresh_btn", width="stretch")

        try:
            snap = _fetch_macro(use_cache=not refresh)
        except Exception as e:
            st.caption(f"_Macro unavailable: {e}_")
            return

        if not snap.indicators:
            st.caption("No macro data cached yet. Click Refresh to fetch.")
            return

        st.caption(f"As of {snap.as_of:%Y-%m-%d %H:%M UTC}")
        display_order = ["NIFTY50", "SENSEX", "INDIAVIX", "USDINR", "BRENT", "DXY"]
        shown = [c for c in display_order if c in snap.indicators]
        if shown:
            cols = st.columns(len(shown))
            for col, code in zip(cols, shown):
                r = snap.indicators[code]
                delta = f"{r.d1_pct:+.2f}% 1D" if r.d1_pct is not None else None
                col.metric(label=r.label, value=f"{r.value:,.2f}", delta=delta)
        if snap.missing:
            st.caption(f"_Missing: {', '.join(snap.missing)}_")


_render_market_regime_panel()

# Consume + display stop-request from a previous rerun. The Stop button
# sets this flag; Streamlit reruns the script, we pick the flag up here,
# show a notice once, and clear it so the next Analyze click starts clean.
if st.session_state.get("stop_requested"):
    st.warning("Analysis stopped by user.")
    st.session_state.stop_requested = False

# --- Initialize Report Store ---
@st.cache_resource
def get_report_store():
    return ReportStore(db_path=settings.db_path, cache_hours=settings.report_cache_hours)

store = get_report_store()


class ToolTracker:
    """Thread-safe tool timing tracker and stream buffer. No Streamlit calls.

    Strands agent hooks and callback handler fire from a background thread.
    This class only appends to lists (thread-safe in CPython). The main
    Streamlit thread polls to update the UI.
    """

    def __init__(self):
        self.entries: list[dict] = []
        self._start_times: dict[str, float] = {}
        self.tool_count: int = 0
        self.current_tool: str | None = None
        self.stream_chunks: list[str] = []
        self._stream_version: int = 0

    def on_start(self, tool_name: str):
        self._start_times[tool_name] = time.time()
        self.tool_count += 1
        self.current_tool = tool_name

    def on_end(self, tool_name: str, elapsed: float):
        start_time = self._start_times.pop(tool_name, None)
        started_at = datetime.fromtimestamp(start_time).strftime("%H:%M:%S") if start_time else "—"
        self.entries.append({
            "Tool": tool_name,
            "Started": started_at,
            "Completed": datetime.now().strftime("%H:%M:%S"),
            "Duration (s)": round(elapsed, 2),
        })
        self.current_tool = None

    def callback_handler(self, **kwargs):
        data = kwargs.get("data", "")
        if data:
            self.stream_chunks.append(data)
            self._stream_version += 1

    def get_stream_text(self) -> str:
        return "".join(self.stream_chunks)

    def get_dataframe(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame(columns=["Tool", "Started", "Completed", "Duration (s)"])
        return pd.DataFrame(self.entries)

    def reset(self):
        self.entries.clear()
        self._start_times.clear()
        self.tool_count = 0
        self.current_tool = None
        self.stream_chunks.clear()
        self._stream_version = 0


def run_agent_with_live_progress(
    agent, prompt: str, tracker: ToolTracker, status_label: str,
    report_stream_placeholder=None,
    report_stream_prefix: str = "",
):
    """Run agent in a background thread while polling tracker for live UI updates.

    Args:
        agent: The orchestrator agent.
        prompt: Analysis prompt.
        tracker: ToolTracker to collect timing + stream data.
        status_label: Label for the st.status widget.
        report_stream_placeholder: Optional st.empty() to stream live report into.
        report_stream_prefix: Markdown to prepend before the current stream
            (used in batch mode to show previously completed reports).

    Returns the agent response string. Raises on failure.
    """
    result_holder: dict = {"response": None, "error": None}

    original_handler = agent.callback_handler
    agent.callback_handler = tracker.callback_handler

    def _run():
        try:
            result_holder["response"] = agent(prompt)
        except Exception as e:
            result_holder["error"] = e
        finally:
            agent.callback_handler = original_handler

    thread = threading.Thread(target=_run, daemon=True)

    # Inline UI: status + tool table
    status_container = st.status(status_label, expanded=True)
    st.caption("Tool Execution Summary")
    table_placeholder = st.empty()
    total_placeholder = st.empty()

    thread.start()
    last_count = 0
    last_stream_ver = 0

    while thread.is_alive():
        if st.session_state.get("stop_requested"):
            # Don't wait for the background thread; it's a daemon and will
            # expire with the process. Mark status, surface what we have.
            status_container.update(label="Stopping analysis...", state="error")
            raise AnalysisStopped()
        if tracker.current_tool:
            status_container.update(
                label=f"Running: {tracker.current_tool} (tool #{tracker.tool_count})...",
                state="running",
            )
        elif tracker.tool_count > last_count:
            last_entry = tracker.entries[-1] if tracker.entries else None
            if last_entry:
                status_container.update(
                    label=f"Completed: {last_entry['Tool']} ({last_entry['Duration (s)']}s) — {tracker.tool_count} tools",
                    state="running",
                )

        if tracker.tool_count > last_count:
            df = tracker.get_dataframe()
            if not df.empty:
                table_placeholder.dataframe(df, width="stretch", hide_index=True)
                total_placeholder.metric("Total Tool Execution Time", f"{df['Duration (s)'].sum():.2f}s")
            last_count = tracker.tool_count

        # Stream live report text to Report-Stream tab if placeholder provided
        if report_stream_placeholder and tracker._stream_version > last_stream_ver:
            report_stream_placeholder.markdown(report_stream_prefix + tracker.get_stream_text())
            last_stream_ver = tracker._stream_version

        time.sleep(0.5)

    thread.join()

    # Final updates
    df = tracker.get_dataframe()
    if not df.empty:
        table_placeholder.dataframe(df, width="stretch", hide_index=True)
        total_placeholder.metric("Total Tool Execution Time", f"{df['Duration (s)'].sum():.2f}s")

    if result_holder["error"]:
        status_container.update(label="Analysis failed", state="error")
        raise result_holder["error"]

    status_container.update(label="Analysis complete!", state="complete", expanded=False)
    table_placeholder.empty()
    total_placeholder.empty()

    return result_holder["response"]


def run_research_engine(
    ticker: str,
    exchange: str,
    tracker: "ToolTracker",
    status_label: str,
) -> tuple[StockThesis, str, "datetime | None"]:
    """Run the Claude-style research engine in a background thread with live UI.

    Returns (thesis, rendered_markdown, macro_snapshot_as_of). The third tuple
    element is None if macro context was disabled or the fetch failed.
    """
    result_holder: dict = {
        "thesis": None, "plan": None, "evidence": None, "critique": None,
        "macro": None, "error": None,
    }

    def _run():
        try:
            thesis, plan, evidence, critique_report, macro_snapshot = research_stock(
                ticker,
                exchange,
                on_tool_start=tracker.on_start,
                on_tool_end=tracker.on_end,
            )
            result_holder["thesis"] = thesis
            result_holder["plan"] = plan
            result_holder["evidence"] = evidence
            result_holder["critique"] = critique_report
            result_holder["macro"] = macro_snapshot
        except Exception as e:
            result_holder["error"] = e

    thread = threading.Thread(target=_run, daemon=True)
    status_container = st.status(status_label, expanded=True)
    st.caption("Investigator Tool Calls")
    table_placeholder = st.empty()
    total_placeholder = st.empty()

    thread.start()
    last_count = 0
    while thread.is_alive():
        if st.session_state.get("stop_requested"):
            status_container.update(label="Stopping research...", state="error")
            raise AnalysisStopped()
        if tracker.current_tool:
            status_container.update(
                label=f"Running: {tracker.current_tool} (call #{tracker.tool_count})...",
                state="running",
            )
        elif tracker.tool_count > last_count:
            last_entry = tracker.entries[-1] if tracker.entries else None
            if last_entry:
                status_container.update(
                    label=f"Completed: {last_entry['Tool']} ({last_entry['Duration (s)']}s) — {tracker.tool_count} calls",
                    state="running",
                )
        if tracker.tool_count > last_count:
            df = tracker.get_dataframe()
            if not df.empty:
                table_placeholder.dataframe(df, width="stretch", hide_index=True)
                total_placeholder.metric("Total Tool Execution Time", f"{df['Duration (s)'].sum():.2f}s")
            last_count = tracker.tool_count
        time.sleep(0.5)

    thread.join()

    df = tracker.get_dataframe()
    if not df.empty:
        table_placeholder.dataframe(df, width="stretch", hide_index=True)
        total_placeholder.metric("Total Tool Execution Time", f"{df['Duration (s)'].sum():.2f}s")

    if result_holder["error"]:
        status_container.update(label="Research failed", state="error")
        raise result_holder["error"]

    status_container.update(label="Research complete!", state="complete", expanded=False)
    table_placeholder.empty()
    total_placeholder.empty()

    thesis: StockThesis = result_holder["thesis"]
    rendered = render_thesis_markdown(
        thesis,
        plan=result_holder["plan"],
        evidence=result_holder["evidence"],
        include_citations=True,
    )
    macro_snapshot = result_holder["macro"]
    macro_as_of = (
        macro_snapshot.as_of
        if macro_snapshot is not None and macro_snapshot.indicators
        else None
    )
    return thesis, rendered, macro_as_of


def save_thesis_json(thesis: StockThesis, reports_dir: str) -> str:
    """Persist StockThesis JSON next to the md/pdf artifacts. Returns file path."""
    out_dir = Path(reports_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = thesis.generated_at.strftime("%Y%m%d_%H%M%S")
    fname = f"{thesis.exchange}_{thesis.ticker}_{ts}_thesis.json"
    fpath = out_dir / fname
    fpath.write_text(thesis.model_dump_json(indent=2), encoding="utf-8")
    return str(fpath)


def build_comparison_markdown(current_md: str, previous: dict) -> str:
    """Build a markdown section comparing current report with a previous one."""
    prev_date = previous["analyzed_at"]
    prev_profile = previous["profile"]
    prev_md = previous["report_markdown"]

    lines = [
        f"### Previous Report ({prev_date}, {prev_profile})",
        "",
        prev_md,
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")

    analysis_mode = st.radio("Analysis Mode", ["Single Stock", "Batch (File)"])

    if analysis_mode == "Single Stock":
        ticker_input = st.text_input("Stock Ticker", placeholder="e.g., NSE:RELIANCE, AAPL, BSE:500325")
        exchange_override = st.selectbox("Exchange", ["Auto-Detect", "NSE", "BSE", "NASDAQ"])
    else:
        uploaded_file = st.file_uploader("Upload stocks.txt", type=["txt"])
        if uploaded_file:
            st.code(uploaded_file.getvalue().decode("utf-8")[:500], language="text")

    st.subheader("Analysis Level")
    profile_labels = [PROFILES[k].label for k in PROFILE_ORDER]
    selected_label = st.radio(
        "Choose analysis depth based on your expertise",
        profile_labels,
        index=PROFILE_ORDER.index(DEFAULT_PROFILE),
    )
    selected_profile = PROFILE_ORDER[profile_labels.index(selected_label)]
    profile = PROFILES[selected_profile]
    max_queries = profile.news_queries

    st.caption(profile.description)

    with st.expander("What's included?"):
        group_descriptions = {
            "core": "Exchange detection & stock quotes",
            "market_data": "Historical data & market indices",
            "technical_basic": "200-Day Moving Average (trend)",
            "technical_momentum": "MACD momentum signals",
            "technical_levels": "Support/Resistance & price estimates",
            "technical_dashboard": "RSI, Stochastic, ADX dashboard",
            "news_basic": "Top news headlines",
            "news_batch": "Batch news search & article extraction",
            "news_location": "Location-specific news sources",
            "fundamentals": "Fundamental ratios (PE, ROE, debt, etc.)",
            "scraping_basic": "Google Finance data",
            "scraping_advanced": "Yahoo Finance & MoneyControl data",
            "scraping_chartink": "Chartink screener scans",
            "batch": "Batch stock file processing",
        }
        for group_key in profile.tool_groups:
            if group_key in ("core", "batch"):
                continue
            desc = group_descriptions.get(group_key, group_key)
            st.markdown(f"- {desc}")
        st.markdown(f"- Up to **{max_queries}** news search queries")

    new_capabilities = {
        "beginner": "Includes: Composite Score",
        "novice": "Includes: EMA Crossovers, Composite Score, Risk Metrics",
        "intermediate": "Includes: Fibonacci, VWAP, Insider Activity, MF Holdings, Trendlyne",
        "expert": "Includes: All 40+ tools, Options Chain, Chart Patterns, Full Risk Dashboard",
    }
    st.info(new_capabilities.get(selected_profile, ""))

    # Data source toggle
    st.subheader("Data Source")
    data_source = st.radio("Report Source", ["Fetch Fresh", "Use Cached"], index=0)

    # Analysis engine toggle
    st.subheader("Analysis Engine")
    engine_choice = st.radio(
        "Engine",
        ["Classic (single-pass orchestrator)", "Research (multi-agent)"],
        index=1 if settings.research_mode_enabled else 0,
        help=(
            "Classic: one agent, 40+ tools, linear execution.\n"
            "Research: planner decomposes into threads, parallel investigators "
            "emit structured evidence, synthesizer reconciles contradictions, "
            "self-critic red-teams the thesis."
        ),
    )
    use_research_engine = engine_choice.startswith("Research")

    col_run, col_stop = st.columns(2)
    with col_run:
        analyze_btn = st.button("Analyze", type="primary", width="stretch")
    with col_stop:
        # Renders every page-load. Clicking it triggers a Streamlit rerun;
        # the in-flight polling loop sees `stop_requested=True` and raises
        # AnalysisStopped. For cached-result renders it's a no-op.
        if st.button("Stop", key="stop_btn", width="stretch"):
            st.session_state.stop_requested = True

# --- Session State ---
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
if "results" not in st.session_state:
    st.session_state.results = None
if "batch_results" not in st.session_state:
    st.session_state.batch_results = {}
if "tool_tracker" not in st.session_state:
    st.session_state.tool_tracker = ToolTracker()
if "batch_trackers" not in st.session_state:
    st.session_state.batch_trackers = {}
if "batch_comparisons" not in st.session_state:
    st.session_state.batch_comparisons = {}
if "consolidated_table" not in st.session_state:
    st.session_state.consolidated_table = ""

# === ANALYSIS ===
if analyze_btn:
    # Reset per-run caches that shouldn't carry across runs
    st.session_state.pop("consolidated_xlsx_bytes", None)
    # Fresh analyze click -> clear any stale stop flag from a prior run.
    st.session_state.stop_requested = False
    if analysis_mode == "Single Stock":
        if not ticker_input:
            st.error("Please enter a stock ticker.")
            st.stop()

        ticker = strip_prefix(ticker_input.strip())
        if exchange_override != "Auto-Detect":
            exchange = exchange_override
        else:
            exchange = detect_exchange(ticker_input).value
        display = get_display_ticker(ticker_input)

        if data_source == "Use Cached":
            cached = store.get_latest_report(ticker, exchange)
            if cached:
                st.success(f"Loaded cached report for **{display}** (from {cached['analyzed_at']})")
                st.session_state.results = cached["report_markdown"]
                st.session_state.batch_results = {}
            else:
                st.warning(f"No cached report for **{display}**. Try 'Fetch Fresh'.")
                st.stop()
        else:
            st.info(
                f"Analyzing **{display}** on **{exchange}** | "
                f"Level: **{profile.label}** | {max_queries} news queries"
            )
            tracker = st.session_state.tool_tracker
            tracker.reset()

            try:
                if use_research_engine:
                    thesis, report_md, macro_as_of = run_research_engine(
                        ticker,
                        exchange,
                        tracker,
                        status_label=f"Researching {display} (Claude-style multi-agent)...",
                    )
                    st.session_state.results = report_md
                    st.session_state.batch_results = {}
                    st.session_state.last_thesis = thesis
                    # Auto-save PDF, MD, and thesis JSON
                    pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, selected_profile)
                    pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                    md_path = save_md_to_disk(report_md, ticker, exchange, settings.reports_dir)
                    json_path = save_thesis_json(thesis, settings.reports_dir)
                    store.save_report(
                        ticker, exchange, selected_profile, report_md, pdf_path,
                        macro_snapshot_as_of=macro_as_of,
                    )
                    st.toast(f"Reports auto-saved: {pdf_path}, {md_path}, {json_path}")
                else:
                    prev_profile = st.session_state.get("active_profile")
                    if st.session_state.orchestrator is None or prev_profile != selected_profile:
                        st.session_state.orchestrator = create_orchestrator(
                            profile=selected_profile,
                            on_tool_start=tracker.on_start,
                            on_tool_end=tracker.on_end,
                        )
                        st.session_state.active_profile = selected_profile

                    agent = st.session_state.orchestrator
                    prompt = (
                        f"Analyze the stock {display} on {exchange} exchange. "
                        f"Use up to {max_queries} news search queries.\n\n"
                        f"{profile.prompt_instructions}"
                    )

                    response = run_agent_with_live_progress(
                        agent, prompt, tracker,
                        status_label=f"Running {profile.label.lower()}-level analysis for {display}...",
                    )
                    report_md = str(response)
                    st.session_state.results = report_md
                    st.session_state.batch_results = {}

                    # Auto-save PDF and MD
                    pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, selected_profile)
                    pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                    md_path = save_md_to_disk(report_md, ticker, exchange, settings.reports_dir)
                    store.save_report(ticker, exchange, selected_profile, report_md, pdf_path)
                    st.toast(f"Reports auto-saved: {pdf_path}, {md_path}")
            except AnalysisStopped:
                st.warning(f"Analysis stopped by user (partial state discarded for **{display}**).")
                st.session_state.stop_requested = False
            except Exception as e:
                err_msg = str(e) if str(e) else f"{type(e).__name__} (no message)"
                st.error(f"Analysis failed: {err_msg}")
                import traceback
                st.expander("Error Details").code(traceback.format_exc(), language="text")
                logger.exception("Analysis failed for %s", display)

    else:  # Batch mode
        if not uploaded_file:
            st.error("Please upload a stocks.txt file.")
            st.stop()

        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(uploaded_file.getvalue().decode("utf-8"))
            temp_path = f.name

        try:
            stocks = read_stocks_file.__wrapped__(temp_path)
            if stocks and "error" in stocks[0]:
                st.error(stocks[0]["error"])
                st.stop()

            st.info(
                f"Batch analyzing **{len(stocks)} stocks** | "
                f"Level: **{profile.label}** | {max_queries} queries each"
            )

            # Batch layout: Live Analysis on top, Report-Stream tab below
            batch_results = {}
            batch_trackers = {}
            batch_comparisons = {}
            batch_theses: list[StockThesis] = []  # research-mode only
            progress_bar = st.progress(0, text="Starting batch analysis...")

            # Report-Stream placeholder — accumulates completed reports
            st.subheader("Report Stream")
            report_stream_placeholder = st.empty()
            accumulated_reports = ""

            st.divider()
            st.subheader("Live Analysis")

            for i, stock in enumerate(stocks):
                ticker = stock["ticker"]
                exchange = stock["exchange"]
                display = f"{exchange}:{ticker}"
                progress_bar.progress(
                    (i) / len(stocks),
                    text=f"Analyzing {display} ({i+1}/{len(stocks)})...",
                )

                if data_source == "Use Cached":
                    cached = store.get_latest_report(ticker, exchange)
                    if cached:
                        batch_results[display] = cached["report_markdown"]
                        accumulated_reports += f"## {display} (cached)\n\n{cached['report_markdown']}\n\n---\n\n"
                        report_stream_placeholder.markdown(accumulated_reports)
                        continue

                # Fetch previous report for comparison BEFORE saving new one
                prev_report = store.get_latest_report(ticker, exchange)

                tracker = ToolTracker()

                try:
                    if use_research_engine:
                        thesis, report_md, macro_as_of = run_research_engine(
                            ticker,
                            exchange,
                            tracker,
                            status_label=f"Researching {display} ({i+1}/{len(stocks)})...",
                        )
                        batch_results[display] = report_md
                        batch_theses.append(thesis)

                        pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, selected_profile)
                        pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                        save_md_to_disk(report_md, ticker, exchange, settings.reports_dir)
                        save_thesis_json(thesis, settings.reports_dir)
                        store.save_report(
                            ticker, exchange, selected_profile, report_md, pdf_path,
                            macro_snapshot_as_of=macro_as_of,
                        )
                    else:
                        st.session_state.orchestrator = create_orchestrator(
                            profile=selected_profile,
                            on_tool_start=tracker.on_start,
                            on_tool_end=tracker.on_end,
                        )
                        st.session_state.active_profile = selected_profile
                        agent = st.session_state.orchestrator
                        prompt = (
                            f"Analyze the stock {display} on {exchange} exchange. "
                            f"Use up to {max_queries} news search queries.\n\n"
                            f"{profile.prompt_instructions}"
                        )
                        response = run_agent_with_live_progress(
                            agent, prompt, tracker,
                            status_label=f"Analyzing {display} ({i+1}/{len(stocks)})...",
                            report_stream_placeholder=report_stream_placeholder,
                            report_stream_prefix=accumulated_reports + f"## {display}\n\n",
                        )
                        report_md = str(response)
                        batch_results[display] = report_md

                        pdf_bytes = markdown_to_pdf(report_md, ticker, exchange, selected_profile)
                        pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                        save_md_to_disk(report_md, ticker, exchange, settings.reports_dir)
                        store.save_report(ticker, exchange, selected_profile, report_md, pdf_path)

                    # Accumulate completed report into Report-Stream
                    accumulated_reports += f"## {display}\n\n{report_md}\n\n---\n\n"
                    report_stream_placeholder.markdown(accumulated_reports)

                    # Store comparison data if previous report exists
                    if prev_report:
                        batch_comparisons[display] = prev_report

                except AnalysisStopped:
                    st.warning(
                        f"Batch stopped at **{display}** ({i+1}/{len(stocks)}). "
                        "Completed reports above are preserved."
                    )
                    st.session_state.stop_requested = False
                    # Break the for-loop: treat remaining stocks as skipped.
                    break
                except Exception as e:
                    import traceback
                    err_msg = str(e) if str(e) else f"{type(e).__name__} (no message)"
                    error_text = f"Analysis failed: {err_msg}"
                    batch_results[display] = error_text
                    accumulated_reports += f"## {display}\n\n{error_text}\n\n---\n\n"
                    report_stream_placeholder.markdown(accumulated_reports)
                    logger.exception("Batch analysis failed for %s", display)

                batch_trackers[display] = tracker

            progress_bar.progress(1.0, text="Batch analysis complete!")

            # Generate consolidated summary table
            consolidated_table = ""
            successful_reports = {k: v for k, v in batch_results.items() if not v.startswith("Analysis failed")}
            if successful_reports:
                if use_research_engine and batch_theses:
                    # Research-engine path: build consolidated table deterministically from StockThesis list.
                    # No second orchestrator, no LLM markdown re-parsing.
                    consolidated_table = consolidated_markdown_table(batch_theses)
                    try:
                        xlsx_bytes = consolidated_xlsx_bytes(batch_theses)
                        xlsx_path = Path(settings.reports_dir) / (
                            f"consolidated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        )
                        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
                        xlsx_path.write_bytes(xlsx_bytes)
                        st.session_state.consolidated_xlsx_bytes = xlsx_bytes
                        st.toast(f"Consolidated XLSX saved: {xlsx_path}")
                    except Exception as e:
                        logger.warning("Failed to save research-mode XLSX: %s", e)
                else:
                    with st.spinner("Generating consolidated summary table..."):
                        try:
                            summary_agent = create_orchestrator(profile=selected_profile)
                            all_reports_text = "\n\n---\n\n".join(
                                f"### {ticker}\n{report}" for ticker, report in successful_reports.items()
                            )
                            summary_prompt = (
                                "Based on the following stock analysis reports, create a single consolidated summary table in markdown format.\n\n"
                                "The table MUST have these exact columns (in this order):\n"
                                "| S.No | Stock | Current Price | 200DMA Trend | MACD Status | MACD Signal | EMA Status | EMA Trend | "
                                "News Sentiment | PE Ratio | PE Assessment | ROE | ROE Assessment | ROCE Assessment | Debt Status | "
                                "Dividend Yield | OPM Margin Trend | OPM Assessment | Risk Level | Composite Score | Signal | Target Price |\n\n"
                                "Number each stock starting from 1 in the S.No column.\n"
                                "Extract the values from each stock report below. If a value is not available, put 'N/A'.\n"
                                "Only output the markdown table, nothing else.\n\n"
                                f"{all_reports_text}"
                            )
                            summary_response = summary_agent(summary_prompt)
                            consolidated_table = str(summary_response)
                        except Exception as e:
                            logger.warning("Failed to generate consolidated table: %s", e)
                            consolidated_table = "*Could not generate consolidated table.*"

                    if consolidated_table and not consolidated_table.startswith("*"):
                        try:
                            xlsx_path, _ = consolidated_table_to_xlsx(consolidated_table, settings.reports_dir)
                            st.toast(f"Consolidated XLSX saved: {xlsx_path}")
                        except Exception as e:
                            logger.warning("Failed to save XLSX: %s", e)

                # Auto-save batch PDF (reports only, no consolidated table)
                batch_pdf = batch_report_to_pdf(successful_reports, selected_profile)
                batch_pdf_path = save_batch_pdf_to_disk(batch_pdf, settings.reports_dir)
                st.toast(f"Batch PDF saved: {batch_pdf_path}")

            st.session_state.consolidated_table = consolidated_table
            st.session_state.batch_results = batch_results
            st.session_state.batch_trackers = batch_trackers
            st.session_state.batch_comparisons = batch_comparisons
            st.session_state.results = None
        except Exception as e:
            st.error(f"Batch analysis failed: {e}")
            logger.exception("Batch analysis failed")
        finally:
            os.unlink(temp_path)

# --- Display Single Stock Results ---
if st.session_state.results:
    st.divider()
    report_md = st.session_state.results

    tab1, tab2, tab3, tab4 = st.tabs(["Report", "Stream Data", "Tool Execution Log", "Raw Output"])
    with tab1:
        st.markdown(report_md)

        # Comparison with previous report
        tracker = st.session_state.tool_tracker
        if hasattr(st.session_state, "active_profile"):
            pass  # Single stock comparison shown below
    with tab2:
        tracker = st.session_state.tool_tracker
        stream_text = tracker.get_stream_text()
        col_info, col_clear = st.columns([4, 1])
        with col_info:
            st.caption(f"{len(tracker.stream_chunks)} chunk(s), {len(stream_text)} chars")
        with col_clear:
            if st.button("Clear", key="clear_stream_btn", width="stretch",
                         disabled=not stream_text):
                tracker.stream_chunks.clear()
                tracker._stream_version = 0
                st.rerun()
        if stream_text:
            st.markdown(stream_text)
        else:
            st.info("No stream data available.")
    with tab3:
        tracker = st.session_state.tool_tracker
        df = tracker.get_dataframe()
        if not df.empty:
            st.caption(f"{len(df)} tools executed")
            st.dataframe(df, width="stretch", hide_index=True)
            total_time = df["Duration (s)"].sum()
            st.metric("Total Tool Execution Time", f"{total_time:.2f}s")
        else:
            st.info("No tool execution data available (cached report).")
    with tab4:
        st.code(report_md, language="markdown")

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download Report (Markdown)",
            data=report_md,
            file_name="stock_analysis_report.md",
            mime="text/markdown",
        )
    with col2:
        pdf_bytes = markdown_to_pdf(report_md, "STOCK", "EX", selected_profile)
        st.download_button(
            label="Download Report (PDF)",
            data=pdf_bytes,
            file_name="stock_analysis_report.pdf",
            mime="application/pdf",
        )

# --- Display Batch Results ---
if st.session_state.batch_results:
    st.divider()
    st.subheader(f"Batch Results \u2014 {len(st.session_state.batch_results)} stocks")

    # Consolidated Summary Table — sortable/filterable dataframe + XLSX download
    if st.session_state.consolidated_table:
        with st.expander("Consolidated Report Table", expanded=True):
            table_md = st.session_state.consolidated_table
            # Parse markdown table into DataFrame for sorting/filtering
            import re
            table_lines = [l.strip() for l in table_md.strip().splitlines() if l.strip().startswith("|")]
            if len(table_lines) >= 2:
                def _parse_md_row(line):
                    cells = [c.strip() for c in line.split("|")]
                    if cells and cells[0] == "":
                        cells = cells[1:]
                    if cells and cells[-1] == "":
                        cells = cells[:-1]
                    return [re.sub(r"\*\*(.*?)\*\*", r"\1", c) for c in cells]

                headers = _parse_md_row(table_lines[0])
                rows = []
                for line in table_lines[1:]:
                    if re.match(r"^\|[\s\-:|]+\|$", line):
                        continue
                    rows.append(_parse_md_row(line))

                df_consolidated = pd.DataFrame(rows, columns=headers[:len(rows[0])] if rows else headers)

                # Column filter
                all_cols = df_consolidated.columns.tolist()
                selected_cols = st.multiselect(
                    "Show columns", all_cols, default=all_cols, key="consolidated_cols",
                )
                if selected_cols:
                    st.dataframe(
                        df_consolidated[selected_cols],
                        width="stretch", hide_index=True,
                        column_config={col: st.column_config.TextColumn(col) for col in selected_cols},
                    )
                else:
                    st.dataframe(df_consolidated, width="stretch", hide_index=True)
            else:
                st.markdown(table_md)

            # XLSX download — prefer research-mode bytes built directly from StockThesis list
            try:
                xlsx_bytes = st.session_state.get("consolidated_xlsx_bytes")
                if not xlsx_bytes:
                    _, xlsx_bytes = consolidated_table_to_xlsx(table_md, settings.reports_dir)
                st.download_button(
                    label="Download Consolidated XLSX",
                    data=xlsx_bytes,
                    file_name="consolidated_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="consolidated_xlsx_dl",
                )
            except Exception:
                pass

    for display_ticker, report_md in st.session_state.batch_results.items():
        with st.expander(f"📊 {display_ticker}", expanded=False):
            parts = display_ticker.split(":")
            ex = parts[0] if len(parts) == 2 else "EX"
            tk = parts[1] if len(parts) == 2 else parts[0]

            has_comparison = display_ticker in st.session_state.batch_comparisons
            tab_names = ["Report", "Tool Execution Log"]
            if has_comparison:
                tab_names.append("Comparison")

            tabs = st.tabs(tab_names)

            with tabs[0]:
                st.markdown(report_md)
            with tabs[1]:
                batch_tracker = st.session_state.batch_trackers.get(display_ticker)
                if batch_tracker:
                    df = batch_tracker.get_dataframe()
                    if not df.empty:
                        st.caption(f"{len(df)} tools executed")
                        st.dataframe(df, width="stretch", hide_index=True)
                        total_time = df["Duration (s)"].sum()
                        st.metric("Total Tool Execution Time", f"{total_time:.2f}s")
                    else:
                        st.info("No tool execution data.")
                else:
                    st.info("No tool execution data (cached report).")

            if has_comparison:
                with tabs[2]:
                    prev = st.session_state.batch_comparisons[display_ticker]
                    st.caption(f"Comparing with previous report from **{prev['analyzed_at']}** ({prev['profile']})")

                    col_cur, col_prev = st.columns(2)
                    with col_cur:
                        st.markdown("#### Current Report")
                        st.markdown(report_md)
                    with col_prev:
                        st.markdown(f"#### Previous Report ({prev['analyzed_at']})")
                        st.markdown(prev["report_markdown"])

            col1, col2 = st.columns(2)
            safe_name = display_ticker.replace(":", "_")
            with col1:
                st.download_button(
                    label="Download MD",
                    data=report_md,
                    file_name=f"{safe_name}_report.md",
                    mime="text/markdown",
                    key=f"md_{display_ticker}",
                )
            with col2:
                pdf_bytes = markdown_to_pdf(report_md, tk, ex, selected_profile)
                st.download_button(
                    label="Download PDF",
                    data=pdf_bytes,
                    file_name=f"{safe_name}_report.pdf",
                    mime="application/pdf",
                    key=f"pdf_{display_ticker}",
                )

