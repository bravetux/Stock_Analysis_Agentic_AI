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
