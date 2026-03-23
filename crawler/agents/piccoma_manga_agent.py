"""
픽코마 MANGA (만화) 크롤러 에이전트

PiccomaAgent(SMARTOON)를 상속하여 MANGA 랭킹만 수집.
URL 경로만 /S/ → /K/로 변경, 나머지 로직은 동일.
"""

from crawler.agents.piccoma_agent import PiccomaAgent


class PiccomaMangaAgent(PiccomaAgent):
    """픽코마 MANGA 종합 + 장르별 랭킹 크롤러 에이전트"""

    GENRE_RANKINGS = {
        '': {'name': '총합', 'path': '/web/ranking/K/P/0'},
        'ファンタジー': {'name': '판타지', 'path': '/web/ranking/K/P/2'},
        '恋愛': {'name': '연애', 'path': '/web/ranking/K/P/1'},
        'アクション': {'name': '액션', 'path': '/web/ranking/K/P/5'},
        'ドラマ': {'name': '드라마', 'path': '/web/ranking/K/P/3'},
        'ホラー・ミステリー': {'name': '호러/미스터리', 'path': '/web/ranking/K/P/7'},
        '裏社会・アングラ': {'name': '뒷세계/언더그라운드', 'path': '/web/ranking/K/P/9'},
        'スポーツ': {'name': '스포츠', 'path': '/web/ranking/K/P/6'},
        'グルメ': {'name': '요리', 'path': '/web/ranking/K/P/10'},
        '日常': {'name': '일상', 'path': '/web/ranking/K/P/4'},
        'TL': {'name': 'TL', 'path': '/web/ranking/K/P/13'},
        'BL': {'name': 'BL', 'path': '/web/ranking/K/P/14'},
    }

    def __init__(self):
        # PiccomaAgent.__init__을 우회하고 CrawlerAgent.__init__을 직접 호출
        from crawler.agents.base_agent import CrawlerAgent
        CrawlerAgent.__init__(
            self,
            platform_id='piccoma_manga',
            platform_name='픽코마 (MANGA)',
            url='https://piccoma.com/web/ranking/K/P/0'
        )
        self.genre_results = {}
