# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import os
import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Set test environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.2")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "4096")
    monkeypatch.setenv("DEFAULT_EXCHANGE", "NSE")
    monkeypatch.setenv("STOCKS_FILE", "stocks.txt")
    monkeypatch.setenv("NEWS_SEARCH_COUNT", "10")
    monkeypatch.setenv("SCRAPE_DELAY_SECONDS", "0")
    monkeypatch.setenv("NEWS_API_DELAY", "0")
