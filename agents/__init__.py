"""
The Second Mind - Agent Module
Contains specialized agents that mimic human learning and reasoning processes.
"""

from .base_agent import BaseAgent
from .generation_agent import GenerationAgent
from .reflection_agent import ReflectionAgent
from .ranking_agent import RankingAgent
from .evolution_agent import EvolutionAgent
from .proximity_agent import ProximityAgent
from .meta_review_agent import MetaReviewAgent

__all__ = [
    'BaseAgent',
    'GenerationAgent',
    'ReflectionAgent', 
    'RankingAgent',
    'EvolutionAgent',
    'ProximityAgent',
    'MetaReviewAgent'
]