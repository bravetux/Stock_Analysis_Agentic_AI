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

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import FUNDAMENTAL_AGENT_PROMPT
from src.tools.screener_tools import scrape_screener_in
from src.tools.market_data_tools import get_stock_quote, get_historical_data
from src.tools.fundamental_tools import (
    get_insider_transactions,
    get_mutual_fund_holdings,
    get_earnings_calendar,
)


def create_fundamental_agent() -> Agent:
    """Create the Fundamental Analysis specialist agent."""
    model = BedrockModel(
        boto_session=get_bedrock_session(),
        model_id=settings.bedrock_model_id,
        temperature=settings.agent_temperature,
        top_p=settings.agent_top_p,
        max_tokens=settings.agent_max_tokens,
    )

    return Agent(
        model=model,
        tools=[
            scrape_screener_in,
            get_stock_quote,
            get_historical_data,
            get_insider_transactions,
            get_mutual_fund_holdings,
            get_earnings_calendar,
        ],
        system_prompt=FUNDAMENTAL_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
