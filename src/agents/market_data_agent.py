# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import MARKET_DATA_AGENT_PROMPT
from src.tools.market_data_tools import (
    detect_exchange_for_ticker,
    get_stock_quote,
    get_historical_data,
    get_market_overview,
)


def create_market_data_agent() -> Agent:
    """Create the Market Data specialist agent."""
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
            detect_exchange_for_ticker,
            get_stock_quote,
            get_historical_data,
            get_market_overview,
        ],
        system_prompt=MARKET_DATA_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
