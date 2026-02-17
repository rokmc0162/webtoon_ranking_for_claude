"""
리뷰/코멘트 수집 크롤러 v2 (플랫폼 동시 실행)

변경사항 (v2):
- 3개 플랫폼 동시 실행 (asyncio.gather)
- 라인망가: 상품 페이지 → 네트워크 인터셉트로 실제 book_id 탐지 → API 전체 수집
- 메챠코믹/코믹시모아: 페이지 제한 제거 (전체 리뷰 수집)
- 수집 후 코멘트 수 매칭 검증 로깅
- 픽코마: 제외 (하트수는 detail_scraper에서 수집)
"""

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Tuple
from playwright.async_api import Browser, Page

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.db import get_works_for_review, save_reviews

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('crawler.review_crawler')


class ReviewCrawler:
    """리뷰/코멘트 수집 크롤러 (플랫폼 동시 실행)"""

    def __init__(self, max_works: int = 0, delay_seconds: float = 3.0, concurrency: int = 1):
        """
        Args:
            max_works: 최대 작품 수 (0 = 무제한)
            delay_seconds: 작품 간 딜레이 (초)
            concurrency: 플랫폼별 동시 페이지 수 (기본 1 = 순차)
        """
        self.max_works = max_works
        self.delay_seconds = delay_seconds
        self.concurrency = concurrency

    async def run(self, browser: Browser):
        """메인: 3개 플랫폼 병렬 실행"""
        limit = self.max_works if self.max_works > 0 else 10000
        works = get_works_for_review(limit)
        if not works:
            logger.info("리뷰 수집 대상 없음")
            return

        # 플랫폼별 그룹핑
        by_platform = defaultdict(list)
        for w in works:
            by_platform[w['platform']].append(w)

        logger.info(f"리뷰 수집 시작: {len(works)}개 작품 ({len(by_platform)}개 플랫폼 동시 실행)")
        for p, pw in sorted(by_platform.items()):
            logger.info(f"  {p}: {len(pw)}개")

        # 플랫폼별 병렬 실행
        tasks = [
            self._run_platform(browser, platform, pworks)
            for platform, pworks in by_platform.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 집계
        total_reviews = 0
        total_failed = 0
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"플랫폼 오류: {r}")
                continue
            total_reviews += r[0]
            total_failed += r[1]

        logger.info(f"리뷰 수집 완료: {total_reviews}개 리뷰 저장, {total_failed}개 실패")

    async def _run_platform(
        self, browser: Browser, platform: str, works: List[Dict]
    ) -> Tuple[int, int]:
        """플랫폼별 워커 — 자체 브라우저 컨텍스트에서 실행"""
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            ignore_https_errors=(platform == 'cmoa')
        )

        sem = asyncio.Semaphore(self.concurrency)
        review_counts = []
        fail_count = 0

        async def process(i: int, work: Dict):
            nonlocal fail_count
            async with sem:
                page = await ctx.new_page()
                try:
                    reviews = await self._collect_reviews(page, platform, work['url'])
                    if reviews:
                        count = save_reviews(platform, work['title'], reviews)
                        review_counts.append(count)
                        if i <= 5 or i % 50 == 0 or i == len(works):
                            logger.info(
                                f"  [{i}/{len(works)}] {platform}: "
                                f"{work['title'][:25]}... {count}개 리뷰"
                            )
                    else:
                        review_counts.append(0)
                except Exception as e:
                    fail_count += 1
                    if i <= 10 or i % 50 == 0:
                        logger.warning(
                            f"  [{i}/{len(works)}] {platform}: "
                            f"{work['title'][:25]}... 실패: {e}"
                        )
                finally:
                    await page.close()
                    await asyncio.sleep(self.delay_seconds)

        tasks = [process(i, w) for i, w in enumerate(works, 1)]
        await asyncio.gather(*tasks, return_exceptions=True)
        await ctx.close()

        total = sum(review_counts)
        logger.info(f"  [{platform}] 완료: {total}개 리뷰, {fail_count}개 실패")
        return total, fail_count

    async def _collect_reviews(
        self, page: Page, platform: str, url: str
    ) -> List[Dict[str, Any]]:
        """플랫폼별 리뷰 수집 디스패치"""
        if platform == 'linemanga':
            return await self._collect_linemanga(page, url)
        elif platform == 'mechacomic':
            return await self._collect_mechacomic(page, url)
        elif platform == 'cmoa':
            return await self._collect_cmoa(page, url)
        return []

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 라인망가 — 상품 페이지 → book_id 탐지 → API 전체 수집
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def _collect_linemanga(self, page: Page, url: str) -> List[Dict[str, Any]]:
        """
        라인망가 코멘트 수집 (정확한 book_id 탐지 방식)

        문제: URL의 product_id (/product/periodic?id=XXX) ≠ 코멘트 API의 book_id
              예: product_id=Z0001684 이지만 코멘트 API에는 book_id=Z0090127 필요

        해결: 상품 페이지의 코멘트 위젯 요소에서 data-conf 속성 파싱하여
              실제 book_id 추출 (예: .fnComment[data-conf] → bookId)
        """

        # ── 1단계: 상품 페이지 이동 ──
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)
        except Exception:
            return []

        # ── 2단계: 코멘트 위젯의 data-conf에서 book_id 추출 ──
        # 라인망가 상품 페이지에는 코멘트 위젯 요소가 있고,
        # data-conf 속성에 JSON으로 bookId와 commentCount가 들어있음
        comment_info = await page.evaluate(r'''
            () => {
                // 방법 1: 코멘트 위젯의 data-conf 속성 (가장 정확)
                const commentWidget = document.querySelector(
                    '.fnComment[data-conf], [class*="Comment"][data-conf]'
                );
                if (commentWidget) {
                    try {
                        const conf = JSON.parse(
                            commentWidget.getAttribute('data-conf')
                                .replace(/&quot;/g, '"')
                                .replace(/&amp;/g, '&')
                        );
                        if (conf.bookId || conf.book_id) {
                            return {
                                bookId: conf.bookId || conf.book_id,
                                commentCount: conf.commentCount || 0
                            };
                        }
                    } catch(e) {}
                }

                // 방법 2: data-conf를 정규식으로 추출
                const allWithConf = document.querySelectorAll('[data-conf]');
                for (const el of allWithConf) {
                    const conf = el.getAttribute('data-conf') || '';
                    const idMatch = conf.match(/book[_\-]?[Ii]d[^A-Za-z0-9]*([A-Za-z][A-Za-z0-9]+)/);
                    if (idMatch) {
                        const countMatch = conf.match(/commentCount[^0-9]*(\d+)/);
                        return {
                            bookId: idMatch[1],
                            commentCount: countMatch ? parseInt(countMatch[1]) : 0
                        };
                    }
                }

                // 방법 3: HTML에서 book_id 속성 직접 탐색
                const bookIdEls = document.querySelectorAll('[book_id], [data-book-id]');
                for (const el of bookIdEls) {
                    const id = el.getAttribute('book_id') || el.dataset.bookId;
                    if (id) return { bookId: id, commentCount: 0 };
                }

                // 방법 4: 페이지 전체 HTML에서 첫 번째 book_id 추출
                const html = document.documentElement.outerHTML;
                const m = html.match(/book_id="([A-Za-z][A-Za-z0-9]+)"/);
                if (m) return { bookId: m[1], commentCount: 0 };

                return null;
            }
        ''')

        discovered_book_id = comment_info.get('bookId') if comment_info else None
        page_comment_count = comment_info.get('commentCount', 0) if comment_info else 0

        if not discovered_book_id:
            # 최종 fallback: URL에서 추출 (정확하지 않을 수 있음)
            m = re.search(r'[?&]id=([A-Za-z0-9]+)', url)
            if not m:
                return []
            discovered_book_id = m.group(1)
            logger.warning(f"  ⚠️ 라인망가 book_id fallback (URL): {discovered_book_id} — 정확하지 않을 수 있음")

        # ── 검증용: 페이지 표시 코멘트 수 (data-conf 보완) ──
        visible_count = await page.evaluate(r'''
            () => {
                const text = document.body.innerText || '';
                const m = text.match(/コメント\s*([0-9,]+)\s*件/);
                return m ? parseInt(m[1].replace(/,/g, '')) : 0;
            }
        ''') or 0
        if visible_count > 0:
            page_comment_count = visible_count

        # ── 5단계: API로 전체 코멘트 수집 (페이지 제한 없음) ──
        all_reviews = []
        seen_keys = set()  # best_comments ↔ comments 중복 방지
        page_num = 1

        while True:
            api_url = (
                f'https://manga.line.me/api/book_comment/list'
                f'?book_id={discovered_book_id}&page={page_num}&rows=20'
            )

            try:
                result = await page.evaluate(
                    'async (url) => {'
                    '  try { const r = await fetch(url);'
                    '    if (!r.ok) return null;'
                    '    return await r.json();'
                    '  } catch { return null; }'
                    '}',
                    api_url
                )

                if not result or 'result' not in result:
                    break

                comments = result['result'].get('comments', [])

                # 첫 페이지: best_comments도 함께 수집
                if page_num == 1:
                    best = result['result'].get('best_comments', [])
                    comments = best + comments

                if not comments:
                    break

                for c in comments:
                    # 중복 방지 (nickname + timestamp)
                    key = f"{c.get('nickname', '')}-{c.get('commented_on', '')}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    reviewed_at = None
                    if c.get('commented_on'):
                        try:
                            reviewed_at = datetime.fromtimestamp(c['commented_on']).isoformat()
                        except (ValueError, OSError):
                            pass

                    all_reviews.append({
                        'reviewer_name': c.get('nickname', ''),
                        'reviewer_info': '',
                        'body': c.get('body', ''),
                        'rating': None,
                        'likes_count': c.get('iine_count', 0),
                        'is_spoiler': False,
                        'reviewed_at': reviewed_at,
                    })

                # 다음 페이지 확인
                pager = result['result'].get('pager', {})
                if not pager.get('hasNext'):
                    break

                page_num += 1
                await asyncio.sleep(0.3)

            except Exception:
                break

        # ── 6단계: 수집 검증 ──
        if page_comment_count > 0 and len(all_reviews) > 0:
            ratio = len(all_reviews) / page_comment_count
            if ratio < 0.5:
                logger.warning(
                    f"  ⚠️ 라인망가 코멘트 불일치: "
                    f"페이지 {page_comment_count}건 vs 수집 {len(all_reviews)}건 "
                    f"(book_id={discovered_book_id})"
                )

        return all_reviews

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 메챠코믹 — SSR 리뷰 페이지 전체 수집
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def _collect_mechacomic(self, page: Page, url: str) -> List[Dict[str, Any]]:
        """메챠코믹 리뷰 전체 수집 (페이지 제한 없음)"""
        match = re.search(r'/books/(\d+)', url)
        if not match:
            return []

        book_id = match.group(1)
        all_reviews = []
        page_num = 1

        while True:
            review_url = f'https://mechacomic.jp/r/books/{book_id}/reviews?sort=newest&page={page_num}'

            try:
                await page.goto(review_url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(1000)

                reviews = await page.evaluate(r'''
                    () => {
                        const results = [];
                        const items = document.querySelectorAll('.p-commentList_item, .p-comment');

                        for (const el of items) {
                            const bodyEl = el.querySelector('.p-comment_content');
                            const body = bodyEl?.textContent?.trim();
                            if (!body || body.length < 5) continue;

                            // 별점
                            let rating = null;
                            const scoreEl = el.querySelector('.p-comment_score-average');
                            if (scoreEl) {
                                const m = scoreEl.textContent.match(/([0-9.]+)/);
                                if (m) rating = Math.round(parseFloat(m[1]));
                            }
                            if (!rating) {
                                const starImg = el.querySelector('.p-comment_score-star');
                                if (starImg) {
                                    const m = (starImg.alt || starImg.src).match(/([0-9.]+)/);
                                    if (m) rating = Math.round(parseFloat(m[1]));
                                }
                            }

                            const nameEl = el.querySelector('.p-comment_customerName');
                            const reviewer_name = nameEl?.textContent?.trim() || '';

                            let reviewed_at = null;
                            const dateEl = el.querySelector('.p-comment_updateDay');
                            if (dateEl) {
                                const dm = dateEl.textContent.match(/(\d{4})\/(\d{1,2})\/(\d{1,2})/);
                                if (dm) reviewed_at = `${dm[1]}-${dm[2].padStart(2,'0')}-${dm[3].padStart(2,'0')}T00:00:00`;
                            }

                            let likes = 0;
                            const goodEl = el.querySelector('.p-commentSubMenu_good-link');
                            if (goodEl) {
                                const hm = goodEl.textContent.match(/(\d+)/);
                                if (hm) likes = parseInt(hm[1]);
                            }

                            const isSpoiler = el.textContent.includes('ネタバレ');

                            results.push({
                                reviewer_name, body, rating, likes_count: likes,
                                is_spoiler: isSpoiler, reviewed_at,
                                reviewer_info: ''
                            });
                        }
                        return results;
                    }
                ''')

                if not reviews:
                    break

                all_reviews.extend(reviews)

                # 다음 페이지 존재 확인
                has_next = await page.evaluate(r'''
                    () => {
                        const nextLink = document.querySelector(
                            'a[rel="next"], .pagination .next a, .p-pager_next a'
                        );
                        return !!nextLink;
                    }
                ''')

                if not has_next:
                    break

                page_num += 1
                await asyncio.sleep(0.5)

            except Exception:
                break

        return all_reviews

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 코믹시모아 — Playwright 리뷰 페이지 전체 수집
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    async def _collect_cmoa(self, page: Page, url: str) -> List[Dict[str, Any]]:
        """코믹시모아 리뷰 전체 수집 (페이지 제한 없음)"""
        match = re.search(r'/title/(\d+)', url)
        if not match:
            return []

        title_id = match.group(1)
        all_reviews = []
        page_num = 1

        while True:
            review_url = (
                f'https://www.cmoa.jp/title/customer_review/title_id/{title_id}/'
                f'?site_kbn=1&sort=2&page={page_num}'
            )

            try:
                await page.goto(review_url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(1000)

                reviews = await page.evaluate(r'''
                    (currentPage) => {
                        const results = [];
                        const reviewBlocks = document.querySelectorAll('.review_detail');

                        for (const block of reviewBlocks) {
                            // 본문: 일반 리뷰는 .body_text, 스포일러는 .netabare_hide_txt
                            const bodyEl = block.querySelector('.body_text');
                            const netaEl = block.querySelector('.netabare_hide_txt');
                            const body = (bodyEl || netaEl)?.textContent?.trim();
                            if (!body || body.length < 3) continue;

                            // 작성자
                            const nameEl = block.querySelector('.reviewer_name');
                            const reviewer_name = nameEl?.textContent?.trim() || '';

                            // 작성자 정보 (성별/연대) — 첫번째 .reviewer_age 중 괄호 패턴
                            let reviewer_info = '';
                            const ageEls = block.querySelectorAll('.reviewer_age');
                            for (const ageEl of ageEls) {
                                const m = ageEl.textContent.match(/\(([^)]+)\)/);
                                if (m) { reviewer_info = m[1]; break; }
                            }

                            // 별점: .review_star 내 img[src*="whole_star"] 개수
                            let rating = null;
                            const starEl = block.querySelector('.review_star');
                            if (starEl) {
                                const wholeStars = starEl.querySelectorAll('img[src*="whole_star"]').length;
                                const halfStars = starEl.querySelectorAll('img[src*="half_star"]').length;
                                if (wholeStars > 0 || halfStars > 0) {
                                    rating = wholeStars + (halfStars > 0 ? 1 : 0);
                                }
                            }

                            // 날짜: .t_r_review_date
                            let reviewed_at = null;
                            const dateEl = block.querySelector('.t_r_review_date');
                            if (dateEl) {
                                const dm = dateEl.textContent.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
                                if (dm) {
                                    reviewed_at = `${dm[1]}-${dm[2].padStart(2,'0')}-${dm[3].padStart(2,'0')}T00:00:00`;
                                }
                            }

                            // 좋아요: .good_mark 내 숫자
                            let likes = 0;
                            const goodEl = block.querySelector('.good_mark');
                            if (goodEl) {
                                const hm = goodEl.textContent.match(/(\d+)件/);
                                if (hm) likes = parseInt(hm[1]);
                            }

                            // 스포일러: .netabare_txt 존재 여부
                            const isSpoiler = !!block.querySelector('.netabare_txt');

                            results.push({
                                reviewer_name, reviewer_info, body, rating,
                                likes_count: likes, is_spoiler: isSpoiler,
                                reviewed_at
                            });
                        }

                        // 다음 페이지 존재 여부: page=N+1 링크가 있는지 확인
                        const nextPage = currentPage + 1;
                        const nextLink = document.querySelector(
                            `a[href*="page=${nextPage}"]`
                        );

                        return { reviews: results, hasNext: !!nextLink };
                    }
                ''', page_num)

                page_reviews = reviews.get('reviews', []) if isinstance(reviews, dict) else reviews
                has_next = reviews.get('hasNext', False) if isinstance(reviews, dict) else False

                if not page_reviews:
                    break

                all_reviews.extend(page_reviews)

                if not has_next:
                    break

                page_num += 1
                await asyncio.sleep(0.5)

            except Exception:
                break

        return all_reviews


async def run_review_crawler(max_works: int = 0, concurrency: int = 1):
    """독립 실행용 래퍼"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            crawler = ReviewCrawler(
                max_works=max_works,
                delay_seconds=3.0,
                concurrency=concurrency
            )
            await crawler.run(browser)
        finally:
            await browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("리뷰/코멘트 수집 크롤러 v2 (플랫폼 동시 실행)")
    print("=" * 60)
    asyncio.run(run_review_crawler(max_works=10))
