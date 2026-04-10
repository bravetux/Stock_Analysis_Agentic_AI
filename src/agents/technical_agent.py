# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import TECHNICAL_AGENT_PROMPT
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_macd,
    calculate_support_resistance,
    estimate_next_high_low,
    get_technical_summary,
)


def create_technical_agent() -> Agent:
    """Create the Technical Analysis specialist agent."""
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
            calculate_200dma,
            calculate_macd,
            calculate_support_resistance,
            estimate_next_high_low,
            get_technical_summary,
        ],
        system_prompt=TECHNICAL_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
