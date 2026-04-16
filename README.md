# Stock Analysis AI Agent

A multi-agent stock analysis system built with the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) that analyzes stocks across **BSE**, **NSE**, and **NASDAQ** exchanges using technical analysis, news intelligence, fundamental data, and web scraping.

## Architecture

**Orchestrator + 5 Specialist Sub-Agents:**

```
                    ┌─────────────────────┐
                    │    Orchestrator      │
                    │  (routes & reports)  │
                    └────────┬────────────┘
          ┌──────────┬───────┼───────┬──────────┐
          ▼          ▼       ▼       ▼          ▼
    ┌──────────┐ ┌───────┐ ┌─────┐ ┌──────┐ ┌────────┐
    │Technical │ │ News  │ │Fund.│ │Market│ │  Web   │
    │  Agent   │ │ Agent │ │Agent│ │ Data │ │Scraping│
    └──────────┘ └───────┘ └─────┘ └──────┘ └────────┘
```

| Agent | What It Does |
|-------|-------------|
| **Technical** | 200DMA breakpoints, MACD crossovers, support/resistance, ATR + Bollinger price estimates, RSI/ADX/Stochastic dashboard |
| **News** | 100 search query types across 10 categories, location-aware sources, article extraction |
| **Fundamental** | Screener.in (Indian stocks), yfinance (US stocks) — PE, ROE, ROCE, debt, shareholding |
| **Market Data** | Real-time quotes via yfinance, nsetools, bsedata; historical OHLCV; market indices |
| **Web Scraping** | Google Finance, Yahoo Finance, Chartink screener scans, MoneyControl |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS credentials with Bedrock access (for the LLM)

### Install & Run

```bash
# Clone
git clone https://github.com/bravetux/Stock_Analysis_Agentic_AI.git
cd Stock_Analysis_Agentic_AI

# Install dependencies
uv sync

# Configure
cp .env.example .env
# Edit .env with your AWS credentials

# Run Streamlit UI
uv run streamlit run src/ui/app.py

# Or use CLI
uv run python main.py NSE:RELIANCE
uv run python main.py AAPL NASDAQ
uv run python main.py --batch stocks.txt
```

### Docker

```bash
docker compose up --build
# UI available at http://localhost:8501
```

## Analysis Profiles

Choose an analysis level based on your expertise. Default is **Novice**.

| Level | News Queries | Features Included |
|-------|:-----------:|-------------------|
| **Beginner** | 10 | Current price, 200DMA trend, top 5 headlines, simple UP/DOWN/SIDEWAYS verdict |
| **Novice** | 25 | + MACD momentum, news sentiment breakdown, key fundamentals (PE, ROE, D/E) |
| **Intermediate** | 50 | + Support/resistance levels, price estimates, multi-source scraping, detailed fundamentals |
| **Expert** | 100 | + RSI/Stochastic/ADX dashboard, all 100 news query types, Chartink scans, full report |

Each profile controls which tools are loaded, how many news queries run, and the depth of the output report.

**CLI usage:**

```bash
uv run python main.py NSE:RELIANCE --profile beginner
uv run python main.py AAPL --profile expert
```

## News Sources

News sources are configured in [`src/config/news_sources.yaml`](src/config/news_sources.yaml) — a single YAML file with 50+ financial websites organized by region:

| Region | Enabled Sources | Examples |
|--------|:--------------:|---------|
| **India** | 22 | MoneyControl, Economic Times, LiveMint, NDTV Profit, Screener, Trendlyne, NSE, BSE, SEBI |
| **US** | 24 | CNBC, Bloomberg, Reuters, WSJ, Seeking Alpha, Zacks, TipRanks, Benzinga, SEC |
| **Global** | 4 | Reuters Global, Google Finance, TradingView, Nasdaq.com |

To add or remove a source, edit the YAML file — no code changes needed:

```yaml
india:
  - name: MoneyControl
    domain: moneycontrol.com
    category: general
    enabled: true       # toggle to false to disable
```

## Supported Exchanges & Ticker Formats

| Exchange | Formats | Data Sources |
|----------|---------|-------------|
| **NSE** | `NSE:RELIANCE`, `RELIANCE.NS`, `RELIANCE` | nsetools, yfinance |
| **BSE** | `BSE:500325`, `500325.BO` | bsedata, yfinance |
| **NASDAQ** | `NASDAQ:AAPL`, `AAPL` | yfinance |

## Batch Mode

Create a `stocks.txt` file with one ticker per line:

```text
# Indian stocks
NSE:RELIANCE
NSE:TCS
NSE:INFY

# US stocks
NASDAQ:AAPL
NASDAQ:MSFT
```

Run via CLI or upload through the Streamlit UI.

## Configuration

All settings are in `.env` (copy from `.env.example`):

| Setting | Default | Description |
|---------|---------|-------------|
| `BEDROCK_MODEL_ID` | `anthropic.claude-sonnet-4-20250514-v1:0` | AWS Bedrock LLM model |
| `DEFAULT_EXCHANGE` | `NSE` | Default exchange for ambiguous tickers |
| `HISTORICAL_DAYS` | `365` | Days of historical data to fetch |
| `DMA_PERIOD` | `200` | Moving average period |
| `SCRAPE_DELAY_SECONDS` | `1.0` | Rate limit between scraping requests |
| `NEWS_API_DELAY` | `0.5` | Rate limit between news queries |

## Tests

```bash
uv run pytest tests/ -v
```

Test coverage includes exchange detection, search query generation, all tool modules (technical analysis, market data, news, scraping, screener, chartink, batch), and orchestrator creation.

## Project Structure

```
├── main.py                          # CLI entry point
├── src/
│   ├── ui/app.py                    # Streamlit web interface
│   ├── agents/
│   │   ├── orchestrator.py          # Main coordinator agent
│   │   ├── technical_agent.py       # Technical analysis specialist
│   │   ├── news_agent.py            # News intelligence specialist
│   │   ├── fundamental_agent.py     # Fundamental analysis specialist
│   │   ├── market_data_agent.py     # Market data specialist
│   │   └── web_scraping_agent.py    # Web scraping specialist
│   ├── config/
│   │   ├── settings.py              # Pydantic settings from .env
│   │   ├── analysis_profiles.py     # Beginner/Novice/Intermediate/Expert profiles
│   │   ├── news_sources.yaml        # 50+ configurable news sources
│   │   ├── news_sources.py          # YAML loader for news sources
│   │   ├── search_queries.py        # 100 search query templates
│   │   ├── exchanges.py             # Exchange detection & normalization
│   │   ├── prompts.py               # Agent system prompts
│   │   └── aws_client.py            # Bedrock session factory
│   └── tools/
│       ├── technical_analysis_tools.py  # 200DMA, MACD, S/R, estimates, dashboard
│       ├── market_data_tools.py         # Quotes, historical data, indices
│       ├── news_tools.py               # Google News search & extraction
│       ├── scraping_tools.py           # Google Finance, Yahoo, MoneyControl
│       ├── screener_tools.py           # Screener.in fundamentals
│       ├── chartink_tools.py           # Chartink screener scans
│       └── batch_tools.py             # Batch stock file reader
├── tests/                           # Pytest test suite
├── pyproject.toml                   # Dependencies & build config
├── Dockerfile                       # Container build
├── docker-compose.yml               # Docker compose setup
└── stocks.txt                       # Sample batch input
```

## Disclaimer

This tool is for **informational and educational purposes only**. It is not investment advice. Always do your own research and consult a qualified financial advisor before making investment decisions.

## License

See repository for license details.
