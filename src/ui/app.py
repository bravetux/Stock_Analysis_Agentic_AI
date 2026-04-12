# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import streamlit as st
import logging
import time
from datetime import datetime
from src.agents.orchestrator import create_orchestrator
from src.tools.batch_tools import read_stocks_file
from src.config.exchanges import detect_exchange, strip_prefix, get_display_ticker
from src.config.analysis_profiles import PROFILES, PROFILE_ORDER, DEFAULT_PROFILE
from src.config.settings import settings
from src.db.report_store import ReportStore
from src.ui.pdf_export import markdown_to_pdf, save_pdf_to_disk, save_md_to_disk, build_tool_log_markdown
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
    """Tracks tool execution times with live table updates during analysis."""

    def __init__(self):
        self.entries: list[dict] = []
        self._start_times: dict[str, float] = {}
        self._status_container = None
        self._table_placeholder = None
        self._total_placeholder = None
        self._tool_count = 0

    def set_status_container(self, container):
        """Set the Streamlit status container for live updates."""
        self._status_container = container

    def set_table_placeholder(self, table_ph, total_ph):
        """Set Streamlit placeholders for the live-updating table and total metric."""
        self._table_placeholder = table_ph
        self._total_placeholder = total_ph

    def _refresh_table(self):
        """Redraw the live table with current entries."""
        if not self._table_placeholder:
            return
        df = self.get_dataframe()
        if not df.empty:
            self._table_placeholder.dataframe(df, use_container_width=True, hide_index=True)
            total_time = df["Duration (s)"].sum()
            self._total_placeholder.metric("Total Tool Execution Time", f"{total_time:.2f}s")

    def on_start(self, tool_name: str):
        self._start_times[tool_name] = time.time()
        self._tool_count += 1
        if self._status_container:
            self._status_container.update(
                label=f"Running: {tool_name} (tool #{self._tool_count})...",
                state="running",
            )

    def on_end(self, tool_name: str, elapsed: float):
        start_time = self._start_times.pop(tool_name, None)
        started_at = datetime.fromtimestamp(start_time).strftime("%H:%M:%S") if start_time else "—"
        self.entries.append({
            "Tool": tool_name,
            "Started": started_at,
            "Completed": datetime.now().strftime("%H:%M:%S"),
            "Duration (s)": round(elapsed, 2),
        })
        if self._status_container:
            self._status_container.update(
                label=f"Completed: {tool_name} ({elapsed:.2f}s) — {self._tool_count} tools so far",
                state="running",
            )
        self._refresh_table()

    def get_dataframe(self) -> pd.DataFrame:
        if not self.entries:
            return pd.DataFrame(columns=["Tool", "Started", "Completed", "Duration (s)"])
        return pd.DataFrame(self.entries)

    def reset(self):
        self.entries.clear()
        self._start_times.clear()
        self._tool_count = 0
        self._table_placeholder = None
        self._total_placeholder = None


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

    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

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

            # Check cached first if requested
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
                status_container = st.status(
                    f"Running {profile.label.lower()}-level analysis for {display}...",
                    expanded=True,
                )
                tracker.set_status_container(status_container)

                # Live progress table (visible during analysis)
                st.subheader("Tool Execution Summary")
                live_table = st.empty()
                live_total = st.empty()
                tracker.set_table_placeholder(live_table, live_total)

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
                    response = agent(prompt)
                    report_md = str(response)
                    st.session_state.results = report_md
                    st.session_state.batch_results = {}

                    # Clear the live progress table (data moves to Tool Execution Log tab)
                    live_table.empty()
                    live_total.empty()

                    # Build full report with tool execution log
                    tool_log_md = build_tool_log_markdown(tracker.entries)
                    full_report = report_md + tool_log_md

                    # Auto-save PDF and MD with full content
                    pdf_bytes = markdown_to_pdf(full_report, ticker, exchange, selected_profile)
                    pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                    md_path = save_md_to_disk(full_report, ticker, exchange, settings.reports_dir)
                    store.save_report(ticker, exchange, selected_profile, report_md, pdf_path)

                    status_container.update(label="Analysis complete!", state="complete", expanded=False)
                    st.toast(f"Reports auto-saved: {pdf_path}, {md_path}")
                except Exception as e:
                    live_table.empty()
                    live_total.empty()
                    status_container.update(label="Analysis failed", state="error")
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

                batch_results = {}
                batch_trackers = {}
                progress_bar = st.progress(0, text="Starting batch analysis...")

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
                            continue

                    tracker = ToolTracker()
                    status_container = st.status(
                        f"Analyzing {display} ({i+1}/{len(stocks)})...",
                        expanded=True,
                    )
                    tracker.set_status_container(status_container)

                    # Live progress table for this stock
                    st.caption(f"**{display}** — Tool Execution Summary")
                    batch_live_table = st.empty()
                    batch_live_total = st.empty()
                    tracker.set_table_placeholder(batch_live_table, batch_live_total)

                    # Re-create orchestrator per stock so hooks use the current tracker
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
                        response = agent(prompt)
                        report_md = str(response)
                        batch_results[display] = report_md

                        # Clear live table (data moves to Tool Execution Log tab)
                        batch_live_table.empty()
                        batch_live_total.empty()

                        # Build full report with tool execution log
                        tool_log_md = build_tool_log_markdown(tracker.entries)
                        full_report = report_md + tool_log_md

                        # Auto-save PDF and MD with full content
                        pdf_bytes = markdown_to_pdf(full_report, ticker, exchange, selected_profile)
                        pdf_path = save_pdf_to_disk(pdf_bytes, ticker, exchange, settings.reports_dir)
                        save_md_to_disk(full_report, ticker, exchange, settings.reports_dir)
                        store.save_report(ticker, exchange, selected_profile, report_md, pdf_path)
                        status_container.update(label=f"{display} — complete!", state="complete", expanded=False)
                    except Exception as e:
                        batch_live_table.empty()
                        batch_live_total.empty()
                        import traceback
                        err_msg = str(e) if str(e) else f"{type(e).__name__} (no message)"
                        batch_results[display] = f"Analysis failed: {err_msg}\n\n```\n{traceback.format_exc()}\n```"
                        status_container.update(label=f"{display} — failed", state="error")
                        logger.exception("Batch analysis failed for %s", display)

                    batch_trackers[display] = tracker

                progress_bar.progress(1.0, text="Batch analysis complete!")
                st.session_state.batch_results = batch_results
                st.session_state.batch_trackers = batch_trackers
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

        tab1, tab2, tab3 = st.tabs(["Report", "Tool Execution Log", "Raw Output"])
        with tab1:
            st.markdown(report_md)
        with tab2:
            tracker = st.session_state.tool_tracker
            df = tracker.get_dataframe()
            if not df.empty:
                st.caption(f"{len(df)} tools executed")
                st.dataframe(df, use_container_width=True, hide_index=True)
                total_time = df["Duration (s)"].sum()
                st.metric("Total Tool Execution Time", f"{total_time:.2f}s")
            else:
                st.info("No tool execution data available (cached report).")
        with tab3:
            st.code(report_md, language="markdown")

        # Build full report for downloads (includes tool log)
        tracker = st.session_state.tool_tracker
        tool_log_md = build_tool_log_markdown(tracker.entries)
        full_report = report_md + tool_log_md

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Report (Markdown)",
                data=full_report,
                file_name="stock_analysis_report.md",
                mime="text/markdown",
            )
        with col2:
            pdf_bytes = markdown_to_pdf(full_report, "STOCK", "EX", selected_profile)
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

        for display_ticker, report_md in st.session_state.batch_results.items():
            with st.expander(f"📊 {display_ticker}", expanded=False):
                report_tab, log_tab = st.tabs(["Report", "Tool Execution Log"])
                with report_tab:
                    st.markdown(report_md)
                with log_tab:
                    batch_tracker = st.session_state.batch_trackers.get(display_ticker)
                    if batch_tracker:
                        df = batch_tracker.get_dataframe()
                        if not df.empty:
                            st.caption(f"{len(df)} tools executed")
                            st.dataframe(df, use_container_width=True, hide_index=True)
                            total_time = df["Duration (s)"].sum()
                            st.metric("Total Tool Execution Time", f"{total_time:.2f}s")
                        else:
                            st.info("No tool execution data.")
                    else:
                        st.info("No tool execution data (cached report).")

                # Build full report for downloads (includes tool log)
                batch_tracker_dl = st.session_state.batch_trackers.get(display_ticker)
                batch_tool_log = build_tool_log_markdown(batch_tracker_dl.entries) if batch_tracker_dl else ""
                full_batch_report = report_md + batch_tool_log

                col1, col2 = st.columns(2)
                safe_name = display_ticker.replace(":", "_")
                with col1:
                    st.download_button(
                        label="Download MD",
                        data=full_batch_report,
                        file_name=f"{safe_name}_report.md",
                        mime="text/markdown",
                        key=f"md_{display_ticker}",
                    )
                with col2:
                    parts = display_ticker.split(":")
                    ex = parts[0] if len(parts) == 2 else "EX"
                    tk = parts[1] if len(parts) == 2 else parts[0]
                    pdf_bytes = markdown_to_pdf(full_batch_report, tk, ex, selected_profile)
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
