"""
YouTube Playwright 크롤러.
- API 키 불필요 — 브라우저로 YouTube 검색 결과 직접 스크래핑
- "{만화 제목} PV 公式" 검색 → 조회수 수집
"""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page

from crawler.sns.base_collector import BaseCollector
from crawler.sns.external_db import (
    get_cached_external_id, save_external_id, save_external_metrics_batch
)

logger = logging.getLogger('crawler.sns.youtube')


def parse_view_count(text: str) -> Optional[int]:
    """YouTube 조회수 텍스트를 숫자로 변환.
    예: '123万回視聴' → 1230000, '1.5万回' → 15000, '1,234回視聴' → 1234
        '1.2M views' → 1200000, '123K views' → 123000
    """
    if not text:
        return None

    text = text.strip().replace(',', '').replace(' ', '')

    # 일본어: 億, 万
    m = re.search(r'([\d.]+)\s*億', text)
    if m:
        return int(float(m.group(1)) * 100_000_000)

    m = re.search(r'([\d.]+)\s*万', text)
    if m:
        return int(float(m.group(1)) * 10_000)

    # 영어: B, M, K
    m = re.search(r'([\d.]+)\s*B', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000_000_000)

    m = re.search(r'([\d.]+)\s*M', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000_000)

    m = re.search(r'([\d.]+)\s*K', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000)

    # 숫자만
    m = re.search(r'([\d]+)', text)
    if m:
        return int(m.group(1))

    return None


class YoutubeCollector(BaseCollector):

    def __init__(self, max_titles: int = 80):
        super().__init__(source_name='youtube', rate_limit_delay=3.0)
        self.max_titles = max_titles
        self._collected = 0
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def _ensure_browser(self):
        """브라우저가 없으면 시작."""
        if self._browser is None:
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
            ctx = await self._browser.new_context(
                locale='ja-JP',
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36',
            )
            self._page = await ctx.new_page()
            # YouTube 쿠키 동의 우회
            await self._page.goto('https://www.youtube.com', wait_until='domcontentloaded')
            await asyncio.sleep(2)
            # 쿠키 동의 버튼 클릭 (있으면)
            try:
                consent_btn = self._page.locator(
                    'button:has-text("Accept all"), button:has-text("すべて同意"), '
                    'button:has-text("Agree"), button:has-text("同意")'
                )
                if await consent_btn.count() > 0:
                    await consent_btn.first.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

    async def close(self):
        """브라우저 종료."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

    async def collect_all(self, works):
        """오버라이드: 브라우저 시작/종료 래핑."""
        try:
            await self._ensure_browser()
            return await super().collect_all(works)
        finally:
            await self.close()

    async def collect_one(self, title: str, platform: str) -> bool:
        if self._collected >= self.max_titles:
            return False

        cached_id = get_cached_external_id(title, 'youtube')

        if cached_id and cached_id != 'NOT_FOUND':
            # 캐시된 video ID가 있으면 개별 영상 페이지에서 조회수 수집
            video_ids = cached_id.split(',')
            stats = await self._get_stats_from_pages(video_ids[:3])
            if stats:
                self._save_metrics(title, stats)
                return True
            return False

        if cached_id == 'NOT_FOUND':
            return False

        # 새로 검색
        results = await self._search_youtube(title)

        if not results:
            # 찾지 못함 — NOT_FOUND 캐시
            save_external_id(
                platform=platform, title=title, source='youtube',
                external_id='NOT_FOUND', external_title='',
                match_score=0
            )
            return False

        video_ids = [r['id'] for r in results]
        save_external_id(
            platform=platform, title=title, source='youtube',
            external_id=','.join(video_ids[:5]),
            external_title=results[0].get('title', '')[:100],
            match_score=0.8
        )
        self._collected += 1

        # 검색 결과에서 이미 조회수를 얻었으므로 바로 저장
        views = [r['views'] for r in results if r.get('views')]
        if views:
            metrics = {
                'pv_views': max(views),
                'pv_count': len(views),
                'total_views': sum(views),
            }
            save_external_metrics_batch(title, 'youtube', metrics)
            return True

        return False

    async def _search_youtube(self, title: str) -> List[Dict]:
        """YouTube에서 PV 검색, 상위 결과 반환."""
        page = self._page
        if not page:
            return []

        query = f'{title} PV 公式'
        search_url = f'https://www.youtube.com/results?search_query={_url_encode(query)}'

        try:
            await page.goto(search_url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(3)

            # 검색 결과에서 비디오 정보 추출
            results = await page.evaluate('''() => {
                const videos = [];
                const items = document.querySelectorAll('ytd-video-renderer');
                for (let i = 0; i < Math.min(items.length, 5); i++) {
                    const item = items[i];
                    const titleEl = item.querySelector('#video-title');
                    const metaEl = item.querySelector('#metadata-line span');
                    const linkEl = item.querySelector('a#video-title');

                    let videoId = '';
                    if (linkEl) {
                        const href = linkEl.getAttribute('href') || '';
                        const match = href.match(/v=([^&]+)/);
                        if (match) videoId = match[1];
                    }

                    videos.push({
                        title: titleEl ? titleEl.textContent.trim() : '',
                        views_text: metaEl ? metaEl.textContent.trim() : '',
                        id: videoId,
                    });
                }
                return videos;
            }''')

            # 조회수 파싱
            parsed = []
            for r in results:
                if not r.get('id'):
                    continue
                views = parse_view_count(r.get('views_text', ''))
                parsed.append({
                    'id': r['id'],
                    'title': r.get('title', ''),
                    'views': views,
                })

            return parsed

        except Exception as e:
            logger.warning(f"YouTube search error for '{title[:30]}': {e}")
            return []

    async def _get_stats_from_pages(self, video_ids: List[str]) -> List[Dict]:
        """개별 비디오 페이지에서 조회수 수집 (캐시된 ID 재수집용)."""
        page = self._page
        if not page:
            return []

        stats = []
        for vid in video_ids:
            try:
                url = f'https://www.youtube.com/watch?v={vid}'
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(2)

                view_text = await page.evaluate('''() => {
                    // 조회수 텍스트 찾기
                    const infoEl = document.querySelector(
                        '#count .ytd-video-primary-info-renderer, ' +
                        'ytd-video-primary-info-renderer #info-strings yt-formatted-string, ' +
                        '#info-container yt-formatted-string'
                    );
                    if (infoEl) return infoEl.textContent.trim();

                    // 대안: description 영역
                    const viewEl = document.querySelector(
                        '#info span.view-count, ' +
                        'ytd-watch-metadata #info span'
                    );
                    if (viewEl) return viewEl.textContent.trim();

                    return '';
                }''')

                views = parse_view_count(view_text)
                if views:
                    stats.append({'viewCount': views})
            except Exception:
                continue

        return stats

    def _save_metrics(self, title: str, stats: List[Dict]):
        total = sum(s.get('viewCount', 0) for s in stats)
        metrics = {
            'pv_views': max(s.get('viewCount', 0) for s in stats),
            'pv_count': len(stats),
            'total_views': total,
        }
        save_external_metrics_batch(title, 'youtube', metrics)


def _url_encode(text: str) -> str:
    """간단한 URL 인코딩."""
    from urllib.parse import quote
    return quote(text, safe='')
