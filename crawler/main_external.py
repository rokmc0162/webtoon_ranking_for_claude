"""
외부 데이터 수집 진입점
Usage:
    python crawler/main_external.py              # 기본 (anilist + mal + youtube)
    python crawler/main_external.py --anilist    # AniList만
    python crawler/main_external.py --mal        # Jikan/MAL만
    python crawler/main_external.py --youtube    # YouTube만
    python crawler/main_external.py --trends     # Google Trends만
    python crawler/main_external.py --reddit     # Reddit만
    python crawler/main_external.py --bookwalker # BookWalker만
    python crawler/main_external.py --pixiv      # Pixiv만
    python crawler/main_external.py --amazon     # Amazon JP만
    python crawler/main_external.py --twitter    # Twitter/X만
    python crawler/main_external.py --all        # 전체 9개 소스
    python crawler/main_external.py --max-works 10  # 최대 10개 작품
"""
import asyncio
import argparse
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.db import init_db
from crawler.sns.external_db import get_works_for_external

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('crawler.external')

ALL_SOURCES = [
    'anilist', 'mal', 'youtube',
    'trends', 'reddit', 'bookwalker',
    'pixiv', 'amazon', 'twitter',
]

DEFAULT_SOURCES = ['anilist', 'mal', 'youtube']


async def run_collectors(sources: list, max_works: int = 200):
    works = get_works_for_external(max_works)
    if not works:
        logger.info("수집 대상 작품 없음")
        return

    logger.info(f"외부 데이터 수집 대상: {len(works)}개 작품")

    for source in sources:
        try:
            if source == 'anilist':
                from crawler.sns.anilist_collector import AnilistCollector
                collector = AnilistCollector()
                await collector.collect_all(works)

            elif source == 'mal':
                from crawler.sns.jikan_collector import JikanCollector
                collector = JikanCollector()
                await collector.collect_all(works)

            elif source == 'youtube':
                from crawler.sns.youtube_collector import YoutubeCollector
                collector = YoutubeCollector(max_titles=80)
                await collector.collect_all(works)

            elif source == 'trends':
                from crawler.sns.trends_collector import TrendsCollector
                collector = TrendsCollector()
                await collector.collect_all(works)

            elif source == 'reddit':
                from crawler.sns.reddit_collector import RedditCollector
                collector = RedditCollector()
                await collector.collect_all(works)

            elif source == 'bookwalker':
                from crawler.sns.bookwalker_collector import BookWalkerCollector
                collector = BookWalkerCollector()
                await collector.collect_all(works)

            elif source == 'pixiv':
                from crawler.sns.pixiv_collector import PixivCollector
                collector = PixivCollector()
                await collector.collect_all(works)

            elif source == 'amazon':
                from crawler.sns.amazon_collector import AmazonCollector
                collector = AmazonCollector()
                await collector.collect_all(works)

            elif source == 'twitter':
                from crawler.sns.twitter_collector import TwitterCollector
                collector = TwitterCollector()
                await collector.collect_all(works)

        except ImportError as e:
            logger.warning(f"[{source}] 의존성 누락: {e}")
        except Exception as e:
            logger.error(f"[{source}] 수집 실패: {e}")


def main():
    parser = argparse.ArgumentParser(description='외부 데이터 수집기')
    parser.add_argument('--anilist', action='store_true', help='AniList')
    parser.add_argument('--mal', action='store_true', help='Jikan/MAL')
    parser.add_argument('--youtube', action='store_true', help='YouTube')
    parser.add_argument('--trends', action='store_true', help='Google Trends')
    parser.add_argument('--reddit', action='store_true', help='Reddit')
    parser.add_argument('--bookwalker', action='store_true', help='BookWalker')
    parser.add_argument('--pixiv', action='store_true', help='Pixiv')
    parser.add_argument('--amazon', action='store_true', help='Amazon JP')
    parser.add_argument('--twitter', action='store_true', help='Twitter/X')
    parser.add_argument('--all', action='store_true', help='전체 9개 소스')
    parser.add_argument('--max-works', type=int, default=200, help='최대 작품 수')
    args = parser.parse_args()

    try:
        init_db()

        if args.all:
            sources = ALL_SOURCES[:]
        else:
            sources = []
            for s in ALL_SOURCES:
                if getattr(args, s, False):
                    sources.append(s)

        if not sources:
            sources = DEFAULT_SOURCES[:]

        print(f"\n🌐 외부 데이터 수집 시작: {', '.join(sources)}\n")
        asyncio.run(run_collectors(sources, args.max_works))
        print("\n✅ 외부 데이터 수집 완료")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 중단했습니다")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 외부 데이터 수집 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
