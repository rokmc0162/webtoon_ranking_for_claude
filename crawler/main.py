"""
메인 크롤러 - 11개 플랫폼 병렬 실행 (Agent 기반)

실행 방법:
    python3 crawler/main.py

플랫폼:
- 기존: 픽코마, 라인망가, 메챠코믹, 코믹시모아(어덜트 포함)
- 신규: 코미코, 렌타, 북라이브, 이북재팬, 레진, 벨툰, U-NEXT

변경사항:
- 순차 실행 → 병렬 실행 (asyncio.gather)
- 각 플랫폼이 독립 에이전트로 실행
- 재시도 로직 내장 (exponential backoff)
- 100위까지 수집 (기존 50위)
"""

import asyncio
from pathlib import Path
import sys

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawler.orchestrator import CrawlerOrchestrator
from crawler.db import init_db
from crawler.verify import verify
from crawler.utils import fill_missing_title_kr


def main():
    """메인 함수"""
    try:
        # DB 연결 확인
        init_db()

        # Orchestrator를 통해 병렬 크롤링 실행
        orchestrator = CrawlerOrchestrator()
        results = asyncio.run(orchestrator.run_all())

        # 성공 여부에 따라 종료 코드 반환
        success_count = sum(1 for r in results.values() if r.success)

        # 크롤링 후 자동 검증
        if success_count > 0:
            print("\n")
            verify()

            # 상세 페이지 메타데이터 스크래핑 (50개, 순차)
            try:
                from crawler.detail_scraper import run_detail_scraper
                print("\n📋 상세 페이지 메타데이터 수집 시작...")
                asyncio.run(run_detail_scraper(max_works=50))
            except Exception as e:
                print(f"⚠️  상세 스크래핑 중 오류 (무시): {e}")

            # title_kr 누락 작품 자동 번역
            try:
                print("\n🔤 title_kr 누락 작품 자동 번역...")
                fill_missing_title_kr()
            except Exception as e:
                print(f"⚠️  자동 번역 중 오류 (무시): {e}")

        total = len(results)
        if success_count == 0:
            print("⚠️  모든 플랫폼 크롤링 실패")
            sys.exit(1)
        elif success_count < total:
            print(f"⚠️  일부 플랫폼 크롤링 실패 ({success_count}/{total})")
            sys.exit(0)  # 일부 성공은 정상 종료
        else:
            print(f"🎉 모든 플랫폼 크롤링 성공! ({total}개)")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  사용자가 중단했습니다")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ 크롤링 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
