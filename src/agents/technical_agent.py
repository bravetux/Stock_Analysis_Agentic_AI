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
from src.config.prompts import TECHNICAL_AGENT_PROMPT
from src.tools.technical_analysis_tools import (
    calculate_200dma,
    calculate_macd,
    calculate_support_resistance,
    estimate_next_high_low,
    get_technical_summary,
    calculate_ema_crossovers,
    detect_golden_death_cross,
    calculate_fibonacci_levels,
    calculate_vwap,
    calculate_obv,
    calculate_ichimoku,
    calculate_williams_r,
    calculate_adx_directional,
    calculate_trend_strength,
    detect_chart_patterns,
    calculate_risk_metrics,
    calculate_relative_strength,
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
            calculate_ema_crossovers,
            detect_golden_death_cross,
            calculate_fibonacci_levels,
            calculate_vwap,
            calculate_obv,
            calculate_ichimoku,
            calculate_williams_r,
            calculate_adx_directional,
            calculate_trend_strength,
            detect_chart_patterns,
            calculate_risk_metrics,
            calculate_relative_strength,
        ],
        system_prompt=TECHNICAL_AGENT_PROMPT,
        conversation_manager=SlidingWindowConversationManager(window_size=10),
    )
