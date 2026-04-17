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

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # AWS credentials
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_session_token: str = Field(default="", alias="AWS_SESSION_TOKEN")
    aws_region: str = Field(default="us-east-1", alias="AWS_DEFAULT_REGION")

    # LLM
    bedrock_model_id: str = Field(
        default="anthropic.claude-sonnet-4-20250514-v1:0", alias="BEDROCK_MODEL_ID"
    )
    agent_temperature: float = Field(default=0.2, alias="AGENT_TEMPERATURE")
    agent_top_p: float = Field(default=0.9, alias="AGENT_TOP_P")
    agent_max_tokens: int = Field(default=8192, alias="AGENT_MAX_TOKENS")

    # Stock Analysis
    default_exchange: str = Field(default="NSE", alias="DEFAULT_EXCHANGE")
    stocks_file: str = Field(default="stocks.txt", alias="STOCKS_FILE")
    news_search_count: int = Field(default=100, alias="NEWS_SEARCH_COUNT")
    historical_days: int = Field(default=365, alias="HISTORICAL_DAYS")
    dma_period: int = Field(default=200, alias="DMA_PERIOD")

    # Scoring
    risk_free_rate: float = Field(default=0.065, alias="RISK_FREE_RATE")
    var_confidence: float = Field(default=0.95, alias="VAR_CONFIDENCE")
    technical_weight: float = Field(default=0.40, alias="TECHNICAL_WEIGHT")
    fundamental_weight: float = Field(default=0.35, alias="FUNDAMENTAL_WEIGHT")
    sentiment_weight: float = Field(default=0.25, alias="SENTIMENT_WEIGHT")

    # Cache
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_dir: str = Field(default=".cache", alias="CACHE_DIR")

    # Google Trends
    trends_timeframe: str = Field(default="today 3-m", alias="TRENDS_TIMEFRAME")

    # Rate Limiting
    scrape_delay_seconds: float = Field(default=1.0, alias="SCRAPE_DELAY_SECONDS")
    news_api_delay: float = Field(default=0.5, alias="NEWS_API_DELAY")

    # Session
    session_backend: str = Field(default="file", alias="SESSION_BACKEND")
    session_dir: str = Field(default=".sessions", alias="SESSION_DIR")

    # Report Database
    report_cache_hours: int = Field(default=720, alias="REPORT_CACHE_HOURS")
    reports_dir: str = Field(default="reports", alias="REPORTS_DIR")
    db_path: str = Field(default="data/reports.db", alias="DB_PATH")

    # Research-agent (Claude-style investigation) settings
    research_mode_enabled: bool = Field(default=False, alias="RESEARCH_MODE_ENABLED")
    lead_temperature: float = Field(default=0.4, alias="LEAD_TEMPERATURE")
    synthesizer_temperature: float = Field(default=0.2, alias="SYNTHESIZER_TEMPERATURE")
    enable_extended_thinking: bool = Field(default=False, alias="ENABLE_EXTENDED_THINKING")
    thinking_budget_tokens: int = Field(default=8000, alias="THINKING_BUDGET_TOKENS")
    enable_prompt_cache: bool = Field(default=False, alias="ENABLE_PROMPT_CACHE")
    max_followup_loops: int = Field(default=1, ge=0, le=3, alias="MAX_FOLLOWUP_LOOPS")
    investigator_timeout_s: int = Field(default=180, alias="INVESTIGATOR_TIMEOUT_S")
    research_max_threads: int = Field(default=6, ge=2, le=10, alias="RESEARCH_MAX_THREADS")

    # Phase 2a: macro + analyst consensus
    macro_snapshot_cache_minutes: int = Field(default=60, alias="MACRO_SNAPSHOT_CACHE_MINUTES")
    macro_history_retention_days: int = Field(default=90, alias="MACRO_HISTORY_RETENTION_DAYS")
    macro_fetch_timeout_seconds: int = Field(default=8, alias="MACRO_FETCH_TIMEOUT_SECONDS")
    enable_analyst_consensus: bool = Field(default=True, alias="ENABLE_ANALYST_CONSENSUS")
    enable_macro_context: bool = Field(default=True, alias="ENABLE_MACRO_CONTEXT")


# Singleton
settings = Settings()
