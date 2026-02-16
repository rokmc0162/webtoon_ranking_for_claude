"""
Agent-based crawler system for Japanese webtoon platforms.

Each platform crawler is implemented as an independent agent with:
- Retry logic with exponential backoff
- Error isolation (one agent failure doesn't affect others)
- Standardized interface for crawling, validation, and data storage
"""

from .base_agent import CrawlerAgent, AgentResult

__all__ = ['CrawlerAgent', 'AgentResult']
