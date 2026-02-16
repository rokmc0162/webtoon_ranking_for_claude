"""
Base agent class for crawler system.

Provides standardized interface and retry logic for all platform crawlers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any
from playwright.async_api import Browser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@dataclass
class AgentResult:
    """Result of agent execution."""
    success: bool
    platform: str
    data: Optional[List[Dict[str, Any]]] = None
    count: int = 0
    error: Optional[str] = None
    attempts: int = 1

    def __post_init__(self):
        if self.data:
            self.count = len(self.data)


class CrawlerAgent(ABC):
    """
    Base class for all crawler agents.

    Each platform implements this interface with platform-specific crawling logic.
    Provides automatic retry with exponential backoff and standardized error handling.
    """

    def __init__(self, platform_id: str, platform_name: str, url: str):
        """
        Initialize crawler agent.

        Args:
            platform_id: Platform identifier (e.g., 'piccoma')
            platform_name: Display name (e.g., '픽코마 (SMARTOON)')
            url: Target URL to crawl
        """
        self.platform_id = platform_id
        self.platform_name = platform_name
        self.url = url
        self.max_retries = 3
        self.retry_delays = [5, 15, 30]  # Exponential backoff in seconds
        self.logger = logging.getLogger(f'crawler.agents.{platform_id}')

    async def execute(self, browser: Browser) -> AgentResult:
        """
        Execute crawler with automatic retry logic.

        Args:
            browser: Playwright browser instance

        Returns:
            AgentResult with success status and data/error
        """
        self.logger.info(f"Starting {self.platform_name} crawler")

        for attempt in range(self.max_retries):
            try:
                # Attempt to crawl
                data = await self.crawl(browser)

                # Validate data
                if self.validate(data):
                    # Save to database
                    date = datetime.now().strftime('%Y-%m-%d')
                    await self.save(date, data)

                    self.logger.info(
                        f"✅ {self.platform_name}: {len(data)}개 작품 수집 완료"
                    )

                    return AgentResult(
                        success=True,
                        platform=self.platform_id,
                        data=data,
                        attempts=attempt + 1
                    )
                else:
                    raise ValueError(f"Data validation failed: {len(data)} items")

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {error_msg}"
                )

                # If not last attempt, wait and retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[attempt]
                    self.logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    # Final attempt failed
                    self.logger.error(
                        f"❌ {self.platform_name} 실패 (모든 재시도 소진): {error_msg}"
                    )

                    return AgentResult(
                        success=False,
                        platform=self.platform_id,
                        error=error_msg,
                        attempts=attempt + 1
                    )

        # Should never reach here
        return AgentResult(
            success=False,
            platform=self.platform_id,
            error="Unknown error",
            attempts=self.max_retries
        )

    @abstractmethod
    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """
        Platform-specific crawling logic.

        Must be implemented by each platform agent.

        Args:
            browser: Playwright browser instance

        Returns:
            List of ranking items (dicts with rank, title, genre, url, etc.)
        """
        pass

    def validate(self, data: List[Dict[str, Any]]) -> bool:
        """
        Validate crawled data.

        Args:
            data: Crawled ranking data

        Returns:
            True if data is valid, False otherwise
        """
        # Basic validation: at least 10 items
        if not data or len(data) < 10:
            self.logger.warning(f"Validation failed: only {len(data) if data else 0} items")
            return False

        # Check that each item has required fields
        required_fields = ['rank', 'title', 'url']
        for item in data:
            if not all(field in item for field in required_fields):
                self.logger.warning(f"Validation failed: missing required fields in item {item}")
                return False

        return True

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """
        Save crawled data to database and JSON backup.

        Args:
            date: Date string (YYYY-MM-DD)
            data: Ranking data to save
        """
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # Save to SQLite
        save_rankings(date, self.platform_id, data)
        self.logger.debug(f"Saved {len(data)} items to database")

        # Save works metadata (thumbnails)
        works_meta = [
            {
                'title': item['title'],
                'thumbnail_url': item.get('thumbnail_url', ''),
                'url': item.get('url', ''),
            }
            for item in data
            if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta)

        # Backup to JSON
        backup_to_json(date, self.platform_id, data)
        self.logger.debug(f"Backed up to JSON")
