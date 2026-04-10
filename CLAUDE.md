# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AG-UC-0999: Stock Analysis AI Agent — a Strands Agents SDK-based tool that analyzes stocks across BSE, NSE, and NASDAQ exchanges using technical analysis (200DMA, MACD), 100 news search query types, fundamentals (Screener.in, Yahoo Finance), and web scraping (Google Finance, Chartink, MoneyControl).

## Build & Run Commands

```bash
# Install dependencies
uv sync

# Run Streamlit UI
uv run streamlit run src/ui/app.py

# Run CLI mode
uv run python main.py NSE:RELIANCE
uv run python main.py --batch stocks.txt

# Run tests
uv run pytest tests/ -v

# Run single test file
uv run pytest tests/test_exchanges.py -v

# Docker
docker compose up --build
```

## Architecture

**Orchestrator + 5 specialist sub-agents** pattern (same as sibling projects 649, 887, 1128):

- **Orchestrator** (`src/agents/orchestrator.py`) — routes to specialists, aggregates reports, handles batch mode via `ThreadPoolExecutor`
- **Technical Agent** — 200DMA breakpoints, MACD crossovers, support/resistance, ATR+Bollinger price estimates
- **News Agent** — 100 search query types across 10 categories, location-aware (India/US), GoogleNews library
- **Fundamental Agent** — Screener.in (Indian stocks), yfinance fundamentals
- **Market Data Agent** — yfinance, nsetools, bsedata for multi-exchange quotes
- **Web Scraping Agent** — Google Finance, Yahoo Finance, Chartink, MoneyControl via BeautifulSoup

## Key Patterns

- **Tools**: `@tool` decorator from `strands`, tested via `.__wrapped__()` to bypass decorator
- **Config**: `pydantic-settings` singleton in `src/config/settings.py`, loaded from `.env`
- **Exchanges**: `src/config/exchanges.py` handles ticker detection/normalization across NSE/BSE/NASDAQ
- **Search queries**: `src/config/search_queries.py` has 100 templates in 10 categories
- **Rate limiting**: `scrape_delay_seconds` and `news_api_delay` settings control scraping speed

## Parent Context

Part of the `ai_arena` ecosystem. Sibling projects: 649 (AWS Monitor), 887 (Training Chatbot), 1128 (Code Analysis). All use Strands Agents + Streamlit + Bedrock + uv.
