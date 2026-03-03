"""
라인망가 앱 (LINE マンガ Android) ADB 크롤러 에이전트

특징:
- ADB + uiautomator dump로 안드로이드 앱에서 직접 크롤링
- 브라우저 불필요 (Playwright 미사용)
- 3열 그리드 레이아웃, 위치 기반 순위 결정
- 今日の人気ランキング (총합) 페이지 크롤링
- すべて + 장르별 탭 수집 (キャンペーン, ￥0パス 제외)
"""

import asyncio
import subprocess
import xml.etree.ElementTree as ET
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

from crawler.agents.base_agent import CrawlerAgent, AgentResult

logger = logging.getLogger('crawler.agents.linemanga_app')

# 앱 패키지
PACKAGE = 'jp.naver.linemanga.android'

# 수집할 장르 탭 목록 (탭 순서대로)
GENRE_TABS = [
    {'key': '', 'tab_name': 'すべて', 'label': '전체'},
    {'key': '恋愛', 'tab_name': '恋愛', 'label': '연애'},
    {'key': 'ファンタジー・SF', 'tab_name': 'ファンタジー･SF', 'label': '판타지/SF'},
    {'key': 'ミステリー・ホラー', 'tab_name': 'ミステリー･ホラー', 'label': '미스터리/호러'},
    {'key': 'ヒューマンドラマ', 'tab_name': 'ヒューマンドラマ', 'label': '휴먼드라마'},
    {'key': 'バトル・アクション', 'tab_name': 'バトル･アクション', 'label': '배틀/액션'},
    {'key': '裏社会・アングラ', 'tab_name': '裏社会･アングラ', 'label': '뒷세계'},
    {'key': 'コメディ・ギャグ', 'tab_name': 'コメディ･ギャグ', 'label': '코미디/개그'},
    {'key': 'スポーツ', 'tab_name': 'スポーツ', 'label': '스포츠'},
    {'key': '歴史・時代', 'tab_name': '歴史･時代', 'label': '역사/시대'},
]

# 제외할 탭
SKIP_TABS = {'キャンペーン', '￥0パス', '新着', 'オリジナル', '雑誌', '小説･ラノベ', 'その他'}

# 순위 데이터가 아닌 텍스트 (필터링용)
NON_TITLE_TEXTS = {
    'ランキング', '総合', '女性', '男性', 'コインGET!',
    'home', 'search', 'serial_top_weekly', 'store', 'bookshelf',
    'おすすめ', '探す', 'オリジナル', '単行本', '本棚',
}

# 장르 라벨 목록
GENRE_LABELS = {
    '恋愛', 'ファンタジー・SF', 'ファンタジー･SF', 'ミステリー・ホラー', 'ミステリー･ホラー',
    'バトル・アクション', 'バトル･アクション', 'ヒューマンドラマ', '裏社会・アングラ', '裏社会･アングラ',
    'コメディ・ギャグ', 'コメディ･ギャグ', 'スポーツ', '歴史・時代', '歴史･時代',
    'その他', '小説・ラノベ', '小説･ラノベ', '雑誌',
}


class LinemangaAppAgent(CrawlerAgent):
    """라인망가 앱 ADB 크롤러 에이전트"""

    def __init__(self):
        super().__init__(
            platform_id='linemanga_app',
            platform_name='라인망가 (앱)',
            url=''  # 앱이라 URL 없음
        )
        self.genre_results = {}
        self.device_id = None

    # ===== ADB 헬퍼 메서드 =====

    def _run_adb(self, cmd: str, timeout: int = 15) -> str:
        """ADB 명령 실행"""
        full_cmd = f'adb shell {cmd}'
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            self.logger.warning(f"ADB timeout: {cmd}")
            return ''
        except Exception as e:
            self.logger.error(f"ADB error: {e}")
            return ''

    def _check_device(self) -> bool:
        """ADB 디바이스 연결 확인"""
        try:
            result = subprocess.run(
                'adb devices', shell=True, capture_output=True, text=True, timeout=10
            )
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # 첫 줄 "List of devices attached" 스킵
                if '\tdevice' in line:
                    self.device_id = line.split('\t')[0]
                    return True
            return False
        except Exception:
            return False

    def _tap(self, x: int, y: int):
        """화면 좌표 탭"""
        self._run_adb(f'input tap {x} {y}')

    def _swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """스와이프"""
        self._run_adb(f'input swipe {x1} {y1} {x2} {y2} {duration}')

    def _swipe_up(self):
        """화면 위로 스크롤 (랭킹 더 보기)"""
        self._swipe(540, 1800, 540, 600, 400)

    def _swipe_tabs_left(self):
        """탭 바를 왼쪽으로 스크롤 (더 많은 탭 보기)"""
        self._swipe(900, 258, 100, 258, 300)

    def _swipe_tabs_right(self):
        """탭 바를 오른쪽으로 스크롤 (처음 탭으로 돌아가기)"""
        self._swipe(100, 258, 900, 258, 300)

    def _dump_ui(self, local_path: str = '/tmp/lm_app_ui.xml') -> Optional[ET.Element]:
        """UI 트리 덤프 & 파싱"""
        try:
            self._run_adb('uiautomator dump /sdcard/ui.xml')
            subprocess.run(
                f'adb pull /sdcard/ui.xml {local_path}',
                shell=True, capture_output=True, timeout=10
            )
            tree = ET.parse(local_path)
            return tree.getroot()
        except Exception as e:
            self.logger.error(f"UI dump failed: {e}")
            return None

    def _find_element_bounds(self, root: ET.Element, text: str) -> Optional[Tuple[int, int, int, int]]:
        """텍스트로 UI 요소의 bounds 찾기 (공백 무시)"""
        for node in root.iter('node'):
            node_text = node.get('text', '').strip()
            node_desc = node.get('content-desc', '').strip()
            if text in (node_text, node_desc):
                bounds = node.get('bounds', '')
                try:
                    parts = bounds.replace('[', '').replace(']', ',').split(',')
                    return int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                except:
                    pass
        return None

    def _tap_center(self, bounds: Tuple[int, int, int, int]):
        """bounds 중앙을 탭"""
        x = (bounds[0] + bounds[2]) // 2
        y = (bounds[1] + bounds[3]) // 2
        self._tap(x, y)

    # ===== 크롤링 로직 =====

    def _parse_ranking_items(self, root: ET.Element) -> List[Dict[str, Any]]:
        """
        현재 화면에서 랭킹 아이템 파싱.

        UI 구조 (3열 그리드):
        - ranking level (View) → 순위 아이콘
        - rank changed (View) + 숫자 (TextView) → 순위 변동
        - 제목 (TextView) → 작품명
        - 장르/무료정보 (TextView) → 장르 또는 "14話無料" 등

        Returns:
            타이틀 목록 [{title, genre, x, y}, ...]
        """
        items = []

        for node in root.iter('node'):
            text = node.get('text', '')
            desc = node.get('content-desc', '')
            bounds = node.get('bounds', '')

            if not text or not bounds:
                continue

            # bounds 파싱
            try:
                parts = bounds.replace('[', '').replace(']', ',').split(',')
                x1, y1, x2, y2 = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            except:
                continue

            # 콘텐츠 영역만 (탭/네비 바 제외)
            if y1 < 400 or y1 > 2100:
                continue

            # 제외: 시스템 텍스트, 랭킹 메타정보
            if text in NON_TITLE_TEXTS:
                continue
            if '集計' in text:
                continue

            # 제외: 무료 정보, 순위 변동 숫자
            if '話無料' in text or '冊無料' in text or 'CMみて' in text or '¥0パス' in text:
                continue

            # 제외: 순위 변동 숫자 (1~3자리 숫자)
            try:
                num = int(text)
                if 1 <= num <= 999:
                    continue
            except ValueError:
                pass

            # 제외: 장르 라벨
            if text in GENRE_LABELS:
                # 장르 정보는 아이템에 연결할 수 있으나, 일단 제목만 수집
                continue

            # 나머지 = 작품 제목
            items.append({
                'title': text.strip(),
                'x': x1,
                'y': y1,
            })

        # x좌표 기반 열, y좌표 기반 행으로 정렬 (왼쪽→오른쪽, 위→아래)
        items.sort(key=lambda item: (item['y'], item['x']))

        return items

    def _collect_tab_rankings(self, max_scrolls: int = 15, max_items: int = 100) -> List[Dict[str, Any]]:
        """
        현재 탭에서 스크롤하며 전체 랭킹 수집.

        Returns:
            [{rank, title, genre, url}, ...]
        """
        import time
        all_titles = []
        seen_titles = set()
        no_new_count = 0

        for scroll_i in range(max_scrolls + 1):
            time.sleep(1.5 if scroll_i == 0 else 1)

            root = self._dump_ui(f'/tmp/lm_app_scroll_{scroll_i}.xml')
            if root is None:
                break

            items = self._parse_ranking_items(root)
            new_count = 0

            for item in items:
                title = item['title']
                if title not in seen_titles:
                    seen_titles.add(title)
                    all_titles.append(title)
                    new_count += 1

            self.logger.debug(f"  Scroll {scroll_i}: {new_count} new, total {len(all_titles)}")

            if new_count == 0:
                no_new_count += 1
                if no_new_count >= 2:
                    break
            else:
                no_new_count = 0

            if len(all_titles) >= max_items:
                break

            if scroll_i < max_scrolls:
                self._swipe_up()

        # 순위 할당 (수집 순서 = 순위)
        rankings = []
        for rank, title in enumerate(all_titles[:max_items], 1):
            rankings.append({
                'rank': rank,
                'title': title,
                'genre': '',
                'url': '',
                'thumbnail_url': '',
            })

        return rankings

    def _navigate_to_ranking_page(self) -> bool:
        """
        홈 → 今日の人気ランキング → 총합 랭킹 페이지로 이동.

        Returns:
            True if successfully navigated
        """
        import time

        # 1. 앱 종료 후 재실행
        self.logger.info("📱 라인망가 앱 재시작...")
        self._run_adb(f'am force-stop {PACKAGE}')
        time.sleep(2)
        self._run_adb(
            f'monkey -p {PACKAGE} -c android.intent.category.LAUNCHER 1'
        )
        time.sleep(6)

        # 2. 팝업 닫기 (최대 3번 시도)
        for popup_i in range(3):
            root = self._dump_ui()
            if root is None:
                return False

            # "閉じる" 버튼 찾기
            close_bounds = self._find_element_bounds(root, '閉じる')
            if close_bounds:
                self.logger.info(f"  팝업 닫기 ({popup_i + 1})...")
                # "次回から表示しない" 먼저 탭
                dont_show = self._find_element_bounds(root, '次回から表示しない')
                if dont_show:
                    self._tap_center(dont_show)
                    time.sleep(0.5)
                self._tap_center(close_bounds)
                time.sleep(2)
            else:
                break

        # 3. 홈 탭을 두 번 탭하여 맨 위로 스크롤
        root = self._dump_ui()
        if root:
            home_bounds = self._find_element_bounds(root, 'おすすめ')
            if not home_bounds:
                home_bounds = self._find_element_bounds(root, 'home')
            if home_bounds:
                self._tap_center(home_bounds)
                time.sleep(0.5)
                self._tap_center(home_bounds)
                time.sleep(1)
                self.logger.debug("  홈 탭 더블탭 → 맨 위로 이동")

        # 4. 홈 화면에서 "今日の人気ランキング" 찾기 (스크롤)
        for scroll_i in range(8):
            root = self._dump_ui()
            if root is None:
                return False

            ranking_bounds = self._find_element_bounds(root, '今日の人気ランキング')
            if ranking_bounds:
                # "今日の人気ランキング" 제목 자체를 탭 → 전용 랭킹 페이지로 이동
                self.logger.info("  '今日の人気ランキング' 발견 → 탭")
                self._tap_center(ranking_bounds)
                time.sleep(4)

                # 5. ランキング 페이지 도달 확인
                root = self._dump_ui()
                if root is None:
                    return False

                ranking_header = self._find_element_bounds(root, 'ランキング')
                if ranking_header:
                    self.logger.info("  ✅ 랭킹 페이지 도달")
                    return True

                self.logger.warning("  ⚠️ 랭킹 페이지 확인 실패, 재시도...")
                # 홈으로 돌아가서 재시도
                home_bounds = self._find_element_bounds(root, 'おすすめ')
                if home_bounds:
                    self._tap_center(home_bounds)
                    time.sleep(1)
                continue

            self._swipe_up()
            time.sleep(1)

        self.logger.error("❌ 랭킹 페이지를 찾을 수 없음")
        return False

    def _navigate_to_tab(self, tab_name: str) -> bool:
        """
        탭 이름으로 특정 장르 탭 이동.
        탭 바를 좌우 스크롤하며 찾음.
        """
        import time

        # 먼저 탭 바를 맨 왼쪽으로 리셋 (오른쪽으로 3번 스크롤)
        for _ in range(4):
            self._swipe_tabs_right()
            time.sleep(0.5)

        # 왼쪽으로 스크롤하며 탭 찾기 (최대 5번)
        for scroll_i in range(6):
            time.sleep(0.5)
            root = self._dump_ui()
            if root is None:
                return False

            bounds = self._find_element_bounds(root, tab_name)
            if bounds:
                self._tap_center(bounds)
                time.sleep(2)
                return True

            self._swipe_tabs_left()

        self.logger.warning(f"  ⚠️ 탭 '{tab_name}' 을 찾을 수 없음")
        return False

    # ===== CrawlerAgent 인터페이스 =====

    async def execute(self, browser=None) -> AgentResult:
        """
        ADB 기반 크롤링 실행 (browser 파라미터 무시).
        """
        self.logger.info(f"Starting {self.platform_name} crawler (ADB)")

        for attempt in range(self.max_retries):
            try:
                # 1. 디바이스 확인
                if not self._check_device():
                    return AgentResult(
                        success=False,
                        platform=self.platform_id,
                        error="ADB device not connected (skip)",
                        attempts=1
                    )
                self.logger.info(f"  📱 Device: {self.device_id}")

                # 2. 랭킹 페이지로 이동
                if not self._navigate_to_ranking_page():
                    raise Exception("Failed to navigate to ranking page")

                # 3. すべて 탭 크롤링 (전체 랭킹)
                self.logger.info("📱 라인망가 앱 [전체] 크롤링 중...")
                if not self._navigate_to_tab('すべて'):
                    raise Exception("Failed to navigate to すべて tab")

                import time
                time.sleep(2)
                all_rankings = self._collect_tab_rankings()
                self.logger.info(f"  ✅ [전체]: {len(all_rankings)}개 작품")
                self.genre_results[''] = all_rankings

                # 4. 장르별 탭 크롤링
                for genre_info in GENRE_TABS[1:]:  # すべて 스킵
                    tab_name = genre_info['tab_name']
                    label = genre_info['label']
                    genre_key = genre_info['key']

                    self.logger.info(f"📱 라인망가 앱 [{label}] 크롤링 중...")

                    try:
                        if self._navigate_to_tab(tab_name):
                            time.sleep(2)
                            rankings = self._collect_tab_rankings()
                            self.genre_results[genre_key] = rankings
                            self.logger.info(f"  ✅ [{label}]: {len(rankings)}개 작품")
                        else:
                            self.genre_results[genre_key] = []
                            self.logger.warning(f"  ⚠️ [{label}] 탭 이동 실패")
                    except Exception as e:
                        self.logger.warning(f"  ⚠️ [{label}] 실패: {e}")
                        self.genre_results[genre_key] = []

                # 5. 데이터 검증
                if self.validate(all_rankings):
                    from datetime import datetime
                    date = datetime.now().strftime('%Y-%m-%d')
                    await self.save(date, all_rankings)

                    self.logger.info(
                        f"✅ {self.platform_name}: {len(all_rankings)}개 작품 수집 완료"
                    )
                    return AgentResult(
                        success=True,
                        platform=self.platform_id,
                        data=all_rankings,
                        attempts=attempt + 1
                    )
                else:
                    raise ValueError(f"Validation failed: {len(all_rankings)} items")

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(
                    f"Attempt {attempt + 1}/{self.max_retries} failed: {error_msg}"
                )
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[attempt]
                    self.logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"❌ {self.platform_name} 실패: {error_msg}"
                    )
                    return AgentResult(
                        success=False,
                        platform=self.platform_id,
                        error=error_msg,
                        attempts=attempt + 1
                    )

        return AgentResult(
            success=False,
            platform=self.platform_id,
            error="Unknown error",
            attempts=self.max_retries
        )

    async def crawl(self, browser=None) -> List[Dict[str, Any]]:
        """사용되지 않음 (execute()에서 직접 처리)"""
        return []

    def validate(self, data: List[Dict[str, Any]]) -> bool:
        """ADB 크롤링은 최소 5개 이상이면 유효"""
        if not data or len(data) < 5:
            self.logger.warning(f"Validation failed: only {len(data) if data else 0} items")
            return False
        for item in data:
            if 'rank' not in item or 'title' not in item:
                return False
        return True

    async def save(self, date: str, data: List[Dict[str, Any]]):
        """종합 + 장르별 랭킹 저장"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 랭킹 저장
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': '', 'url': '',
             'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        # 장르별 랭킹 저장
        for genre_info in GENRE_TABS[1:]:
            genre_key = genre_info['key']
            label = genre_info['label']
            rankings = self.genre_results.get(genre_key, [])
            if not rankings:
                continue
            save_rankings(date, self.platform_id, rankings, sub_category=genre_key)
            genre_meta = [
                {'title': item['title'], 'thumbnail_url': '', 'url': '',
                 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings
            ]
            if genre_meta:
                save_works_metadata(self.platform_id, genre_meta, date=date, sub_category=genre_key)
            self.logger.info(f"   💾 [{label}]: {len(rankings)}개 저장")


if __name__ == "__main__":
    import asyncio
    import time

    async def test():
        print("=" * 60)
        print("라인망가 앱 (ADB) 에이전트 테스트")
        print("=" * 60)

        agent = LinemangaAppAgent()

        # 디바이스 체크
        if not agent._check_device():
            print("❌ ADB 디바이스가 연결되지 않았습니다.")
            return

        print(f"📱 Device: {agent.device_id}")

        result = await agent.execute()

        print(f"\n✅ Success: {result.success}")
        print(f"📊 Count: {result.count}")

        if result.success and result.data:
            print(f"\n샘플 (1~10위):")
            for item in result.data[:10]:
                print(f"  {item['rank']}위: {item['title']}")

            print(f"\n장르별 결과:")
            for genre_info in GENRE_TABS:
                key = genre_info['key']
                label = genre_info['label']
                rankings = agent.genre_results.get(key, [])
                print(f"  [{label}]: {len(rankings)}개")
        else:
            print(f"\n❌ Error: {result.error}")

        print("\n" + "=" * 60)

    asyncio.run(test())
