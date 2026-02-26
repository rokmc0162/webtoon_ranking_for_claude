"""
작품 상세 페이지 메타데이터 스크래퍼
- 매일 랭킹 크롤링 후 실행
- 1회 최대 50개, 요청 간 3초 딜레이 (NAS 부하 방지)
- 작가/출판사/레이블/태그/하트수/별점 등 수집
"""

import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional
from playwright.async_api import Browser, Page

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.db import get_works_needing_detail, save_work_detail

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('crawler.detail_scraper')


class DetailScraper:
    """작품 상세 페이지에서 메타데이터를 수집하는 스크래퍼"""

    def __init__(self, max_works: int = 50, delay_seconds: float = 3.0):
        self.max_works = max_works
        self.delay_seconds = delay_seconds

    async def run(self, browser: Browser, riverse_only: bool = False):
        """메인 실행: 메타데이터가 필요한 작품들을 순차 처리"""
        works = get_works_needing_detail(self.max_works, riverse_only=riverse_only)
        if not works:
            logger.info("상세 스크래핑 대상 없음")
            return

        logger.info(f"상세 스크래핑 시작: {len(works)}개 작품")

        # 플랫폼별 컨텍스트 (CMOA는 TLS 우회 필요)
        context_default = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        context_cmoa = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            ignore_https_errors=True
        )

        page_default = await context_default.new_page()
        page_cmoa = await context_cmoa.new_page()

        success = 0
        failed = 0

        for i, work in enumerate(works, 1):
            platform = work['platform']
            title = work['title']
            url = work['url']

            try:
                page = page_cmoa if platform == 'cmoa' else page_default

                detail = await self._scrape_detail(page, platform, url)
                if detail:
                    save_work_detail(platform, title, detail)
                    success += 1
                    if i <= 5 or i % 10 == 0:
                        logger.info(f"  [{i}/{len(works)}] {platform}: {title[:30]}... OK")
                else:
                    failed += 1
                    logger.warning(f"  [{i}/{len(works)}] {platform}: {title[:30]}... 데이터 없음")
            except Exception as e:
                failed += 1
                logger.warning(f"  [{i}/{len(works)}] {platform}: {title[:30]}... 실패: {e}")

            if i < len(works):
                await asyncio.sleep(self.delay_seconds)

        await page_default.close()
        await page_cmoa.close()
        await context_default.close()
        await context_cmoa.close()

        logger.info(f"상세 스크래핑 완료: 성공 {success}, 실패 {failed}")

    async def _scrape_detail(self, page: Page, platform: str, url: str) -> Optional[Dict[str, Any]]:
        """플랫폼별 상세 스크래핑 디스패치"""
        if platform == 'piccoma':
            return await self._scrape_piccoma(page, url)
        elif platform == 'linemanga':
            return await self._scrape_linemanga(page, url)
        elif platform == 'mechacomic':
            return await self._scrape_mechacomic(page, url)
        elif platform == 'cmoa':
            return await self._scrape_cmoa(page, url)
        return None

    # ─── 픽코마 (SSR) ───
    async def _scrape_piccoma(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)

        detail = await page.evaluate('''
            () => {
                const result = {};

                // JSON-LD에서 Product 데이터 추출
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        if (data["@type"] === "Product") {
                            result.description = data.description || '';
                            if (data.offers && data.offers.category) {
                                result.genre = data.offers.category;
                            }
                        }
                    } catch(e) {}
                }

                // 작가 (author) — 중복 제거
                const authorLinks = document.querySelectorAll('a[href*="/author/product/list/"]');
                if (authorLinks.length > 0) {
                    result.author = [...new Set(Array.from(authorLinks).map(a => a.textContent.trim()))].join(', ');
                }

                // 출판사 (publisher/partner) — 중복 제거
                const partnerLinks = document.querySelectorAll('a[href*="/partner/product/list/"]');
                if (partnerLinks.length > 0) {
                    result.publisher = [...new Set(Array.from(partnerLinks).map(a => a.textContent.trim()))].join(', ');
                }

                // 레이블 (category/label) — 중복 제거
                const categoryLinks = document.querySelectorAll('a[href*="/category/product/list/"]');
                if (categoryLinks.length > 0) {
                    result.label = [...new Set(Array.from(categoryLinks).map(a => a.textContent.trim()))].join(', ');
                }

                // 하트수 (いいね)
                const likeImg = document.querySelector('img[alt="いいね"]');
                if (likeImg) {
                    const parent = likeImg.closest('.PCM-productHome_like, [class*="like"]') || likeImg.parentElement;
                    if (parent) {
                        const text = parent.textContent.replace(/[^0-9,]/g, '').replace(/,/g, '');
                        if (text) result.hearts = parseInt(text, 10);
                    }
                }

                return result;
            }
        ''')

        return detail if detail and (detail.get('author') or detail.get('publisher')) else detail

    # ─── 라인망가 (CSR - Playwright 필수) ───
    async def _scrape_linemanga(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(2000)  # JS 렌더링 대기

        detail = await page.evaluate('''
            () => {
                const result = {};

                // ─── 줄거리 (description) ───
                // 1) CSS 셀렉터로 시도
                const summaryEl = document.querySelector('.MdMNG03Summary .mdMNG03Txt, .MdMNG03Summary p');
                if (summaryEl && summaryEl.textContent.trim().length > 10) {
                    result.description = summaryEl.textContent.trim();
                }
                // 2) fallback: meta description
                if (!result.description) {
                    const metaDesc = document.querySelector('meta[name="description"]');
                    if (metaDesc) {
                        const content = metaDesc.getAttribute('content') || '';
                        // "【N話無料】" 접두사 제거
                        const cleaned = content.replace(/^【[^】]*】/, '').trim();
                        if (cleaned.length > 10) result.description = cleaned;
                    }
                }

                // ─── 작가 정보 (역할별 분리) ───
                // 구조화된 DOM에서 추출 시도: dt.mdMNG04Dt02 + dd.mdMNG04Dd02
                const authorDd = document.querySelector('.mdMNG04Dd02, dd.mdMNG04Dd02');
                if (authorDd) {
                    // 링크된 작가명 추출 (역할 정보 포함)
                    const authorLinks = authorDd.querySelectorAll('a[href*="author_id"]');
                    if (authorLinks.length > 0) {
                        // 전체 텍스트에서 역할 파싱: "WAN.Z(redice studio)(脚色)・Maslow(原作)・swingbat(作画)"
                        const fullText = authorDd.textContent.trim();
                        result.author = fullText;
                    }
                }

                // fallback: body 텍스트에서 추출
                if (!result.author) {
                    const body = document.body.innerText;
                    const authorMatch = body.match(/作者[\\s\\n]*([^\\n]+)/);
                    if (authorMatch) result.author = authorMatch[1].trim();
                }

                // ─── 출판사 ───
                const pubDd = document.querySelector('.mdMNG04Dd03, dd.mdMNG04Dd03');
                if (pubDd && pubDd.textContent.trim()) {
                    result.publisher = pubDd.textContent.trim();
                }
                if (!result.publisher) {
                    const body = document.body.innerText;
                    const pubMatch = body.match(/出版社[\\s\\n]*([^\\n]+)/);
                    if (pubMatch) result.publisher = pubMatch[1].trim();
                }

                // ─── 掲載誌 (레이블/잡지) ───
                const magDd = document.querySelector('.mdMNG04Dd04, dd.mdMNG04Dd04');
                if (magDd && magDd.textContent.trim()) {
                    result.label = magDd.textContent.trim();
                }
                if (!result.label) {
                    const body = document.body.innerText;
                    const magMatch = body.match(/掲載誌[\\s\\n]*([^\\n]+)/);
                    if (magMatch) result.label = magMatch[1].trim();
                }

                // ─── ジャンル (장르) ───
                const genreDd = document.querySelector('.mdMNG04Dd01, dd.mdMNG04Dd01');
                if (genreDd && genreDd.textContent.trim()) {
                    result.genre = genreDd.textContent.trim();
                }

                // ─── お気に入り (즐겨찾기 수) ───
                const favElements = document.querySelectorAll('[class*="Fav"], [class*="fav"]');
                for (const el of favElements) {
                    const numMatch = el.textContent.replace(/,/g, '').match(/([0-9]+)/);
                    if (numMatch && parseInt(numMatch[1]) > 100) {
                        result.favorites = parseInt(numMatch[1]);
                        break;
                    }
                }

                // 즐겨찾기가 아직 없으면 본문에서 숫자 큰 것 찾기
                if (!result.favorites) {
                    const body = document.body.innerText;
                    const numPattern = body.match(/([0-9,]{4,})[\\s]*人?/);
                    if (numPattern) {
                        const num = parseInt(numPattern[1].replace(/,/g, ''));
                        if (num > 1000) result.favorites = num;
                    }
                }

                return result;
            }
        ''')

        return detail

    # ─── 메챠코믹 (SSR) ───
    async def _scrape_mechacomic(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(1000)

        detail = await page.evaluate('''
            () => {
                const result = {};

                // 작가
                const authorLinks = document.querySelectorAll('a[href*="/authors/"]');
                if (authorLinks.length > 0) {
                    result.author = Array.from(authorLinks).map(a => a.textContent.trim()).join(', ');
                }

                // 레이블
                const labelLinks = document.querySelectorAll('a[href*="/labels/"]');
                if (labelLinks.length > 0) {
                    result.label = Array.from(labelLinks).map(a => a.textContent.trim()).join(', ');
                }

                // 평점 (img alt에서 추출)
                const ratingImgs = document.querySelectorAll('img[alt*="評価"]');
                for (const img of ratingImgs) {
                    const match = img.alt.match(/([0-9.]+)/);
                    if (match) {
                        result.rating = parseFloat(match[1]);
                        break;
                    }
                }

                // 리뷰 수
                const body = document.body.innerText;
                const reviewMatch = body.match(/全([0-9]+)件/);
                if (reviewMatch) {
                    result.review_count = parseInt(reviewMatch[1]);
                }

                // JSON-LD BreadcrumbList에서 장르 추출
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);
                        if (data["@type"] === "BreadcrumbList" && data.itemListElement) {
                            for (const item of data.itemListElement) {
                                if (item.position === 2) result.genre = item.name;
                            }
                        }
                    } catch(e) {}
                }

                return result;
            }
        ''')

        return detail

    # ─── 코믹시모아 (Playwright, TLS 우회) ───
    async def _scrape_cmoa(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(1000)

        detail = await page.evaluate('''
            () => {
                const result = {};

                // JSON-LD 파싱
                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (const s of scripts) {
                    try {
                        const data = JSON.parse(s.textContent);

                        // Product (브랜드=출판사, 카테고리=장르, 평점)
                        if (data["@type"] === "product" || data["@type"] === "Product") {
                            if (data.brand) result.publisher = typeof data.brand === 'string' ? data.brand : data.brand.name || '';
                            if (data.category) result.genre = data.category;
                            if (data.aggregateRating) {
                                result.rating = parseFloat(data.aggregateRating.ratingValue) || null;
                                result.review_count = parseInt(data.aggregateRating.reviewCount) || null;
                            }
                        }

                        // Book (작가)
                        if (data["@type"] === "Book" && data.author) {
                            const authors = Array.isArray(data.author) ? data.author : [data.author];
                            result.author = authors.map(a => a.name || a).filter(Boolean).join(', ');
                        }
                    } catch(e) {}
                }

                // 레이블/잡지
                const magLinks = document.querySelectorAll('a[href*="/search/magazine/"]');
                if (magLinks.length > 0) {
                    result.label = Array.from(magLinks).map(a => a.textContent.trim()).join(', ');
                }

                // 태그 — 중복 제거
                const tagLinks = document.querySelectorAll('a[href*="/search/titletag/"]');
                if (tagLinks.length > 0) {
                    const tags = [...new Set(Array.from(tagLinks).map(a => a.textContent.trim()))];
                    result.tags = tags.join(',');
                }

                // 장르 (서브장르 포함)
                const genreLinks = document.querySelectorAll('a[href*="/search/genre/"]');
                if (genreLinks.length > 0 && !result.genre) {
                    result.genre = Array.from(genreLinks).map(a => a.textContent.trim()).join(' / ');
                }

                return result;
            }
        ''')

        return detail


async def run_detail_scraper(max_works: int = 50, riverse_only: bool = False):
    """독립 실행용 래퍼"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            scraper = DetailScraper(max_works=max_works)
            await scraper.run(browser, riverse_only=riverse_only)
        finally:
            await browser.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='작품 상세 메타데이터 스크래퍼')
    parser.add_argument('--riverse', action='store_true', help='리버스 작품만 수집 (전체 강제 재수집)')
    parser.add_argument('--max-works', type=int, default=50, help='최대 작품 수 (기본 50)')
    args = parser.parse_args()

    max_w = args.max_works if not args.riverse else max(args.max_works, 500)
    mode = "리버스 전용" if args.riverse else "일반"
    print("=" * 60)
    print(f"상세 페이지 메타데이터 스크래퍼 ({mode}, 최대 {max_w}개)")
    print("=" * 60)
    asyncio.run(run_detail_scraper(max_works=max_w, riverse_only=args.riverse))
