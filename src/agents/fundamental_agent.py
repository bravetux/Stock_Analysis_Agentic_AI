# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import FUNDAMENTAL_AGENT_PROMPT
from src.tools.screener_tools import scrape_screener_in
from src.tools.market_data_tools import get_stock_quote, get_historical_data


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
        ],
        system_prompt=FUNDAMENTAL_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
