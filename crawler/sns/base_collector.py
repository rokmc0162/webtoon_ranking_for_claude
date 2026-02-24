"""
외부 데이터 수집기 추상 베이스 클래스.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseCollector(ABC):

    def __init__(self, source_name: str, rate_limit_delay: float = 1.0):
        self.source_name = source_name
        self.rate_limit_delay = rate_limit_delay
        self.logger = logging.getLogger(f'crawler.sns.{source_name}')
        self.success_count = 0
        self.fail_count = 0
        self.skip_count = 0

    async def collect_all(self, works: List[Dict[str, str]]) -> Dict[str, int]:
        """전체 작품에 대해 외부 데이터 수집."""
        self.logger.info(f"[{self.source_name}] {len(works)}개 작품 수집 시작")

        # 타이틀 중복 제거 (외부 데이터는 타이틀 단위)
        seen = set()
        unique = []
        for w in works:
            if w['title'] not in seen:
                seen.add(w['title'])
                unique.append(w)

        self.logger.info(f"[{self.source_name}] 중복 제거 후 {len(unique)}개")

        for i, work in enumerate(unique, 1):
            try:
                collected = await self.collect_one(work['title'], work['platform'])
                if collected:
                    self.success_count += 1
                else:
                    self.skip_count += 1

                if i <= 5 or i % 50 == 0 or i == len(unique):
                    status = 'OK' if collected else 'SKIP'
                    self.logger.info(f"  [{i}/{len(unique)}] {work['title'][:30]}... {status}")
            except Exception as e:
                self.fail_count += 1
                if i <= 10:
                    self.logger.warning(f"  [{i}/{len(unique)}] {work['title'][:30]}... ERROR: {e}")

            await asyncio.sleep(self.rate_limit_delay)

        result = {
            'success': self.success_count,
            'failed': self.fail_count,
            'skipped': self.skip_count,
        }
        self.logger.info(f"[{self.source_name}] 완료: {result}")
        return result

    @abstractmethod
    async def collect_one(self, title: str, platform: str) -> bool:
        """단일 작품의 외부 데이터 수집. 수집 성공시 True."""
        pass
