# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

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

    # Rate Limiting
    scrape_delay_seconds: float = Field(default=1.0, alias="SCRAPE_DELAY_SECONDS")
    news_api_delay: float = Field(default=0.5, alias="NEWS_API_DELAY")

    # Session
    session_backend: str = Field(default="file", alias="SESSION_BACKEND")
    session_dir: str = Field(default=".sessions", alias="SESSION_DIR")


# Singleton
settings = Settings()
