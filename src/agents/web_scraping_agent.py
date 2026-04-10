# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

from strands import Agent
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager
from src.config.settings import settings
from src.config.aws_client import get_bedrock_session
from src.config.prompts import WEB_SCRAPING_AGENT_PROMPT
from src.tools.scraping_tools import (
    scrape_google_finance,
    scrape_yahoo_finance_page,
    scrape_moneycontrol,
)
from src.tools.chartink_tools import (
    scrape_chartink_screener,
    get_chartink_stock_data,
)


def create_web_scraping_agent() -> Agent:
    """Create the Web Scraping specialist agent."""
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
            scrape_google_finance,
            scrape_yahoo_finance_page,
            scrape_moneycontrol,
            scrape_chartink_screener,
            get_chartink_stock_data,
        ],
        system_prompt=WEB_SCRAPING_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
