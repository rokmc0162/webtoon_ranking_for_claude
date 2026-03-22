"""
벨툰 (BeLTOON) 크롤러 에이전트

특징:
- CSR 방식 (Next.js + styled-components)
- IP 제한 없음
- 해시된 클래스명 → 구조 기반 셀렉터 사용
- li > div > span > div > img 패턴, image.balcony.studio 도메인
- 종합: /app/all/ranking URL 직접 접근
- 장르별: 필터(絞り込み) UI에서 장르 태그 선택 후 적용
"""

import re
from typing import List, Dict, Any
from playwright.async_api import Browser

from crawler.agents.base_agent import CrawlerAgent


class BeltoonAgent(CrawlerAgent):
    """벨툰 데일리 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '종합(데일리)', 'slug': 'all'},
        'ロマンス': {'name': '로만스', 'filter_tag': 'ロマンス'},
    }

    def __init__(self):
        super().__init__(
            platform_id='beltoon',
            platform_name='벨툰 (BeLTOON)',
            url='https://www.beltoon.jp/app/all/ranking'
        )
        self.genre_results = {}

    async def crawl(self, browser: Browser) -> List[Dict[str, Any]]:
        """벨툰 종합 + 장르별 데일리 랭킹 크롤링"""
        page = await browser.new_page()
        all_rankings = []

        try:
            for genre_key, genre_info in self.GENRE_RANKINGS.items():
                label = genre_info['name']

                self.logger.info(f"📱 벨툰 [{label}] 크롤링 중...")

                try:
                    if genre_key == '':
                        # 종합: URL 직접 접근
                        rankings = await self._crawl_all(page)
                    else:
                        # 장르별: 필터 UI로 장르 선택
                        filter_tag = genre_info['filter_tag']
                        rankings = await self._crawl_filtered(page, filter_tag)

                    # genre 설정: 종합은 '総合', 그 외는 genre_key
                    genre_value = genre_key if genre_key else '総合'
                    for item in rankings:
                        item['genre'] = genre_value

                    self.genre_results[genre_key] = rankings
                    self.logger.info(f"   ✅ [{label}]: {len(rankings)}개 작품")
                except Exception as e:
                    self.logger.warning(f"   ⚠️ [{label}] 크롤링 실패: {e}")
                    self.genre_results[genre_key] = []
                    continue

                # 종합 랭킹은 반환값으로 사용
                if genre_key == '':
                    all_rankings = rankings

            return all_rankings

        finally:
            await page.close()

    async def _crawl_all(self, page) -> List[Dict[str, Any]]:
        """종합 랭킹: URL 직접 접근"""
        await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # 스크롤 다운으로 lazy loading 트리거
        for _ in range(10):
            await page.evaluate('window.scrollBy(0, 1000)')
            await page.wait_for_timeout(500)

        rankings = await self._parse_dom_rankings(page)

        if len(rankings) < 5:
            self.logger.info(f"   DOM 파싱 부족, 텍스트 폴백...")
            body_text = await page.inner_text('body')
            rankings = self._parse_text_rankings(body_text)

        return rankings

    async def _crawl_filtered(self, page, filter_tag: str) -> List[Dict[str, Any]]:
        """장르별 랭킹: 필터 UI에서 장르 체크박스 선택"""
        # 종합 랭킹 페이지로 이동 (필터 초기화)
        await page.goto(self.url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(5000)

        # 1. 絞り込み(필터) 버튼 클릭
        filter_btn = await page.query_selector('text="絞り込み"')
        if not filter_btn:
            self.logger.warning("   ⚠️ 絞り込み 버튼을 찾을 수 없음")
            return []
        await filter_btn.click()
        await page.wait_for_timeout(2000)
        self.logger.info(f"   🔍 필터 팝업 열기")

        # 2. 장르 체크박스: filter_tag만 남기고 나머지 해제
        genre_labels = await page.query_selector_all('label[data-type="genre"]')
        for label in genre_labels:
            text_span = await label.query_selector('.text')
            text = await text_span.inner_text() if text_span else ''
            checkbox = await label.query_selector('input[type="checkbox"]')
            is_checked = await checkbox.is_checked() if checkbox else False

            if text == filter_tag:
                # 원하는 장르는 체크 유지
                if not is_checked:
                    await label.click()
                    await page.wait_for_timeout(200)
                self.logger.info(f"   🏷️ {text} 체크 유지")
                continue

            # 나머지 장르 해제
            if is_checked:
                await label.click()
                await page.wait_for_timeout(200)

        await page.wait_for_timeout(500)

        # 3. 絞り込む(적용) 버튼 클릭 - 검색결과 건수 로그
        apply_btn = await page.query_selector('button:has-text("絞り込む")')
        if not apply_btn:
            self.logger.warning("   ⚠️ 絞り込む 버튼을 찾을 수 없음")
            return []
        btn_text = await apply_btn.inner_text()
        self.logger.info(f"   🔎 {btn_text}")
        await apply_btn.click()
        await page.wait_for_timeout(5000)

        # 4. 스크롤 다운
        for _ in range(10):
            await page.evaluate('window.scrollBy(0, 1000)')
            await page.wait_for_timeout(500)

        # 5. DOM 파싱
        rankings = await self._parse_dom_rankings(page)

        if len(rankings) < 1:
            self.logger.info(f"   DOM 파싱 부족, 텍스트 폴백...")
            body_text = await page.inner_text('body')
            rankings = self._parse_text_rankings(body_text)

        return rankings

    async def _parse_dom_rankings(self, page) -> List[Dict[str, Any]]:
        """DOM에서 랭킹 아이템 + 썸네일 추출"""
        items = await page.evaluate("""() => {
            const results = [];
            // beltoon: styled-components, 구조 기반으로 추출
            // li 안에 img[alt="thumbnail"] + 텍스트 구조
            const allLis = document.querySelectorAll('li');
            let rank = 0;

            for (const li of allLis) {
                const img = li.querySelector('img[alt="thumbnail"], img[src*="balcony.studio"], img[src*="image."]');
                if (!img) continue;

                const src = img.getAttribute('src') || '';
                if (!src || src.includes('logo') || src.includes('icon')) continue;

                // 타이틀: li 내의 텍스트 노드 중 적절한 것 찾기
                // 보통 img 이후에 span 또는 p 로 타이틀이 있음
                let title = '';
                const textEls = li.querySelectorAll('span, p, h3, h4, div');
                for (const el of textEls) {
                    const text = el.textContent.trim();
                    // 숫자만(순위), 조회수(N만), 작가명은 스킵
                    if (text.length >= 3 && text.length <= 100 &&
                        !/^\\d+$/.test(text) &&
                        !/^[\\d.]+만$/.test(text) &&
                        !text.includes('チェック') &&
                        !text.includes('ロマンス') &&
                        !text.includes('BL') &&
                        el.children.length === 0) {
                        title = text;
                        break;
                    }
                }

                if (!title || title.length < 2) continue;

                // URL: beltoon은 a 태그 없음 — 이미지 URL에서 slug 추출 후 /detail/{slug} 구성
                // 이미지 URL 패턴: .../co_thumbnail/{slug}/{timestamp}.webp
                const slugMatch = src.match(/co_thumbnail\/([^\/]+)\//);
                const slug = slugMatch ? slugMatch[1] : '';
                const fullUrl = slug ? ('https://www.beltoon.jp/detail/' + slug) : '';

                const thumbUrl = src.startsWith('http') ? src : (src.startsWith('/') ? 'https://www.beltoon.jp' + src : '');

                rank++;
                if (rank <= 100) {
                    results.push({
                        rank: rank,
                        title: title,
                        url: fullUrl,
                        thumbnail_url: thumbUrl,
                    });
                }
            }
            return results;
        }""")

        return [
            {
                'rank': item['rank'],
                'title': item['title'],
                'genre': '',
                'url': item.get('url', ''),
                'thumbnail_url': item.get('thumbnail_url', ''),
            }
            for item in items[:100]
        ]

    def _parse_text_rankings(self, body_text: str) -> List[Dict[str, Any]]:
        """텍스트에서 랭킹 아이템 추출 - 폴백"""
        lines = [l.strip() for l in body_text.split('\n') if l.strip()]
        rankings = []

        start_idx = 0
        for i, line in enumerate(lines):
            if line == 'デイリー':
                start_idx = i + 1
                break

        i = start_idx
        while i < len(lines) and len(rankings) < 100:
            line = lines[i]

            if line.isdigit() and 1 <= int(line) <= 100:
                rank = int(line)
                j = i + 1
                while j < len(lines) and lines[j].isdigit():
                    j += 1

                if j < len(lines):
                    title = lines[j].strip()
                    if (len(title) >= 2 and
                            title not in ['チェック解除', '絞り込み', '...', 'ロマンス',
                                          'BL', 'ファンタジー', 'ドラマ', 'GL', '少女マンガ'] and
                            not title.startswith('(')):
                        rankings.append({
                            'rank': rank,
                            'title': title,
                            'genre': '',
                            'url': 'https://www.beltoon.jp/app/all/ranking',
                            'thumbnail_url': '',
                        })
                        i = j + 1
                        continue

            i += 1

        return rankings

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 모두 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 랭킹 저장
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
             'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data if item.get('thumbnail_url')
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        # 장르별 랭킹 저장
        for genre_key, rankings in self.genre_results.items():
            if genre_key == '':
                continue
            genre_name = self.GENRE_RANKINGS[genre_key]['name']
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': item.get('thumbnail_url', ''),
                 'url': item.get('url', ''), 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings if item.get('thumbnail_url')
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{genre_name}]: {len(rankings)}개 저장")
