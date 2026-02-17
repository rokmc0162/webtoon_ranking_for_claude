"""
주간 리뷰/코멘트 수집 엔트리포인트
- 매주 월요일 01:00 JST (cron)
- 최근 7일 랭킹 등장 작품 대상
- 3개 플랫폼 동시 실행 (라인망가, 메챠코믹, 코믹시모아)
- 픽코마 제외 (하트수는 detail_scraper에서 수집)
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.db import init_db
from crawler.review_crawler import run_review_crawler


def main():
    """리뷰 수집 메인"""
    try:
        init_db()
        print("\n📝 주간 리뷰/코멘트 수집 시작 (3개 플랫폼 동시 실행)\n")
        asyncio.run(run_review_crawler(max_works=0, concurrency=1))
        print("\n✅ 리뷰 수집 완료")
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 중단했습니다")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ 리뷰 수집 중 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
