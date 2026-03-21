"""
Asura Scans (asuracomic.net) 크롤러 에이전트

특징:
- 영어 번역 해적판 웹툰 사이트 (한국 웹툰 중심)
- SSR 방식 → HTTP 요청으로도 가능하나, Playwright로 통일
- IP 제한 없음
- 약 350~400개 시리즈
- 수집 데이터:
  1. 인기 랭킹 (Weekly/Monthly/All TOP 10)
  2. 시리즈 목록 (인기순, ~370개)
  3. 작품 상세 (별점, 팔로워, 장르, 챕터 수, 댓글 수)
  4. 댓글 (작품별)

주의:
- 해적판 사이트 → 도메인 변경/폐쇄 가능성
- 기존 일본 플랫폼 크롤링과 분리 실행
- 요청 간격 충분히 두기 (3~5초)
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from playwright.async_api import Browser, Page

logger = logging.getLogger('crawler.agents.asura')

BASE_URL = 'https://asurascans.com'


class AsuraAgent:
    """Asura Scans 크롤러 (독립 실행)"""

    def __init__(self):
        self.platform_id = 'asura'
        self.platform_name = 'Asura Scans'
        self.logger = logger
        self.results = {
            'rankings_weekly': [],
            'rankings_monthly': [],
            'rankings_all': [],
            'series_list': [],       # 인기순 전체 목록
            'series_details': [],    # 상세 메타데이터
            'comments': [],          # 댓글
        }

    async def execute(self, browser: Browser,
                      phases: List[str] = None) -> Dict[str, Any]:
        """
        크롤링 실행

        Args:
            browser: Playwright 브라우저
            phases: 실행할 페이즈 ['rankings', 'series', 'details', 'comments']
                    None이면 전부 실행

        Returns:
            {phase: count} 결과 요약
        """
        if phases is None:
            phases = ['rankings', 'series', 'details', 'comments']

        ctx = await browser.new_context(
            locale='en-US',
            viewport={'width': 1366, 'height': 768},
            ignore_https_errors=True,
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        )
        page = await ctx.new_page()
        summary = {}

        try:
            # Phase 1: 인기 랭킹 (Weekly/Monthly/All TOP 10)
            if 'rankings' in phases:
                self.logger.info("📊 [Phase 1] 인기 랭킹 수집 시작...")
                await self._crawl_rankings(page)
                summary['rankings'] = {
                    'weekly': len(self.results['rankings_weekly']),
                    'monthly': len(self.results['rankings_monthly']),
                    'all': len(self.results['rankings_all']),
                }
                self.logger.info(
                    f"   ✅ Weekly {summary['rankings']['weekly']}개, "
                    f"Monthly {summary['rankings']['monthly']}개, "
                    f"All {summary['rankings']['all']}개"
                )

            # Phase 2: 시리즈 전체 목록 (인기순)
            if 'series' in phases:
                self.logger.info("📚 [Phase 2] 시리즈 목록 수집 시작...")
                await self._crawl_series_list(page)
                summary['series'] = len(self.results['series_list'])
                self.logger.info(f"   ✅ {summary['series']}개 시리즈")

            # Phase 3: 작품 상세 + 댓글
            if 'details' in phases or 'comments' in phases:
                targets = list(self.results['series_list'])

                # DB에서 상세 미수집 작품도 타겟에 추가
                try:
                    from crawler.db import get_db_connection
                    db_conn = get_db_connection()
                    db_cur = db_conn.cursor()
                    db_cur.execute("""
                        SELECT title, url, thumbnail_url FROM works
                        WHERE platform = 'asura'
                          AND url IS NOT NULL AND url != ''
                          AND (detail_scraped_at IS NULL
                               OR detail_scraped_at < NOW() - INTERVAL '14 days')
                    """)
                    db_works = [
                        {'title': r[0], 'url': r[1], 'thumbnail_url': r[2] or ''}
                        for r in db_cur.fetchall()
                    ]
                    db_conn.close()

                    existing_urls = {s['url'] for s in targets}
                    extra = [w for w in db_works if w['url'] not in existing_urls]
                    if extra:
                        targets.extend(extra)
                        self.logger.info(
                            f"   DB에서 미수집 작품 {len(extra)}개 추가"
                        )
                except Exception as e:
                    self.logger.warning(f"   DB 미수집 작품 로드 실패: {e}")

                if not targets:
                    self.logger.warning("   ⚠️ 타겟 없음 - Phase 2 먼저 실행 필요")
                else:
                    self.logger.info(
                        f"📝 [Phase 3] 작품 상세 + 댓글 수집 시작... "
                        f"({len(targets)}개 작품)"
                    )
                    collect_comments = 'comments' in phases
                    await self._crawl_details(page, targets, collect_comments)
                    summary['details'] = len(self.results['series_details'])
                    summary['comments'] = len(self.results['comments'])
                    self.logger.info(
                        f"   ✅ 상세 {summary.get('details', 0)}개, "
                        f"댓글 {summary.get('comments', 0)}개"
                    )

            return summary

        except Exception as e:
            self.logger.error(f"❌ Asura 크롤링 실패: {e}")
            raise
        finally:
            await page.close()
            await ctx.close()

    # ===== Phase 1: 인기 랭킹 =====

    async def _crawl_rankings(self, page: Page):
        """메인 페이지에서 Weekly/Monthly/All 인기 랭킹 수집"""
        await page.goto(BASE_URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)

        # 탭 구조: button[data-state=active/inactive] → role="tabpanel"[data-state]
        # Weekly (기본 활성 탭)
        self.results['rankings_weekly'] = await self._extract_popular_tab(
            page, 'weekly'
        )

        # Monthly 탭 클릭
        monthly_tab = await page.query_selector('button:has-text("Monthly")')
        if monthly_tab:
            await monthly_tab.click()
            await page.wait_for_timeout(2000)
            self.results['rankings_monthly'] = await self._extract_popular_tab(
                page, 'monthly'
            )

        # All 탭 클릭
        all_tab = await page.query_selector('button:has-text("All")')
        if all_tab:
            await all_tab.click()
            await page.wait_for_timeout(2000)
            self.results['rankings_all'] = await self._extract_popular_tab(
                page, 'all'
            )

    async def _extract_popular_tab(self, page: Page, period: str) -> List[Dict]:
        """현재 활성 탭에서 랭킹 추출

        DOM 구조 (2026-03 기준, asurascans.com):
        - Weekly/Monthly/All 버튼 클릭 후
        - a[href*="/comics/"] 링크에서 제목+URL 추출
        """
        items = await page.evaluate("""() => {
            const results = [];

            // /comics/ 링크에서 텍스트가 있는 것만 추출
            const links = document.querySelectorAll('a[href*="/comics/"]');
            const seen = new Set();
            let rank = 0;

            for (const link of links) {
                const href = link.getAttribute('href') || '';
                if (!href.match(/\\/comics\\/[a-z]/)) continue;
                if (seen.has(href)) continue;

                // 텍스트 추출 - 줄바꿈 분리 후 첫 의미있는 줄이 제목
                const rawText = link.innerText.trim();
                if (!rawText || rawText.length < 2) continue;

                // 제목 추출: 숫자(평점)나 "Chapter"를 제거
                const lines = rawText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                let title = '';
                for (const line of lines) {
                    // 평점 숫자만 있는 줄이나 Chapter 줄은 건너뛰기
                    if (/^\\d+\\.\\d+$/.test(line)) continue;
                    if (/^Chapter/i.test(line)) continue;
                    title = line;
                    break;
                }
                if (!title || title.length < 2) continue;

                // 평점 추출
                const ratingMatch = rawText.match(/(\\d+\\.\\d+)/);
                const rating = ratingMatch ? parseFloat(ratingMatch[1]) : null;

                // 썸네일
                let thumbUrl = '';
                const img = link.querySelector('img');
                if (img) {
                    thumbUrl = img.getAttribute('src') || '';
                }

                seen.add(href);
                rank++;

                // URL 슬러그에서 전체 제목 복원
                // /comics/nano-machine-7f873ca6 → Nano Machine
                const slugMatch = href.match(/\\/comics\\/([a-z0-9-]+?)(?:-[0-9a-f]{6,})?\\/?$/);
                let fullTitle = title.replace(/\\.\\.\\.$/, '').trim();
                if (slugMatch && slugMatch[1]) {
                    const fromSlug = slugMatch[1]
                        .split('-')
                        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
                        .join(' ');
                    if (fromSlug.length > fullTitle.length) {
                        fullTitle = fromSlug;
                    }
                }

                results.push({
                    rank: rank,
                    title: fullTitle,
                    rating: rating,
                    url: href.startsWith('http') ? href :
                        'https://asurascans.com' + href,
                    thumbnail_url: thumbUrl,
                });
            }

            return results.slice(0, 10);
        }""")

        return [
            {**item, 'period': period}
            for item in items
        ]

    # ===== Phase 2: 시리즈 전체 목록 =====

    async def _crawl_series_list(self, page: Page):
        """전체 시리즈를 인기순으로 수집 (페이지네이션)

        DOM 구조:
        - 메인 그리드 카드: a[href^="series/"] (슬래시 없이 시작)
        - 사이드바 Popular: a[href^="/comics/"] (슬래시 있음)
        - 카드 innerText: "STATUS | TYPE | Title | Chapter N | Rating"
        - 15개/페이지
        """
        all_series = []
        page_num = 1

        while True:
            url = f'{BASE_URL}/series?page={page_num}&order=popular'
            loaded = False
            for attempt in range(3):
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    loaded = True
                    break
                except Exception as e:
                    if attempt < 2:
                        self.logger.info(f"   페이지 {page_num} 재시도 {attempt+1}/2: {e}")
                        await page.wait_for_timeout(5000)
                    else:
                        self.logger.warning(f"   페이지 {page_num} 로드 실패: {e} — 시리즈 목록 수집 종료")
            if not loaded:
                break
            await page.wait_for_timeout(3000)

            try:
                await page.wait_for_load_state('domcontentloaded')
            except Exception:
                pass

            items = await page.evaluate("""() => {
                const results = [];
                // 메인 그리드 카드: href가 "series/"로 시작 (/ 없이)
                // 사이드바는 "/comics/"로 시작 → 구분 가능
                const allLinks = document.querySelectorAll('a');

                for (const link of allLinks) {
                    const href = link.getAttribute('href') || '';
                    // 메인 그리드만: series/로 시작 (앞에 / 없음)
                    if (!href.match(/^series\\/[a-z]/)) continue;

                    const text = link.innerText || '';
                    const parts = text.split('\\n').map(s => s.trim()).filter(Boolean);
                    // parts 예: ["ONGOING", "MANHWA", "Title", "Chapter 39", "7.0"]

                    if (parts.length < 3) continue;

                    // 상태 (첫 번째 파트)
                    let status = 'Unknown';
                    const statusMap = {
                        'ONGOING': 'Ongoing', 'DROPPED': 'Dropped',
                        'HIATUS': 'Hiatus', 'SEASON END': 'Season End',
                        'COMPLETED': 'Completed',
                    };
                    if (statusMap[parts[0]]) {
                        status = statusMap[parts[0]];
                    }

                    // 타입 (두 번째 파트)
                    let type = 'MANHWA';
                    if (parts.length > 1) {
                        const t = parts[1].toUpperCase();
                        if (t === 'MANGA' || t === 'MANGATOON') type = 'MANGA';
                        else if (t === 'MANHUA') type = 'MANHUA';
                        else if (t === 'MANHWA') type = 'MANHWA';
                    }

                    // 제목 (상태/타입 이후, Chapter 이전)
                    let title = '';
                    let latestChapter = null;
                    let rating = null;

                    for (let i = 2; i < parts.length; i++) {
                        const p = parts[i];
                        const chMatch = p.match(/^Chapter\\s*(\\d+)/i);
                        if (chMatch) {
                            latestChapter = parseInt(chMatch[1]);
                            continue;
                        }
                        const rMatch = p.match(/^(\\d+\\.\\d+)$/);
                        if (rMatch) {
                            rating = parseFloat(rMatch[1]);
                            continue;
                        }
                        if (!title) title = p;
                    }

                    if (!title || title.length < 2) continue;

                    // DOM 제목이 잘려있을 수 있으므로 URL 슬러그에서 전체 제목 복원
                    title = title.replace(/\\.\\.\\.$/, '').trim();
                    const seriesSlugMatch = href.match(/series\\/([a-z0-9-]+?)(?:-[0-9a-f]{6,})?\\/?$/);
                    if (seriesSlugMatch && seriesSlugMatch[1]) {
                        const fromSlug = seriesSlugMatch[1]
                            .split('-')
                            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
                            .join(' ');
                        if (fromSlug.length > title.length) {
                            title = fromSlug;
                        }
                    }

                    // 썸네일
                    const img = link.querySelector('img');
                    const thumbUrl = img ?
                        (img.getAttribute('src') || '') : '';

                    const fullUrl = 'https://asurascans.com/' + href;

                    results.push({
                        title: title,
                        rating: rating,
                        status: status,
                        latest_chapter: latestChapter,
                        type: type,
                        url: fullUrl,
                        thumbnail_url: thumbUrl,
                    });
                }
                return results;
            }""")

            if not items:
                self.logger.info(
                    f"   페이지 {page_num}: 시리즈 없음, 중단"
                )
                break

            # 중복 제거 (이전 페이지와)
            existing_urls = {s['url'] for s in all_series}
            new_items = [
                item for item in items
                if item['url'] not in existing_urls
            ]

            if not new_items:
                self.logger.info(
                    f"   페이지 {page_num}: 새 시리즈 없음, 중단"
                )
                break

            all_series.extend(new_items)
            self.logger.info(
                f"   페이지 {page_num}: {len(new_items)}개 "
                f"(누적 {len(all_series)}개)"
            )

            page_num += 1
            if page_num > 30:  # 안전 제한
                break

        # 인기순 랭크 부여
        for i, series in enumerate(all_series, 1):
            series['rank'] = i

        self.results['series_list'] = all_series

    # ===== Phase 3: 작품 상세 + 댓글 =====

    async def _crawl_details(self, page: Page,
                             targets: List[Dict],
                             collect_comments: bool = True):
        """각 작품의 상세 페이지 크롤링"""
        total = len(targets)

        for idx, series in enumerate(targets, 1):
            url = series['url']
            title = series['title']

            try:
                self.logger.info(
                    f"   [{idx}/{total}] {title[:30]}..."
                )

                await page.goto(
                    url, wait_until='domcontentloaded', timeout=30000
                )
                await page.wait_for_timeout(2000)

                # 상세 정보 추출
                detail = await self._extract_detail(page, url)
                if detail:
                    detail['title'] = title
                    detail['url'] = url
                    self.results['series_details'].append(detail)

                # 댓글 수집
                if collect_comments:
                    comments = await self._extract_comments(page, title)
                    if comments:
                        self.results['comments'].extend(comments)
                        self.logger.info(
                            f"      💬 댓글 {len(comments)}개"
                        )

                # 요청 간격 (해적판 사이트이므로 넉넉히)
                await page.wait_for_timeout(2000)

            except Exception as e:
                self.logger.warning(
                    f"      ⚠️ {title[:30]} 상세 실패: {e}"
                )

    async def _extract_detail(self, page: Page,
                              url: str) -> Optional[Dict]:
        """작품 상세 페이지에서 메타데이터 추출"""
        detail = await page.evaluate("""() => {
            const result = {};
            const body = document.body.textContent || '';

            // 별점
            const ratingEls = document.querySelectorAll(
                'span, p, div'
            );
            for (const el of ratingEls) {
                const t = el.textContent.trim();
                const m = t.match(/^(\\d+\\.\\d+)$/);
                if (m && parseFloat(m[1]) <= 10) {
                    result.rating = parseFloat(m[1]);
                    break;
                }
            }

            // 팔로워 수
            const followerMatch = body.match(
                /([\\d,]+)\\s*(?:people|followers|follow)/i
            );
            if (followerMatch) {
                result.followers = parseInt(
                    followerMatch[1].replace(/,/g, '')
                );
            }

            // 상태
            for (const s of ['Ongoing', 'Dropped', 'Hiatus',
                             'Season End', 'Completed']) {
                if (body.includes(s)) {
                    result.status = s;
                    break;
                }
            }

            // 타입
            if (body.includes('Manhwa')) result.type = 'Manhwa';
            else if (body.includes('Manga')) result.type = 'Manga';
            else if (body.includes('Manhua')) result.type = 'Manhua';

            // 작가/아티스트
            const labels = document.querySelectorAll('span, h3, dt, th');
            for (const label of labels) {
                const lt = label.textContent.trim().toLowerCase();
                const next = label.nextElementSibling;
                const nextText = next ? next.textContent.trim() : '';

                if (lt === 'author' || lt === 'author(s)') {
                    result.author = nextText || '';
                }
                if (lt === 'artist' || lt === 'artist(s)') {
                    result.artist = nextText || '';
                }
                if (lt === 'serialization') {
                    result.serialization = nextText || '';
                }
            }

            // 장르 (trailing comma 제거 + 중복 제거)
            const genreLinks = document.querySelectorAll(
                'a[href*="genres"]'
            );
            const genres = Array.from(genreLinks)
                .map(a => a.textContent.trim().replace(/,$/,'').trim())
                .filter(g => g.length > 0 && g.length < 30);
            result.genres = [...new Set(genres)].join(', ');

            // 설명
            const descEls = document.querySelectorAll(
                'p, span.font-medium'
            );
            for (const el of descEls) {
                const text = el.textContent.trim();
                if (text.length > 100 && text.length < 5000) {
                    result.description = text;
                    break;
                }
            }

            // 챕터 수 (href의 /chapter/N 에서 추출 — 텍스트는 연결됨)
            const chapterLinks = document.querySelectorAll(
                'a[href*="/chapter/"]'
            );
            let maxChapter = 0;
            for (const cl of chapterLinks) {
                const href = cl.getAttribute('href') || '';
                const m = href.match(/\/chapter\/(\d+)/);
                if (m) {
                    const num = parseInt(m[1]);
                    if (num > maxChapter) maxChapter = num;
                }
            }
            if (maxChapter > 0) result.total_chapters = maxChapter;

            // 댓글 수 (span 내부 "449 Comments" 패턴)
            const allSpans = document.querySelectorAll(
                'span.text-base, span.font-medium'
            );
            for (const sp of allSpans) {
                const t = sp.textContent.trim();
                const cm = t.match(/^(\d+)\s*Comment/i);
                if (cm) {
                    result.comment_count = parseInt(cm[1]);
                    break;
                }
            }

            return result;
        }""")

        return detail if detail else None

    async def _extract_comments(self, page: Page,
                                title: str) -> List[Dict]:
        """작품 상세 페이지에서 댓글 추출

        DOM 구조 (각 댓글):
        div.flex
          div.flex-shrink-0.mr-3 → 아바타
          div.flex-1.min-w-0
            div.flex.items-center.gap-2.mb-1
              div.font-semibold → 유저명
              span.text-xs.text-zinc-400 → "10 months ago"
            div.text-sm.leading-relaxed.mb-3 → 본문
            ... → 좋아요, Reply 버튼
        """
        # 스크롤 다운하여 댓글 로드
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

        # "Load More Comments" 클릭 (최대 5회 → 약 150~200개)
        for _ in range(5):
            load_more = await page.query_selector(
                'button:has-text("Load More Comments")'
            )
            if not load_more:
                break
            try:
                await load_more.click()
                await page.wait_for_timeout(1500)
            except Exception:
                break

        comments = await page.evaluate("""(title) => {
            const results = [];
            const seen = new Set();

            // 댓글 블록: div.flex > div.flex-shrink-0 + div.flex-1 구조
            const allDivs = document.querySelectorAll(
                'div.flex-1.min-w-0'
            );

            for (const contentDiv of allDivs) {
                // 유저명: div.font-semibold
                const nameEl = contentDiv.querySelector(
                    'div.font-semibold, span.font-semibold'
                );
                const name = nameEl ? nameEl.textContent.trim() : '';
                if (!name || name.length > 50 || name.length < 2) continue;

                // 시간: span.text-xs 또는 "ago" 패턴
                const timeEl = contentDiv.querySelector(
                    'span.text-xs'
                );
                let timeText = '';
                if (timeEl) {
                    const tt = timeEl.textContent.trim();
                    if (tt.match(/ago$/i)) timeText = tt;
                }

                // 본문: div.text-sm.leading-relaxed 또는 div.mb-3
                const bodyEl = contentDiv.querySelector(
                    'div.text-sm.leading-relaxed, div.mb-3'
                );
                let body = '';
                if (bodyEl) {
                    body = bodyEl.textContent.trim();
                }
                if (!body || body.length < 3) continue;

                // 중복 방지
                const key = name + '|' + body.substring(0, 50);
                if (seen.has(key)) continue;
                seen.add(key);

                // 좋아요 수: 버튼 내부 숫자 (첫 번째 = upvote)
                const buttons = contentDiv.querySelectorAll('button');
                let likes = 0;
                for (const btn of buttons) {
                    const btnText = btn.textContent.trim();
                    if (btnText.match(/^\\d+$/) && parseInt(btnText) < 100000) {
                        likes = parseInt(btnText);
                        break;  // 첫 번째 숫자 버튼 = upvote
                    }
                }

                results.push({
                    reviewer_name: name,
                    body: body.substring(0, 2000),
                    reviewed_at_text: timeText,
                    likes_count: likes,
                    work_title: title,
                });
            }

            return results;
        }""", title)

        return comments or []

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[str]:
        """'3 months ago' → approximate ISO date string"""
        if not text:
            return None
        text = text.strip().lower()
        now = datetime.now()
        try:
            if 'just now' in text or 'second' in text:
                return now.strftime('%Y-%m-%d')
            parts = text.split()
            if len(parts) < 2:
                return None
            num = int(parts[0]) if parts[0].isdigit() else 1
            unit = parts[1]
            if 'minute' in unit:
                return now.strftime('%Y-%m-%d')
            elif 'hour' in unit:
                return now.strftime('%Y-%m-%d')
            elif 'day' in unit:
                from datetime import timedelta
                return (now - timedelta(days=num)).strftime('%Y-%m-%d')
            elif 'week' in unit:
                from datetime import timedelta
                return (now - timedelta(weeks=num)).strftime('%Y-%m-%d')
            elif 'month' in unit:
                from datetime import timedelta
                return (now - timedelta(days=num * 30)).strftime('%Y-%m-%d')
            elif 'year' in unit:
                from datetime import timedelta
                return (now - timedelta(days=num * 365)).strftime('%Y-%m-%d')
        except (ValueError, IndexError):
            pass
        return None

    # ===== 데이터 저장 =====

    async def save_all(self, date: str):
        """수집한 모든 데이터를 DB에 저장"""
        from crawler.db import (
            save_rankings, save_works_metadata, save_work_detail,
            save_reviews, backup_to_json
        )

        # 1. 랭킹 저장 (Weekly를 메인으로)
        weekly = self.results['rankings_weekly']
        if weekly:
            save_rankings(date, self.platform_id, [
                {
                    'rank': item['rank'],
                    'title': item['title'],
                    'genre': item.get('genres', ''),
                    'url': item.get('url', ''),
                }
                for item in weekly
            ], sub_category='weekly')
            self.logger.info(f"   💾 Weekly 랭킹: {len(weekly)}개")

        monthly = self.results['rankings_monthly']
        if monthly:
            save_rankings(date, self.platform_id, [
                {
                    'rank': item['rank'],
                    'title': item['title'],
                    'genre': item.get('genres', ''),
                    'url': item.get('url', ''),
                }
                for item in monthly
            ], sub_category='monthly')
            self.logger.info(f"   💾 Monthly 랭킹: {len(monthly)}개")

        all_time = self.results['rankings_all']
        if all_time:
            save_rankings(date, self.platform_id, [
                {
                    'rank': item['rank'],
                    'title': item['title'],
                    'genre': item.get('genres', ''),
                    'url': item.get('url', ''),
                }
                for item in all_time
            ], sub_category='all')
            self.logger.info(f"   💾 All-time 랭킹: {len(all_time)}개")

        # 2. 시리즈 목록 → works 메타데이터만 저장 (종합 랭킹은 존재하지 않으므로 저장 안 함)
        series = self.results['series_list']
        if series:
            # works 메타데이터 저장 (전체, rating/review_count 포함)
            works_meta = [
                {
                    'title': item['title'],
                    'thumbnail_url': item.get('thumbnail_url', ''),
                    'url': item.get('url', ''),
                    'genre': '',
                    'rank': item.get('rank'),
                    'rating': item.get('rating'),
                    'review_count': item.get('comment_count'),
                }
                for item in series
                if item.get('thumbnail_url')
            ]
            if works_meta:
                save_works_metadata(
                    self.platform_id, works_meta, date=date, sub_category=''
                )
            self.logger.info(
                f"   💾 시리즈 목록: {min(len(series), 100)}개 랭킹 + "
                f"{len(works_meta)}개 메타데이터"
            )

            backup_to_json(date, self.platform_id, [
                {
                    'rank': item['rank'],
                    'title': item['title'],
                    'rating': item.get('rating'),
                    'status': item.get('status'),
                    'latest_chapter': item.get('latest_chapter'),
                    'type': item.get('type'),
                    'url': item.get('url', ''),
                    'thumbnail_url': item.get('thumbnail_url', ''),
                }
                for item in series
            ])

        # 3. 상세 정보 저장
        details = self.results['series_details']
        detail_count = 0
        for detail in details:
            try:
                saved = save_work_detail(self.platform_id, detail['title'], {
                    'author': detail.get('author', ''),
                    'publisher': '',
                    'label': '',
                    'tags': detail.get('genres', ''),
                    'description': detail.get('description', ''),
                    'hearts': detail.get('followers'),
                    'favorites': detail.get('followers'),
                    'rating': detail.get('rating'),
                    'review_count': detail.get('comment_count'),
                })
                if saved:
                    detail_count += 1
            except Exception as e:
                self.logger.warning(
                    f"      상세 저장 실패 {detail.get('title', '')[:20]}: {e}"
                )
        if detail_count:
            self.logger.info(f"   💾 상세 정보: {detail_count}개")

        # 4. 댓글 저장
        comments = self.results['comments']
        if comments:
            # 작품별로 그룹핑하여 저장
            from collections import defaultdict
            by_title = defaultdict(list)
            for c in comments:
                # "X months ago" → approximate date
                reviewed_at = self._parse_relative_time(
                    c.get('reviewed_at_text', '')
                )
                by_title[c['work_title']].append({
                    'reviewer_name': c.get('reviewer_name', ''),
                    'reviewer_info': '',
                    'body': c.get('body', ''),
                    'rating': None,
                    'likes_count': c.get('likes_count', 0),
                    'is_spoiler': False,
                    'reviewed_at': reviewed_at,
                })

            total_saved = 0
            for work_title, reviews in by_title.items():
                saved = save_reviews(self.platform_id, work_title, reviews)
                total_saved += saved

            self.logger.info(f"   💾 댓글: {total_saved}개")
