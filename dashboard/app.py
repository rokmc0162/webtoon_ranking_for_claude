"""
일본 웹툰 랭킹 대시보드

실행:
    streamlit run dashboard/app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트
project_root = Path(__file__).parent.parent

# 페이지 설정
st.set_page_config(
    page_title="일본 웹툰 랭킹",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =============================================================================
# DB 헬퍼 함수
# =============================================================================

def get_db_connection():
    """SQLite 연결"""
    db_path = project_root / 'data' / 'rankings.db'
    return sqlite3.connect(str(db_path))


def get_available_dates():
    """사용 가능한 날짜 목록 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT date FROM rankings ORDER BY date DESC')
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates


def load_rankings(date: str, platform: str) -> pd.DataFrame:
    """
    특정 날짜/플랫폼의 랭킹 조회

    Args:
        date: 날짜 (YYYY-MM-DD)
        platform: 플랫폼 ID (piccoma, linemanga, mechacomic, cmoa)

    Returns:
        DataFrame with columns: rank, title, title_kr, genre_kr, url, is_riverse, rank_change
    """
    conn = get_db_connection()

    # 현재 날짜 데이터
    df = pd.read_sql_query('''
        SELECT rank, title, title_kr, genre_kr, url, is_riverse
        FROM rankings
        WHERE date = ? AND platform = ?
        ORDER BY rank
    ''', conn, params=(date, platform))

    # 순위 변동 계산
    rank_changes = calculate_rank_changes(date, platform)
    df['rank_change'] = df['title'].map(rank_changes).fillna(0).astype(int)

    conn.close()
    return df


def calculate_rank_changes(date: str, platform: str) -> dict:
    """
    전날 대비 순위 변동 계산

    Returns:
        {title: change} where positive=상승, negative=하락, 999=NEW
    """
    conn = get_db_connection()

    # 전날 날짜 찾기
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT date
        FROM rankings
        WHERE date < ? AND platform = ?
        ORDER BY date DESC
        LIMIT 1
    ''', (date, platform))

    result = cursor.fetchone()
    if not result:
        conn.close()
        return {}

    prev_date = result[0]

    # 현재 랭킹
    current = pd.read_sql_query('''
        SELECT title, rank FROM rankings
        WHERE date = ? AND platform = ?
    ''', conn, params=(date, platform))

    # 전날 랭킹
    previous = pd.read_sql_query('''
        SELECT title, rank FROM rankings
        WHERE date = ? AND platform = ?
    ''', conn, params=(prev_date, platform))

    conn.close()

    # 딕셔너리 변환
    current_ranks = dict(zip(current['title'], current['rank']))
    previous_ranks = dict(zip(previous['title'], previous['rank']))

    changes = {}
    for title, curr_rank in current_ranks.items():
        if title in previous_ranks:
            prev_rank = previous_ranks[title]
            # 순위가 낮아지면 양수 (1위→10위 = +9)
            # 순위가 높아지면 음수 (10위→1위 = -9)
            changes[title] = prev_rank - curr_rank
        else:
            changes[title] = 999  # NEW

    return changes


def get_rank_history(title: str, platform: str, days: int = 30) -> pd.DataFrame:
    """
    특정 작품의 순위 히스토리 조회

    Args:
        title: 작품 제목 (일본어)
        platform: 플랫폼 ID
        days: 조회 기간 (일)

    Returns:
        DataFrame with columns: date, rank
    """
    conn = get_db_connection()

    df = pd.read_sql_query('''
        SELECT date, rank
        FROM rankings
        WHERE title = ? AND platform = ?
        ORDER BY date DESC
        LIMIT ?
    ''', conn, params=(title, platform, days))

    conn.close()

    # 날짜 오름차순 정렬 (그래프용)
    return df.sort_values('date')


# =============================================================================
# 포맷팅 헬퍼
# =============================================================================

def format_rank_change(change: int) -> str:
    """순위 변동 포맷팅"""
    if change == 999:
        return "🆕 NEW"
    elif change > 0:
        return f"⬆️ {change}"
    elif change < 0:
        return f"⬇️ {abs(change)}"
    else:
        return "➖"


def highlight_riverse(row):
    """리버스 작품 행 하이라이트"""
    if row['is_riverse'] == 1:
        return ['background-color: #FFF9C4'] * len(row)
    else:
        return [''] * len(row)


# =============================================================================
# UI 컴포넌트
# =============================================================================

def render_platform_tab(date: str, platform: str, platform_name: str):
    """
    플랫폼별 탭 렌더링

    Args:
        date: 선택된 날짜
        platform: 플랫폼 ID
        platform_name: 플랫폼 표시 이름
    """
    df = load_rankings(date, platform)

    if df.empty:
        st.warning(f"📭 {platform_name} 데이터가 없습니다. 크롤링을 먼저 실행해주세요.")
        st.code(f"python3 crawler/main.py", language="bash")
        return

    # KPI 메트릭
    col1, col2, col3 = st.columns(3)
    col1.metric("📚 전체 작품", f"{len(df)}개")
    col2.metric("⭐ 리버스 작품", f"{df['is_riverse'].sum()}개")

    # 순위 변동 통계
    up_count = (df['rank_change'] > 0).sum()
    down_count = (df['rank_change'] < 0).sum()
    new_count = (df['rank_change'] == 999).sum()
    col3.metric("📈 순위 상승", f"{up_count}개 ⬆️ / {down_count}개 ⬇️ / {new_count}개 🆕")

    st.divider()

    # 필터
    col1, col2 = st.columns([1, 3])
    with col1:
        show_riverse = st.checkbox("⭐ 리버스만 보기", key=f"{platform}_riverse_filter")

    # 필터 적용
    filtered_df = df[df['is_riverse'] == 1] if show_riverse else df

    # 랭킹 테이블 준비
    display_df = filtered_df.copy()

    # 제목 병합 (일본어 + 한국어)
    display_df['제목'] = display_df.apply(
        lambda row: f"{row['title']}\n({row['title_kr']})" if row['title_kr'] else row['title'],
        axis=1
    )

    # 순위 변동 포맷팅
    display_df['변동'] = display_df['rank_change'].apply(format_rank_change)

    # 표시 컬럼 선택
    table_df = display_df[['rank', '제목', 'genre_kr', '변동', 'url']].copy()
    table_df.columns = ['순위', '제목', '장르', '순위변동', '링크']

    # 테이블 표시
    st.dataframe(
        table_df,
        use_container_width=True,
        height=600,
        column_config={
            '순위': st.column_config.NumberColumn('순위', width='small'),
            '제목': st.column_config.TextColumn('제목', width='large'),
            '장르': st.column_config.TextColumn('장르', width='medium'),
            '순위변동': st.column_config.TextColumn('순위변동', width='small'),
            '링크': st.column_config.LinkColumn('🔗', width='small', display_text="보기")
        },
        hide_index=True
    )

    # 순위 변동 그래프 (핵심 기능!)
    st.divider()
    st.subheader("📈 작품별 순위 변동 추이 (일일 누적)")
    st.caption("매일 크롤링한 데이터를 계속 쌓아서, 특정 작품의 순위 변화를 시간에 따라 그래프로 확인할 수 있습니다.")

    # 작품 선택
    title_options = filtered_df['title'].tolist()
    selected_title = st.selectbox(
        "작품 선택",
        title_options,
        key=f"{platform}_title_select",
        format_func=lambda x: f"{x} ({filtered_df[filtered_df['title'] == x]['title_kr'].values[0]})"
                              if filtered_df[filtered_df['title'] == x]['title_kr'].values[0]
                              else x
    )

    if selected_title:
        history = get_rank_history(selected_title, platform, days=30)

        if len(history) >= 2:
            # 그래프 생성
            fig = px.line(
                history,
                x='date',
                y='rank',
                title=f"{selected_title} 최근 {len(history)}일 순위 변동",
                markers=True,
                line_shape='linear'
            )

            # Y축 반전 (1위가 위로)
            fig.update_yaxis(
                autorange="reversed",
                title="순위",
                dtick=5
            )

            fig.update_xaxis(title="날짜")

            fig.update_layout(
                hovermode='x unified',
                height=400,
                showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )

            # 그리드 스타일
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

            st.plotly_chart(fig, use_container_width=True)

            # 통계
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🏆 최고 순위", f"{history['rank'].min()}위")
            col2.metric("📉 최저 순위", f"{history['rank'].max()}위")
            col3.metric("📊 평균 순위", f"{history['rank'].mean():.1f}위")
            col4.metric("📅 데이터 수", f"{len(history)}일")

        elif len(history) == 1:
            st.info("📊 히스토리 데이터가 1일뿐입니다. 내일부터 그래프가 표시됩니다.")
        else:
            st.info("📊 히스토리 데이터가 없습니다. 매일 크롤링이 실행되면 자동으로 그래프가 생성됩니다.")


# =============================================================================
# 메인 앱
# =============================================================================

def main():
    """메인 앱"""

    # 타이틀
    st.title("📊 일본 웹툰 플랫폼 랭킹 대시보드")
    st.caption("RIVERSE Inc. - 4대 플랫폼 자동 수집 시스템")

    # 날짜 선택
    dates = get_available_dates()

    if not dates:
        st.error("❌ 랭킹 데이터가 없습니다. 크롤링을 먼저 실행해주세요.")
        st.code("python3 crawler/main.py", language="bash")
        st.stop()

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        selected_date = st.selectbox(
            "📅 날짜 선택",
            dates,
            format_func=lambda x: f"{x} ({datetime.strptime(x, '%Y-%m-%d').strftime('%A')})"
        )

    with col2:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()

    with col3:
        st.caption(f"총 {len(dates)}일 데이터")

    st.divider()

    # 플랫폼 탭
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔴 픽코마 (SMARTOON)",
        "🟢 라인망가 (웹 종합)",
        "🔵 메챠코믹 (판매)",
        "🟡 코믹시모아 (종합)"
    ])

    with tab1:
        render_platform_tab(selected_date, 'piccoma', '픽코마')

    with tab2:
        render_platform_tab(selected_date, 'linemanga', '라인망가')

    with tab3:
        render_platform_tab(selected_date, 'mechacomic', '메챠코믹')

    with tab4:
        render_platform_tab(selected_date, 'cmoa', '코믹시모아')

    # 푸터
    st.divider()
    st.caption("💾 데이터베이스: data/rankings.db | 📦 백업: data/backup/")


if __name__ == "__main__":
    main()
