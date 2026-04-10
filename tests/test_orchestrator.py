# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from src.agents.orchestrator import run_parallel_analysis


class TestRunParallelAnalysis:
    @patch("src.agents.orchestrator.create_web_scraping_agent")
    @patch("src.agents.orchestrator.create_market_data_agent")
    @patch("src.agents.orchestrator.create_fundamental_agent")
    @patch("src.agents.orchestrator.create_news_agent")
    @patch("src.agents.orchestrator.create_technical_agent")
    def test_returns_all_keys(self, mock_tech, mock_news, mock_fund, mock_market, mock_web):
        # Create mock agents that return strings when called
        for mock_creator in [mock_tech, mock_news, mock_fund, mock_market, mock_web]:
            mock_agent = MagicMock()
            mock_agent.return_value = "Test analysis result"
            mock_creator.return_value = mock_agent

        results = run_parallel_analysis("RELIANCE", "NSE")
        assert "technical" in results
        assert "news" in results
        assert "fundamental" in results
        assert "market_data" in results
        assert "web_scraping" in results

    @patch("src.agents.orchestrator.create_web_scraping_agent")
    @patch("src.agents.orchestrator.create_market_data_agent")
    @patch("src.agents.orchestrator.create_fundamental_agent")
    @patch("src.agents.orchestrator.create_news_agent")
    @patch("src.agents.orchestrator.create_technical_agent")
    def test_handles_agent_failure(self, mock_tech, mock_news, mock_fund, mock_market, mock_web):
        # Technical agent fails, others succeed
        mock_tech_agent = MagicMock(side_effect=Exception("Agent failed"))
        mock_tech.return_value = mock_tech_agent

        for mock_creator in [mock_news, mock_fund, mock_market, mock_web]:
            mock_agent = MagicMock()
            mock_agent.return_value = "OK"
            mock_creator.return_value = mock_agent

        results = run_parallel_analysis("RELIANCE", "NSE")
        assert "Error" in results["technical"]
        assert results["news"] == "OK"
