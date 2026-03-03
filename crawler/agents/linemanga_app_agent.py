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

# 성별 필터 (랭킹 페이지 상단 오른쪽)
GENDER_FILTERS = [
    {'key': '', 'name': '総合', 'label': '종합'},
    {'key': '女性', 'name': '女性', 'label': '여성'},
    {'key': '男性', 'name': '男性', 'label': '남성'},
]

# 3열 그리드 칼럼 좌표 (랭킹 페이지 실측, 1080px 너비)
COLUMN_BOUNDS = [
    (38, 360),    # Column 0
    (379, 701),   # Column 1
    (720, 1042),  # Column 2
]

# 콘텐츠 영역 Y좌표 경계 (스크린샷 기반 실측)
# 상태바(0-77) + 헤더(108-171) + 탭바(190-314) + 성별필터(314-435) = 435부터 그리드
CONTENT_TOP_Y = 435     # 그리드 콘텐츠 시작 (탭/헤더 아래)
CONTENT_BOTTOM_Y = 2107 # 그리드 콘텐츠 끝 (하단 네비바 위)

# 타이틀→커버 이미지 오프셋 (실측 기반)
THUMB_OFFSET_TOP = 495   # 타이틀 y - 커버이미지 상단 = 495px
THUMB_OFFSET_BOTTOM = 38 # 타이틀 y - 커버이미지 하단 = 38px

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

    # ===== 스크린샷 & 썸네일 =====

    def _capture_screenshot(self, local_path: str = '/tmp/lm_app_screen.png'):
        """스크린샷 캡처 → PIL Image 반환"""
        try:
            self._run_adb('screencap -p /sdcard/screen.png')
            subprocess.run(
                f'adb pull /sdcard/screen.png {local_path}',
                shell=True, capture_output=True, timeout=10
            )
            from PIL import Image as PILImage
            return PILImage.open(local_path)
        except Exception as e:
            self.logger.warning(f"Screenshot failed: {e}")
            return None

    def _crop_thumbnail(self, screenshot, title_x: int, title_y: int):
        """
        작품 타이틀 위치 기반으로 커버 이미지 영역 크롭 → (base64, crop_height).

        레이아웃 (실측):
        - 탭바+헤더: y=0~435 (CONTENT_TOP_Y)
        - 커버 이미지: title_y - 495 ~ title_y - 38
        - 하단 네비바: y=2107~ (CONTENT_BOTTOM_Y)

        경계에 걸치면 클램핑으로 부분 캡처. crop_height로 품질 판별.
        전체 커버 높이 = THUMB_OFFSET_TOP - THUMB_OFFSET_BOTTOM = 457px
        """
        import base64
        from io import BytesIO
        import numpy as np

        if screenshot is None:
            return '', 0

        # 컬럼 결정 (가장 가까운 컬럼 중심으로 매칭)
        col_left, col_right = COLUMN_BOUNDS[0]
        best_dist = 9999
        for cx1, cx2 in COLUMN_BOUNDS:
            center = (cx1 + cx2) / 2
            dist = abs(title_x - center)
            if dist < best_dist:
                best_dist = dist
                col_left, col_right = cx1, cx2

        # 썸네일 영역 계산 (실측 기반 오프셋)
        thumb_top = title_y - THUMB_OFFSET_TOP
        thumb_bottom = title_y - THUMB_OFFSET_BOTTOM

        # 경계 클램핑: 헤더/네비바에 걸치면 잘라내서 부분 캡처
        if thumb_top < CONTENT_TOP_Y:
            thumb_top = CONTENT_TOP_Y
        if thumb_bottom > CONTENT_BOTTOM_Y:
            thumb_bottom = CONTENT_BOTTOM_Y

        # 유효성: 스크린 밖(완전히 안 보이는 경우) 스킵
        if thumb_bottom <= CONTENT_TOP_Y or thumb_top >= CONTENT_BOTTOM_Y:
            return '', 0

        crop_height = thumb_bottom - thumb_top

        # 최소 높이 검증 (100px 이상이면 부분 캡처라도 인식 가능)
        if crop_height < 100:
            return '', 0

        try:
            crop = screenshot.crop((col_left, thumb_top, col_right, thumb_bottom))
            crop_rgb = crop.convert('RGB')

            # 이미지 품질 검증: 너무 단조로운 이미지 거부 (UI 요소 잘못 캡처 방지)
            arr = np.array(crop_rgb)
            std = arr.std()
            if std < 15:
                return '', 0

            # 150x200 리사이즈 + JPEG 압축
            crop_resized = crop_rgb.resize((150, 200))
            buf = BytesIO()
            crop_resized.save(buf, format='JPEG', quality=65)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return f"data:image/jpeg;base64,{b64}", crop_height
        except Exception:
            return '', 0

    def _switch_gender_on_home(self, gender_name: str) -> bool:
        """
        홈 화면에서 성별 필터 전환.

        흐름:
        1. 홈에서 스크롤하며 "今日の人気ランキング" 섹션 찾기
        2. 옆의 현재 필터(총합/남성/여성) 텍스트 탭
        3. 바텀시트 드롭다운에서 원하는 성별 선택
        """
        import time, re

        # 홈 탭 더블탭으로 맨 위로 이동
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

        # 스크롤하며 "今日の人気ランキング" 섹션 찾기
        for scroll_i in range(8):
            root = self._dump_ui()
            if root is None:
                return False

            # 랭킹 섹션의 성별 필터 버튼 찾기
            # "今日の人気ランキング" 근처에 있는 総合/男性/女性 텍스트
            ranking_title = self._find_element_bounds(root, '今日の人気ランキング')
            if ranking_title:
                # 같은 높이(y좌표 비슷)에 있는 필터 버튼 찾기
                rt_y = ranking_title[1]  # y1 좌표

                filter_bounds = None
                for label in ['総合', '男性', '女性']:
                    b = self._find_element_bounds(root, label)
                    if b:
                        by = b[1]  # y1 좌표
                        # 랭킹 제목과 같은 높이 (±100px)
                        if abs(by - rt_y) < 100:
                            filter_bounds = b
                            break

                if filter_bounds:
                    # 필터 버튼 탭 → 드롭다운 열기
                    self._tap_center(filter_bounds)
                    time.sleep(2)

                    # 드롭다운에서 원하는 성별 선택
                    root = self._dump_ui()
                    if root is None:
                        return False

                    target = self._find_element_bounds(root, gender_name)
                    if not target:
                        self.logger.warning(f"  ⚠️ 드롭다운에서 '{gender_name}' 을 찾을 수 없음")
                        self._run_adb('shell input keyevent KEYCODE_BACK')
                        time.sleep(1)
                        return False

                    self._tap_center(target)
                    time.sleep(3)
                    self.logger.info(f"  ✅ 성별 필터 '{gender_name}' 선택 완료")
                    return True

            self._swipe_up()
            time.sleep(1)

        self.logger.warning("  ⚠️ 홈에서 랭킹 섹션을 찾을 수 없음")
        return False

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

            # 콘텐츠 영역만 (탭/헤더/네비 바 제외)
            if y1 < CONTENT_TOP_Y or y1 > CONTENT_BOTTOM_Y:
                continue

            # 제외: 시스템 텍스트, 랭킹 메타정보
            if text in NON_TITLE_TEXTS:
                continue
            if '集計' in text:
                continue

            # 제외: 무료 정보, 순위 변동 숫자
            if '話無料' in text or '冊無料' in text or 'CMみて' in text or '¥0パス' in text:
                continue

            # 제외: 순위 변동/조회수 숫자 (콤마 포함 숫자, 순수 숫자)
            text_stripped = text.replace(',', '').replace('.', '')
            try:
                num = int(text_stripped)
                # 어떤 크기의 순수 숫자도 작품 제목이 아님
                continue
            except ValueError:
                pass

            # 제외: 에피소드 표시 "56話. (56)", "100話. (100)" 등
            if '話.' in text or '話 ' in text:
                continue

            # 제외: 너무 짧은 텍스트 (2글자 이하)
            if len(text.strip()) <= 2:
                continue

            # 제외: 장르 라벨
            if text in GENRE_LABELS:
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

    def _collect_tab_rankings(self, max_scrolls: int = 15, max_items: int = 100,
                              capture_thumbs: bool = True) -> List[Dict[str, Any]]:
        """
        현재 탭에서 스크롤하며 전체 랭킹 수집 + 썸네일 캡처.

        Returns:
            [{rank, title, genre, url, thumbnail_url}, ...]
        """
        import time
        all_items = []  # (title, thumb_b64)
        seen_titles = set()
        title_to_idx = {}  # title → index in all_items (빠른 룩업)
        no_new_count = 0

        # 전체 크롭 높이 기준 (이보다 낮으면 부분 크롭 → 더 나은 걸로 교체 시도)
        FULL_CROP_THRESHOLD = 400  # 전체 높이 457px의 ~87%

        for scroll_i in range(max_scrolls + 1):
            time.sleep(1.5 if scroll_i == 0 else 1)

            root = self._dump_ui(f'/tmp/lm_app_scroll_{scroll_i}.xml')
            if root is None:
                break

            # 썸네일 캡처용 스크린샷 (모든 스크롤)
            screenshot = None
            if capture_thumbs:
                screenshot = self._capture_screenshot(f'/tmp/lm_app_ss_{scroll_i}.png')

            items = self._parse_ranking_items(root)
            new_count = 0

            for item in items:
                title = item['title']
                if title not in seen_titles:
                    # 신규 아이템
                    seen_titles.add(title)
                    thumb_b64 = ''
                    thumb_h = 0
                    if screenshot:
                        thumb_b64, thumb_h = self._crop_thumbnail(screenshot, item['x'], item['y'])
                    idx = len(all_items)
                    all_items.append((title, thumb_b64, thumb_h))
                    title_to_idx[title] = idx
                    new_count += 1
                elif screenshot and title in title_to_idx:
                    # 기존 아이템: 썸네일이 없거나 부분 크롭이면 → 재시도
                    idx = title_to_idx[title]
                    cur_h = all_items[idx][2]
                    if cur_h < FULL_CROP_THRESHOLD:
                        new_thumb, new_h = self._crop_thumbnail(screenshot, item['x'], item['y'])
                        if new_h > cur_h:
                            all_items[idx] = (title, new_thumb, new_h)

            self.logger.debug(f"  Scroll {scroll_i}: {new_count} new, total {len(all_items)}")

            if new_count == 0:
                no_new_count += 1
                if no_new_count >= 2:
                    break
            else:
                no_new_count = 0

            if len(all_items) >= max_items:
                break

            if scroll_i < max_scrolls:
                self._swipe_up()

        # 순위 할당 (수집 순서 = 순위)
        rankings = []
        for rank, (title, thumb_b64, _) in enumerate(all_items[:max_items], 1):
            rankings.append({
                'rank': rank,
                'title': title,
                'genre': '',
                'url': '',
                'thumbnail_url': thumb_b64,  # base64 data URL
            })

        return rankings

    def _restart_app(self):
        """앱 종료 후 재실행 + 팝업 닫기"""
        import time

        self.logger.info("📱 라인망가 앱 재시작...")
        self._run_adb(f'am force-stop {PACKAGE}')
        time.sleep(2)
        self._run_adb(
            f'monkey -p {PACKAGE} -c android.intent.category.LAUNCHER 1'
        )
        time.sleep(6)

        # 팝업 닫기 (최대 3번 시도)
        for popup_i in range(3):
            root = self._dump_ui()
            if root is None:
                return

            close_bounds = self._find_element_bounds(root, '閉じる')
            if close_bounds:
                self.logger.info(f"  팝업 닫기 ({popup_i + 1})...")
                dont_show = self._find_element_bounds(root, '次回から表示しない')
                if dont_show:
                    self._tap_center(dont_show)
                    time.sleep(0.5)
                self._tap_center(close_bounds)
                time.sleep(2)
            else:
                break

    def _enter_ranking_from_home(self) -> bool:
        """
        현재 홈 화면에서 "今日の人気ランキング" 을 찾아 탭 → 랭킹 페이지 진입.
        앱 재시작 없이 동작.
        """
        import time

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

        # 스크롤하며 "今日の人気ランキング" 찾아 탭
        for scroll_i in range(8):
            root = self._dump_ui()
            if root is None:
                return False

            ranking_bounds = self._find_element_bounds(root, '今日の人気ランキング')
            if ranking_bounds:
                self.logger.info("  '今日の人気ランキング' 발견 → 탭")
                self._tap_center(ranking_bounds)
                time.sleep(4)

                root = self._dump_ui()
                if root is None:
                    return False

                ranking_header = self._find_element_bounds(root, 'ランキング')
                if ranking_header:
                    self.logger.info("  ✅ 랭킹 페이지 도달")
                    return True

                self.logger.warning("  ⚠️ 랭킹 페이지 확인 실패, 재시도...")
                home_bounds = self._find_element_bounds(root, 'おすすめ')
                if home_bounds:
                    self._tap_center(home_bounds)
                    time.sleep(1)
                continue

            self._swipe_up()
            time.sleep(1)

        self.logger.error("❌ 랭킹 페이지를 찾을 수 없음")
        return False

    def _navigate_to_ranking_page(self) -> bool:
        """앱 재시작 후 랭킹 페이지 진입."""
        self._restart_app()
        return self._enter_ranking_from_home()

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

                import time

                # 2. 종합(기본) 랭킹 수집
                if not self._navigate_to_ranking_page():
                    raise Exception("Failed to navigate to ranking page")

                # 3. 성별 필터 × 장르 탭 크롤링
                all_rankings = None  # 종합 전체 (메인 데이터)

                for gender in GENDER_FILTERS:
                    gender_key = gender['key']
                    gender_name = gender['name']
                    gender_label = gender['label']

                    if gender_key:
                        # 여성/남성: 홈으로 돌아간 후 성별 전환 → 랭킹 재진입
                        self.logger.info(f"📱 [{gender_label}] 홈으로 복귀 → 필터 전환...")
                        self._run_adb('shell input keyevent KEYCODE_BACK')
                        time.sleep(2)

                        if not self._switch_gender_on_home(gender_name):
                            self.logger.warning(f"  ⚠️ [{gender_label}] 필터 전환 실패")
                            continue

                        # 성별 전환 후 앱 재시작 없이 랭킹 페이지 진입
                        if not self._enter_ranking_from_home():
                            self.logger.warning(f"  ⚠️ [{gender_label}] 랭킹 페이지 재진입 실패")
                            continue

                    # すべて 탭 크롤링
                    sub_key = gender_key  # '' or '女性' or '男性'
                    self.logger.info(f"📱 [{gender_label} 전체] 크롤링 중...")
                    if not self._navigate_to_tab('すべて'):
                        self.logger.warning(f"  ⚠️ [{gender_label} 전체] すべて 탭 이동 실패")
                        continue

                    time.sleep(2)
                    # 전체(すべて) 탭에서는 항상 썸네일 캡처
                    rankings = self._collect_tab_rankings(capture_thumbs=True)
                    self.genre_results[sub_key] = rankings
                    self.logger.info(f"  ✅ [{gender_label} 전체]: {len(rankings)}개 작품")

                    if gender_key == '':
                        all_rankings = rankings

                    # 장르별 탭 크롤링
                    for genre_info in GENRE_TABS[1:]:  # すべて 스킵
                        tab_name = genre_info['tab_name']
                        label = genre_info['label']
                        genre_key_part = genre_info['key']

                        # 복합 키: "女性:恋愛" 형태
                        if gender_key:
                            compound_key = f"{gender_key}:{genre_key_part}"
                        else:
                            compound_key = genre_key_part

                        self.logger.info(f"📱 [{gender_label}·{label}] 크롤링 중...")

                        try:
                            if self._navigate_to_tab(tab_name):
                                time.sleep(2)
                                tab_rankings = self._collect_tab_rankings(capture_thumbs=True)
                                self.genre_results[compound_key] = tab_rankings
                                self.logger.info(f"  ✅ [{gender_label}·{label}]: {len(tab_rankings)}개")
                            else:
                                self.genre_results[compound_key] = []
                                self.logger.warning(f"  ⚠️ [{gender_label}·{label}] 탭 이동 실패")
                        except Exception as e:
                            self.logger.warning(f"  ⚠️ [{gender_label}·{label}] 실패: {e}")
                            self.genre_results[compound_key] = []

                # 4. 데이터 검증
                if all_rankings is None:
                    raise Exception("종합 전체 데이터 수집 실패")

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
        """성별 × 장르별 전체 랭킹 저장 + 썸네일"""
        from crawler.db import save_rankings, backup_to_json, save_works_metadata

        # 종합 전체 랭킹 저장 + JSON 백업
        save_rankings(date, self.platform_id, data, sub_category='')
        works_meta = [
            {'title': item['title'], 'thumbnail_url': '',
             'url': '', 'genre': item.get('genre', ''), 'rank': item.get('rank')}
            for item in data
        ]
        if works_meta:
            save_works_metadata(self.platform_id, works_meta, date=date, sub_category='')
        backup_to_json(date, self.platform_id, data)

        # 모든 탭(전체+장르)의 썸네일 base64 저장
        thumb_count = 0
        try:
            from crawler.db import save_thumbnail_base64
            # 종합 전체 + 모든 장르/성별 탭의 썸네일 저장
            all_thumb_sources = [data]  # 종합 전체
            for gk, rankings in self.genre_results.items():
                if gk != '' and rankings:  # '' = 종합 전체 (이미 data에 포함)
                    all_thumb_sources.append(rankings)

            saved_titles = set()
            for source in all_thumb_sources:
                for item in source:
                    thumb = item.get('thumbnail_url', '')
                    title = item.get('title', '')
                    if thumb and thumb.startswith('data:image') and title not in saved_titles:
                        save_thumbnail_base64(self.platform_id, title, thumb)
                        saved_titles.add(title)
                        thumb_count += 1
        except Exception as e:
            self.logger.warning(f"  ⚠️ 썸네일 저장 실패: {e}")
        if thumb_count:
            self.logger.info(f"   🖼️ 썸네일 {thumb_count}개 저장")

        # 나머지 모든 장르/성별 조합 저장
        for sub_key, rankings in self.genre_results.items():
            if sub_key == '' or not rankings:
                continue  # 종합 전체는 이미 저장

            # 라벨 생성
            if ':' in sub_key:
                parts = sub_key.split(':', 1)
                label = f"{parts[0]}/{parts[1]}"
            else:
                label = sub_key

            save_rankings(date, self.platform_id, rankings, sub_category=sub_key)
            meta = [
                {'title': item['title'], 'thumbnail_url': '',
                 'url': '', 'genre': item.get('genre', ''), 'rank': item.get('rank')}
                for item in rankings
            ]
            if meta:
                save_works_metadata(self.platform_id, meta, date=date, sub_category=sub_key)
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
