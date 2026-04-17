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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

import streamlit as st
from src.db.report_store import ReportStore
from src.config.settings import settings

st.set_page_config(
    page_title="Stock Analysis Agent",
    page_icon="\U0001f4c8",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Initialize report store for stats ────────────────────────────────────────
@st.cache_resource
def get_report_store():
    return ReportStore(db_path=settings.db_path, cache_hours=settings.report_cache_hours)

store = get_report_store()

# ── Inject custom CSS ────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=DM+Sans:wght@300;400;500;600;700&display=swap');

/* ── Light theme overrides ──────────────────────────────────────────────── */
section[data-testid="stMain"] {
    background: #f8f9fc !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* ── Hero text ──────────────────────────────────────────────────────────── */
.hero-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: .8rem;
    font-weight: 600;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: #b8860b;
    border: 1px solid rgba(184,134,11,.3);
    border-radius: 100px;
    padding: .4em 1.4em;
    background: rgba(184,134,11,.08);
}
.hero-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: clamp(2rem, 4.5vw, 3.4rem);
    font-weight: 800;
    line-height: 1.1;
    letter-spacing: -.03em;
    color: #1a1a2e;
    margin: .8rem 0 .6rem;
}
.hero-title .acc { color: #b8860b; }
.hero-sub {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.15rem;
    line-height: 1.65;
    color: #555;
    max-width: 640px;
}

/* ── CTA button ─────────────────────────────────────────────────────────── */
div.cta-wrap [data-testid="stBaseButton-primary"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: .05em !important;
    background: linear-gradient(135deg, #d4a017, #b8860b) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: .85rem 2.6rem !important;
    box-shadow: 0 2px 12px rgba(184,134,11,.18), 0 4px 16px rgba(0,0,0,.08) !important;
    transition: all .25s ease !important;
}
div.cta-wrap [data-testid="stBaseButton-primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 20px rgba(184,134,11,.28), 0 8px 24px rgba(0,0,0,.12) !important;
}

/* ── Pipeline row ───────────────────────────────────────────────────────── */
.pipe-box {
    background: #ffffff;
    border: 1px solid #e0e3eb;
    border-radius: 10px;
    padding: 1.1rem .8rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
}
.pipe-phase {
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    font-weight: 700;
    letter-spacing: .1em;
    text-transform: uppercase;
}
.pipe-name {
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    font-weight: 500;
    color: #444;
    margin-top: .25rem;
}
.pipe-count {
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    color: #777;
    margin-top: .2rem;
}

/* ── Section headers ────────────────────────────────────────────────────── */
.sec-over {
    font-family: 'JetBrains Mono', monospace;
    font-size: .8rem;
    font-weight: 600;
    letter-spacing: .15em;
    text-transform: uppercase;
    color: #888;
    text-align: center;
}
.sec-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.6rem;
    font-weight: 700;
    color: #1a1a2e;
    text-align: center;
    letter-spacing: -.02em;
}

/* ── Feature cards ──────────────────────────────────────────────────────── */
div[data-testid="stVerticalBlock"] .feature-card {
    background: #ffffff;
    border: 1px solid #e0e3eb;
    border-radius: 12px;
    padding: 1.8rem;
    height: 100%;
    box-shadow: 0 1px 6px rgba(0,0,0,.04);
    transition: background .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.feature-card:hover {
    background: #f0f2f8;
    border-color: #c8ccd8;
    box-shadow: 0 4px 16px rgba(0,0,0,.07);
}
.fc-phase {
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: .4rem;
    margin-bottom: .6rem;
}
.fc-phase-dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block;
}
.fc-icon {
    font-size: 2rem;
    display: block;
    margin-bottom: .5rem;
}
.fc-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.3rem;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: .4rem;
}
.fc-desc {
    font-family: 'DM Sans', sans-serif;
    font-size: 1.1rem;
    color: #555;
    line-height: 1.6;
    margin-bottom: .9rem;
}
.fc-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.fc-list li {
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    color: #666;
    line-height: 1.75;
    padding-left: 1rem;
    position: relative;
}
.fc-list li::before {
    content: '\203a';
    position: absolute;
    left: 0;
    font-weight: 700;
    color: #999;
}

/* ── Stats metric overrides ─────────────────────────────────────────────── */
div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e0e3eb;
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
}
div[data-testid="stMetric"] label {
    font-family: 'DM Sans', sans-serif !important;
    color: #888 !important;
    font-size: .85rem !important;
    letter-spacing: .08em !important;
    text-transform: uppercase !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    color: #1a1a2e !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
}

/* ── Profile cards ──────────────────────────────────────────────────────── */
.profile-card {
    background: #ffffff;
    border: 1px solid #e0e3eb;
    border-radius: 10px;
    padding: 1.3rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
    transition: background .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.profile-card:hover {
    background: #f0f2f8;
    border-color: #c8ccd8;
    box-shadow: 0 4px 16px rgba(0,0,0,.07);
}
.profile-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: .3rem;
}
.profile-queries {
    font-family: 'JetBrains Mono', monospace;
    font-size: .85rem;
    color: #777;
    margin-top: .2rem;
}

/* ── Bottom tagline ─────────────────────────────────────────────────────── */
.bottom-tag {
    font-family: 'DM Sans', sans-serif;
    font-size: 1rem;
    color: #777;
    text-align: center;
    margin-bottom: 1rem;
}

/* ── Divider subtle ─────────────────────────────────────────────────────── */
hr {
    border-color: #e0e3eb !important;
}
</style>
""",
    unsafe_allow_html=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  HERO
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("")  # spacer

st.markdown(
    '<div class="hero-badge">Multi-Agent Platform</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero-title">Stock Analysis<span class="acc"> Agent</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero-sub">'
    "5 specialist AI agents analyze stocks across BSE, NSE, and NASDAQ "
    "using technical indicators, 100 news query types, fundamentals, "
    "and real-time web scraping &mdash; delivering comprehensive reports "
    "in minutes."
    "</div>",
    unsafe_allow_html=True,
)

st.markdown("")  # spacer

# ── Primary CTA ──────────────────────────────────────────────────────────────
with st.container():
    st.markdown('<div class="cta-wrap">', unsafe_allow_html=True)
    if st.button("\u2002Start Analysis  \u2192", type="primary"):
        st.switch_page("pages/1_Analysis.py")
    st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  AGENT PIPELINE STRIP
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("")
st.divider()
st.markdown("")

_pipe_data = [
    ("Orchestrator", "Routes & Aggregates", "coordinator", "#f0b429"),
    ("Technical", "200DMA, MACD, RSI", "5 indicators", "#00c8ff"),
    ("News", "100 Query Types", "10 categories", "#22d68a"),
    ("Fundamental", "Screener + Yahoo", "ratios & metrics", "#a37eff"),
    ("Market Data", "Multi-Exchange", "NSE / BSE / NASDAQ", "#ff6b6b"),
]

pipe_cols = st.columns(len(_pipe_data))
for col, (name, desc, detail, color) in zip(pipe_cols, _pipe_data):
    with col:
        st.markdown(
            f'<div class="pipe-box">'
            f'<div class="pipe-phase" style="color:{color};">{name}</div>'
            f'<div class="pipe-name">{desc}</div>'
            f'<div class="pipe-count">{detail}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("")

try:
    all_reports = store.search_tickers("")
    total = len(all_reports) if all_reports else 0
except Exception:
    total = 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Exchanges", 3)
c2.metric("AI Agents", 5)
c3.metric("News Queries", 100)
c4.metric("Reports Saved", total)

st.markdown("")


# ═══════════════════════════════════════════════════════════════════════════════
#  FEATURE CARDS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
st.markdown("")
st.markdown('<div class="sec-over">Capabilities</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sec-title">5 Agents. 3 Exchanges. One Report.</div>',
    unsafe_allow_html=True,
)
st.markdown("")

_FEATURES = [
    {
        "icon": "\U0001f4c9",
        "name": "Technical Analysis",
        "phase": "Agent \u2014 Technical",
        "color": "#00c8ff",
        "desc": "Deep technical indicators with breakpoint detection and price forecasting.",
        "points": [
            "200-Day Moving Average breakpoints",
            "MACD crossovers and momentum signals",
            "Support / Resistance levels via ATR + Bollinger",
            "RSI, Stochastic, ADX technical dashboard",
        ],
    },
    {
        "icon": "\U0001f4f0",
        "name": "News Intelligence",
        "phase": "Agent \u2014 News",
        "color": "#22d68a",
        "desc": "100 search query templates across 10 categories with location awareness.",
        "points": [
            "Earnings, guidance, and analyst upgrades",
            "Sector rotation and competitor moves",
            "Regulatory, legal, and insider activity",
            "India-specific and US-specific sources",
        ],
    },
    {
        "icon": "\U0001f4ca",
        "name": "Fundamental Analysis",
        "phase": "Agent \u2014 Fundamental",
        "color": "#a37eff",
        "desc": "Financial ratios and metrics from Screener.in and Yahoo Finance.",
        "points": [
            "PE, PB, ROE, ROCE, Debt-to-Equity",
            "Dividend yield and payout ratios",
            "Operating profit margin trends",
            "Quarterly and annual comparisons",
        ],
    },
    {
        "icon": "\U0001f4b9",
        "name": "Market Data",
        "phase": "Agent \u2014 Market Data",
        "color": "#ff6b6b",
        "desc": "Real-time and historical quotes across NSE, BSE, and NASDAQ.",
        "points": [
            "Live price, volume, and day range",
            "52-week high/low and market cap",
            "Historical OHLCV data via yfinance",
            "NSETools and BSEData for Indian markets",
        ],
    },
    {
        "icon": "\U0001f310",
        "name": "Web Scraping",
        "phase": "Agent \u2014 Web Scraping",
        "color": "#f0b429",
        "desc": "Extracts live data from Google Finance, Chartink, and MoneyControl.",
        "points": [
            "Google Finance snapshot and peers",
            "Yahoo Finance detailed financials",
            "Chartink screener scan results",
            "MoneyControl consensus and targets",
        ],
    },
    {
        "icon": "\U0001f9e0",
        "name": "Orchestrator",
        "phase": "Coordinator",
        "color": "#f0b429",
        "desc": "Routes analysis to specialists, aggregates results, and handles batch mode.",
        "points": [
            "Parallel batch via ThreadPoolExecutor",
            "4 expertise profiles: beginner to expert",
            "Consolidated summary tables for batch runs",
            "PDF, Markdown, and XLSX export",
        ],
    },
]

# Render in rows of 2
for i in range(0, len(_FEATURES), 2):
    row = st.columns(2)
    for col, feat in zip(row, _FEATURES[i : i + 2]):
        with col:
            li_html = "".join(f"<li>{p}</li>" for p in feat["points"])
            st.markdown(
                f'<div class="feature-card">'
                f'<div class="fc-phase" style="color:{feat["color"]};">'
                f'<span class="fc-phase-dot" style="background:{feat["color"]};"></span>'
                f'{feat["phase"]}</div>'
                f'<span class="fc-icon">{feat["icon"]}</span>'
                f'<div class="fc-name">{feat["name"]}</div>'
                f'<div class="fc-desc">{feat["desc"]}</div>'
                f'<ul class="fc-list">{li_html}</ul>'
                f"</div>",
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS PROFILES
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("")
st.divider()
st.markdown("")
st.markdown('<div class="sec-over">Expertise Levels</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sec-title">Choose Your Depth.</div>',
    unsafe_allow_html=True,
)
st.markdown("")

_PROFILES = [
    ("Beginner", "Core indicators + top headlines", "10 queries", "#22d68a"),
    ("Novice", "EMA crossovers, risk metrics, composite score", "25 queries", "#00c8ff"),
    ("Intermediate", "Fibonacci, VWAP, insider activity, MF holdings", "50 queries", "#a37eff"),
    ("Expert", "All 40+ tools, options chain, chart patterns", "100 queries", "#ff6b6b"),
]

prof_cols = st.columns(4)
for col, (label, desc, queries, color) in zip(prof_cols, _PROFILES):
    with col:
        st.markdown(
            f'<div class="profile-card">'
            f'<div class="profile-label" style="color:{color};">{label}</div>'
            f'<div class="pipe-name">{desc}</div>'
            f'<div class="profile-queries">{queries}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  BOTTOM CTA
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("")
st.divider()
st.markdown("")

st.markdown(
    '<div class="bottom-tag">'
    "Enter a ticker. Pick your level. Get a full report in minutes."
    "</div>",
    unsafe_allow_html=True,
)

with st.container():
    _bl, _bc, _br = st.columns([2, 1, 2])
    with _bc:
        st.markdown('<div class="cta-wrap">', unsafe_allow_html=True)
        if st.button(
            "\u2002Start Analysis  \u2192",
            type="primary",
            use_container_width=True,
            key="bottom_cta",
        ):
            st.switch_page("pages/1_Analysis.py")
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")
