# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import streamlit as st
import logging
import time
import threading
from datetime import datetime
from src.agents.orchestrator import create_orchestrator
from src.tools.batch_tools import read_stocks_file
from src.config.exchanges import detect_exchange, strip_prefix, get_display_ticker
from src.config.analysis_profiles import PROFILES, PROFILE_ORDER, DEFAULT_PROFILE
from src.config.settings import settings
from src.db.report_store import ReportStore
from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk, save_md_to_disk, batch_report_to_pdf, save_batch_pdf_to_disk
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Stock Analysis Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Stock Analysis Agent")
st.caption("AG-UC-0999 | Powered by Strands Agents + AWS Bedrock")

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

    analyze_btn = st.button("Analyze", type="primary", width="stretch")

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

# --- Top-level Tabs ---
analyze_tab, history_tab = st.tabs(["Analyze", "History"])

# === ANALYZE TAB ===
with analyze_tab:
    if analyze_btn:
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
                    st.session_state.orchestrator = create_orchestrator(
                        profile=selected_profile,
                        on_tool_start=tracker.on_start,
                        on_tool_end=tracker.on_end,
                    )
                    st.session_state.active_profile = selected_profile
                    agent = st.session_state.orchestrator

                    try:
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

                        # Auto-save and store in DB
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
                    with st.spinner("Generating consolidated summary table..."):
                        try:
                            summary_agent = create_orchestrator(profile=selected_profile)
                            all_reports_text = "\n\n---\n\n".join(
                                f"### {ticker}\n{report}" for ticker, report in successful_reports.items()
                            )
                            summary_prompt = (
                                "Based on the following stock analysis reports, create a single consolidated summary table in markdown format.\n\n"
                                "The table MUST have these exact columns:\n"
                                "| Stock | Current Price | 200DMA Trend | MACD Status | MACD Signal | EMA Status | EMA Trend | "
                                "News Sentiment | PE Ratio | PE Assessment | ROE | ROE Assessment | ROCE Assessment | Debt Status | "
                                "Dividend Yield | OPM Margin Trend | OPM Assessment | Risk Level | Composite Score | Signal | Target Price |\n\n"
                                "Extract the values from each stock report below. If a value is not available, put 'N/A'.\n"
                                "Only output the markdown table, nothing else.\n\n"
                                f"{all_reports_text}"
                            )
                            summary_response = summary_agent(summary_prompt)
                            consolidated_table = str(summary_response)
                        except Exception as e:
                            logger.warning("Failed to generate consolidated table: %s", e)
                            consolidated_table = "*Could not generate consolidated table.*"

                    # Auto-save consolidated batch PDF
                    batch_pdf = batch_report_to_pdf(successful_reports, consolidated_table, selected_profile)
                    batch_pdf_path = save_batch_pdf_to_disk(batch_pdf, settings.reports_dir)
                    st.toast(f"Consolidated batch PDF saved: {batch_pdf_path}")

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
            # Try to find ticker/exchange from session state context
            tracker = st.session_state.tool_tracker
            if hasattr(st.session_state, "active_profile"):
                # Check for previous report in DB
                pass  # Single stock comparison shown below
        with tab2:
            tracker = st.session_state.tool_tracker
            stream_text = tracker.get_stream_text()
            if stream_text:
                st.markdown(stream_text)
            else:
                st.info("No stream data available (cached report).")
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
        st.subheader(f"Batch Results — {len(st.session_state.batch_results)} stocks")

        # Consolidated Summary Table
        if st.session_state.consolidated_table:
            with st.expander("Consolidated Report Table", expanded=True):
                st.markdown(st.session_state.consolidated_table)

                # Download consolidated batch PDF
                successful = {k: v for k, v in st.session_state.batch_results.items()
                              if not v.startswith("Analysis failed")}
                if successful:
                    batch_pdf = batch_report_to_pdf(
                        successful, st.session_state.consolidated_table, selected_profile,
                    )
                    st.download_button(
                        label="Download Consolidated Batch PDF",
                        data=batch_pdf,
                        file_name="batch_consolidated_report.pdf",
                        mime="application/pdf",
                        key="batch_pdf_dl",
                    )

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

# === HISTORY TAB ===
with history_tab:
    st.subheader("Report History")
    st.caption(f"Reports retained for {settings.report_cache_hours} hours ({settings.report_cache_hours // 24} days). Set REPORT_CACHE_HOURS=0 to keep forever.")
    search_query = st.text_input("Search ticker", placeholder="e.g., RELIANCE, AAPL")

    if search_query:
        tickers = store.search_tickers(search_query)
        if not tickers:
            st.info("No reports found matching that ticker.")
        else:
            selected_ticker = st.selectbox("Select ticker", tickers)
            if selected_ticker:
                history = store.get_report_history(selected_ticker)
                if not history:
                    st.info("No reports found.")
                else:
                    st.caption(f"Found {len(history)} report(s) for {selected_ticker}")

                    # Comparison selector
                    if len(history) >= 2:
                        st.subheader("Compare Reports")
                        compare_options = [
                            f"#{r['id']} — {r['exchange']}:{r['ticker']} | {r['profile']} | {r['analyzed_at']}"
                            for r in history
                        ]
                        col_a, col_b = st.columns(2)
                        with col_a:
                            sel_a = st.selectbox("Report A (newer)", compare_options, index=0, key="cmp_a")
                        with col_b:
                            sel_b = st.selectbox("Report B (older)", compare_options, index=1, key="cmp_b")

                        if st.button("Compare", key="compare_btn"):
                            idx_a = compare_options.index(sel_a)
                            idx_b = compare_options.index(sel_b)
                            report_a = history[idx_a]
                            report_b = history[idx_b]

                            st.divider()
                            col_left, col_right = st.columns(2)
                            with col_left:
                                st.markdown(f"#### Report A — {report_a['analyzed_at']}")
                                st.markdown(report_a["report_markdown"])
                            with col_right:
                                st.markdown(f"#### Report B — {report_b['analyzed_at']}")
                                st.markdown(report_b["report_markdown"])

                        st.divider()

                    # Individual report history
                    for report in history:
                        label = f"{report['exchange']}:{report['ticker']} | {report['profile']} | {report['analyzed_at']}"
                        with st.expander(label, expanded=False):
                            st.markdown(report["report_markdown"])

                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    label="Download MD",
                                    data=report["report_markdown"],
                                    file_name=f"{report['exchange']}_{report['ticker']}_{report['id']}.md",
                                    mime="text/markdown",
                                    key=f"hist_md_{report['id']}",
                                )
                            with col2:
                                pdf_bytes = markdown_to_pdf(
                                    report["report_markdown"],
                                    report["ticker"],
                                    report["exchange"],
                                    report["profile"],
                                )
                                st.download_button(
                                    label="Download PDF",
                                    data=pdf_bytes,
                                    file_name=f"{report['exchange']}_{report['ticker']}_{report['id']}.pdf",
                                    mime="application/pdf",
                                    key=f"hist_pdf_{report['id']}",
                                )
    else:
        st.caption("Enter a ticker symbol above to browse past reports.")
