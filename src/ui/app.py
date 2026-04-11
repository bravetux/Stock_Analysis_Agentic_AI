# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import streamlit as st
import logging
from src.agents.orchestrator import create_orchestrator
from src.tools.batch_tools import read_stocks_file
from src.config.exchanges import detect_exchange, strip_prefix, get_display_ticker
from src.config.analysis_profiles import PROFILES, PROFILE_ORDER, DEFAULT_PROFILE

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
        for group in PROFILE_ORDER[:PROFILE_ORDER.index(selected_profile) + 1]:
            pass  # just for iteration reference
        for group_key in profile.tool_groups:
            if group_key in ("core", "batch"):
                continue
            desc = group_descriptions.get(group_key, group_key)
            st.markdown(f"- {desc}")
        st.markdown(f"- Up to **{max_queries}** news search queries")

    # Show new capabilities summary
    new_capabilities = {
        "beginner": "Includes: Composite Score",
        "novice": "Includes: EMA Crossovers, Composite Score, Risk Metrics",
        "intermediate": "Includes: Fibonacci, VWAP, Insider Activity, MF Holdings, Trendlyne",
        "expert": "Includes: All 40+ tools, Options Chain, Chart Patterns, Full Risk Dashboard",
    }
    st.info(new_capabilities.get(selected_profile, ""))

    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

# --- Session State ---
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = None
if "results" not in st.session_state:
    st.session_state.results = None

# --- Analysis ---
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

        st.info(
            f"Analyzing **{display}** on **{exchange}** | "
            f"Level: **{profile.label}** | {max_queries} news queries"
        )

        with st.spinner(f"Running {profile.label.lower()}-level analysis for {display}..."):
            try:
                # Re-create orchestrator when profile changes
                prev_profile = st.session_state.get("active_profile")
                if st.session_state.orchestrator is None or prev_profile != selected_profile:
                    st.session_state.orchestrator = create_orchestrator(profile=selected_profile)
                    st.session_state.active_profile = selected_profile

                agent = st.session_state.orchestrator
                prompt = (
                    f"Analyze the stock {display} on {exchange} exchange. "
                    f"Use up to {max_queries} news search queries.\n\n"
                    f"{profile.prompt_instructions}"
                )
                response = agent(prompt)
                st.session_state.results = str(response)
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                logger.exception("Analysis failed for %s", display)

    else:  # Batch mode
        if not uploaded_file:
            st.error("Please upload a stocks.txt file.")
            st.stop()

        # Save uploaded file temporarily
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

            with st.spinner(f"Running {profile.label.lower()}-level batch analysis..."):
                prev_profile = st.session_state.get("active_profile")
                if st.session_state.orchestrator is None or prev_profile != selected_profile:
                    st.session_state.orchestrator = create_orchestrator(profile=selected_profile)
                    st.session_state.active_profile = selected_profile

                agent = st.session_state.orchestrator
                stock_list = ", ".join(f"{s['ticker']} ({s['exchange']})" for s in stocks)
                prompt = (
                    f"Analyze these stocks from the batch file: {stock_list}. "
                    f"Use up to {max_queries} news search queries per stock. "
                    f"Provide individual analysis for each stock, then a summary comparison table.\n\n"
                    f"{profile.prompt_instructions}"
                )
                response = agent(prompt)
                st.session_state.results = str(response)
        except Exception as e:
            st.error(f"Batch analysis failed: {e}")
            logger.exception("Batch analysis failed")
        finally:
            os.unlink(temp_path)

# --- Display Results ---
if st.session_state.results:
    st.divider()

    tab1, tab2 = st.tabs(["Report", "Raw Output"])

    with tab1:
        st.markdown(st.session_state.results)

    with tab2:
        st.code(st.session_state.results, language="markdown")

    # Download button
    st.download_button(
        label="Download Report (Markdown)",
        data=st.session_state.results,
        file_name="stock_analysis_report.md",
        mime="text/markdown",
    )
