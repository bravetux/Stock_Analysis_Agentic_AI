# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import NEWS_AGENT_PROMPT
from src.tools.news_tools import (
    search_google_news,
    search_news_batch,
    extract_article_content,
    search_location_news,
)


def create_news_agent() -> Agent:
    """Create the News Intelligence specialist agent."""
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
            search_google_news,
            search_news_batch,
            extract_article_content,
            search_location_news,
        ],
        system_prompt=NEWS_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
