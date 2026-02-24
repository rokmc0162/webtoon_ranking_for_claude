"""
Google Trends 수집기 (pytrends-modern).
- 일본(JP)에서의 검색 관심도를 0-100 스케일로 수집
- 5개씩 배치 비교 (Google Trends 최대 5개)
"""
import asyncio
import logging
from typing import List, Dict

try:
    from pytrends.request import TrendReq
    HAS_PYTRENDS = True
except ImportError:
    try:
        from pytrends_modern import TrendReq
        HAS_PYTRENDS = True
    except ImportError:
        HAS_PYTRENDS = False

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import save_external_metrics_batch

logger = logging.getLogger('crawler.sns.google_trends')


class TrendsCollector(BaseCollector):

    def __init__(self):
        super().__init__(source_name='google_trends', rate_limit_delay=5.0)
        if not HAS_PYTRENDS:
            logger.warning("pytrends-modern 미설치. pip install pytrends-modern")
            self._available = False
        else:
            self._available = True

    async def collect_all(self, works: List[Dict[str, str]]) -> Dict[str, int]:
        """오버라이드: 5개씩 배치로 Google Trends 비교."""
        if not self._available:
            logger.warning("[google_trends] pytrends-modern 미설치, 스킵")
            return {'success': 0, 'failed': 0, 'skipped': len(works)}

        self.logger.info(f"[google_trends] {len(works)}개 작품 수집 시작")

        # 타이틀 중복 제거
        seen = set()
        unique_titles = []
        for w in works:
            if w['title'] not in seen:
                seen.add(w['title'])
                unique_titles.append(w['title'])

        self.logger.info(f"[google_trends] 중복 제거 후 {len(unique_titles)}개")

        # 5개씩 배치
        batches = [unique_titles[i:i+5] for i in range(0, len(unique_titles), 5)]

        for batch_idx, batch in enumerate(batches, 1):
            try:
                results = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_trends, batch
                )
                for title, metrics in results.items():
                    save_external_metrics_batch(title, 'google_trends', metrics)
                    self.success_count += 1

                if batch_idx <= 3 or batch_idx % 10 == 0 or batch_idx == len(batches):
                    self.logger.info(
                        f"  [batch {batch_idx}/{len(batches)}] "
                        f"{len(results)} titles OK"
                    )
            except Exception as e:
                self.fail_count += len(batch)
                if batch_idx <= 5:
                    self.logger.warning(
                        f"  [batch {batch_idx}/{len(batches)}] ERROR: {e}"
                    )

            await asyncio.sleep(self.rate_limit_delay)

        result = {
            'success': self.success_count,
            'failed': self.fail_count,
            'skipped': self.skip_count,
        }
        self.logger.info(f"[google_trends] 완료: {result}")
        return result

    def _fetch_trends(self, titles: List[str]) -> Dict[str, Dict]:
        """동기 함수: pytrends로 관심도 조회."""
        try:
            pytrends = TrendReq(hl='ja', tz=-540)
            # 제목이 너무 길면 잘라서 검색
            kw_list = [t[:50] for t in titles]
            pytrends.build_payload(kw_list, timeframe='today 3-m', geo='JP')
            df = pytrends.interest_over_time()

            if df is None or df.empty:
                return {}

            results = {}
            for title, kw in zip(titles, kw_list):
                if kw not in df.columns:
                    continue
                series = df[kw]
                latest = int(series.iloc[-1]) if len(series) > 0 else 0
                avg = round(float(series.mean()), 1)
                results[title] = {
                    'interest_score': latest,
                    'interest_avg_3m': avg,
                }
            return results

        except Exception as e:
            logger.warning(f"Google Trends fetch error: {e}")
            import time
            time.sleep(30)  # 429 대비 대기
            return {}

    async def collect_one(self, title: str, platform: str) -> bool:
        """개별 수집 (collect_all에서 배치 처리하므로 보통 사용 안 함)."""
        if not self._available:
            return False
        results = await asyncio.get_event_loop().run_in_executor(
            None, self._fetch_trends, [title]
        )
        if title in results:
            save_external_metrics_batch(title, 'google_trends', results[title])
            return True
        return False
