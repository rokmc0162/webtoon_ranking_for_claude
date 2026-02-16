"""
일본 웹툰 랭킹 대시보드

실행:
    streamlit run dashboard/app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import base64
import urllib.request
import urllib.parse
import ssl
import html as html_module
import json

# 프로젝트 루트
project_root = Path(__file__).parent.parent

# 페이지 설정
st.set_page_config(
    page_title="일본 웹툰 랭킹",
    page_icon=str(project_root / 'docs' / 'riverse_logo.png'),
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =============================================================================
# 플랫폼 정보
# =============================================================================

PLATFORMS = {
    'piccoma': {
        'name': '픽코마',
        'color': '#FF6B6B',
        'logo': 'docs/픽코마.webp',
    },
    'linemanga': {
        'name': '라인망가',
        'color': '#06C755',
        'logo': 'docs/라인망가.png',
    },
    'mechacomic': {
        'name': '메챠코믹',
        'color': '#4A90D9',
        'logo': 'docs/메챠코믹.png',
    },
    'cmoa': {
        'name': '코믹시모아',
        'color': '#F5A623',
        'logo': 'docs/시모아.jpg',
    },
}


def _load_logo_base64(rel_path: str) -> str:
    """로고 이미지를 base64 data URI로 변환"""
    path = project_root / rel_path
    if not path.exists():
        return ''
    data = path.read_bytes()
    suffix = path.suffix.lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}
    mime = mime_map.get(suffix, 'image/png')
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime};base64,{b64}"


# 로고 base64 캐싱 (앱 시작 시 1회)
PLATFORM_LOGOS = {pid: _load_logo_base64(info['logo']) for pid, info in PLATFORMS.items()}
RIVERSE_LOGO = _load_logo_base64('docs/riverse_logo.png')

# =============================================================================
# 커스텀 CSS
# =============================================================================

st.markdown("""
<style>
/* ===== 레이아웃: 상단 공백 최소화 ===== */
.main .block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 1rem !important;
    max-width: 1200px;
}
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stDecoration"] { display: none; }
#MainMenu { display: none; }
footer { display: none; }
/* Streamlit 기본 상단 여백 제거 */
.stApp > header { display: none !important; }
.stApp [data-testid="stAppViewContainer"] { padding-top: 0 !important; }

/* ===== 플랫폼 카드: 투명 버튼을 카드 위로 겹치기 ===== */
[data-testid="stVerticalBlock"]:has(.pcard-logo) [data-testid="stElementContainer"]:has([data-testid="stButton"]) {
    margin-top: -100px !important;
    position: relative;
    z-index: 5;
}
[data-testid="stVerticalBlock"]:has(.pcard-logo) [data-testid="stButton"] button {
    opacity: 0 !important;
    min-height: 98px !important;
    cursor: pointer !important;
}

/* ===== 반응형: 모바일 최적화 ===== */
@media (max-width: 768px) {
    .main .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DB 헬퍼
# =============================================================================

def get_db_connection():
    db_path = project_root / 'data' / 'rankings.db'
    return sqlite3.connect(str(db_path))


def get_available_dates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT date FROM rankings ORDER BY date DESC')
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates


def load_rankings(date: str, platform: str) -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query('''
        SELECT rank, title, title_kr, genre, genre_kr, url, is_riverse
        FROM rankings
        WHERE date = ? AND platform = ?
        ORDER BY rank
    ''', conn, params=(date, platform))
    conn.close()

    rank_changes = calculate_rank_changes(date, platform)
    df['rank_change'] = df['title'].map(rank_changes).fillna(0).astype(int)
    return df


def calculate_rank_changes(date: str, platform: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT date FROM rankings
        WHERE date < ? AND platform = ?
        ORDER BY date DESC LIMIT 1
    ''', (date, platform))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return {}
    prev_date = result[0]
    current = pd.read_sql_query(
        'SELECT title, rank FROM rankings WHERE date = ? AND platform = ?',
        conn, params=(date, platform))
    previous = pd.read_sql_query(
        'SELECT title, rank FROM rankings WHERE date = ? AND platform = ?',
        conn, params=(prev_date, platform))
    conn.close()
    current_ranks = dict(zip(current['title'], current['rank']))
    previous_ranks = dict(zip(previous['title'], previous['rank']))
    changes = {}
    for title, curr_rank in current_ranks.items():
        if title in previous_ranks:
            changes[title] = previous_ranks[title] - curr_rank
        else:
            changes[title] = 999
    return changes


def get_rank_history(title: str, platform: str, days: int = 30) -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query('''
        SELECT date, rank FROM rankings
        WHERE title = ? AND platform = ?
        ORDER BY date DESC LIMIT ?
    ''', conn, params=(title, platform, days))
    conn.close()
    return df.sort_values('date')


def get_platform_stats(date: str) -> dict:
    conn = get_db_connection()
    stats = {}
    for pid in PLATFORMS:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM rankings WHERE date=? AND platform=?', (date, pid))
        total = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM rankings WHERE date=? AND platform=? AND is_riverse=1', (date, pid))
        riverse = cursor.fetchone()[0]
        stats[pid] = {'total': total, 'riverse': riverse}
    conn.close()
    return stats


# =============================================================================
# 썸네일 Base64 캐싱
# =============================================================================

def _detect_image_type(data: bytes) -> str:
    """magic bytes로 이미지 타입 감지"""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:2] == b'\xff\xd8':
        return 'image/jpeg'
    if data[:4] == b'GIF8':
        return 'image/gif'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return 'image/jpeg'  # fallback


def _download_and_encode(url: str) -> str:
    """URL에서 이미지 다운로드 → base64 data URI 반환"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'image/*,*/*',
    })
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        data = resp.read()

    mime = _detect_image_type(data)
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime};base64,{b64}"


@st.cache_data(ttl=3600, show_spinner=False)
def ensure_thumbnails_cached(platform: str) -> dict:
    """
    서버사이드에서 썸네일 다운로드 → base64 인코딩 → DB 캐싱
    반환: {title: "data:image/...;base64,..."}
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 이미 base64가 있는 것 로드
    cursor.execute('''
        SELECT title, thumbnail_base64
        FROM works
        WHERE platform = ? AND thumbnail_base64 IS NOT NULL AND thumbnail_base64 != ''
    ''', (platform,))
    cached = {row[0]: row[1] for row in cursor.fetchall()}

    # base64가 없지만 URL이 있는 것
    cursor.execute('''
        SELECT title, thumbnail_url
        FROM works
        WHERE platform = ?
          AND thumbnail_url IS NOT NULL AND thumbnail_url != ''
          AND (thumbnail_base64 IS NULL OR thumbnail_base64 = '')
    ''', (platform,))
    need_download = cursor.fetchall()
    conn.close()

    for title, url in need_download:
        try:
            data_uri = _download_and_encode(url)
            # DB에 저장
            conn2 = get_db_connection()
            cur2 = conn2.cursor()
            cur2.execute('''
                UPDATE works SET thumbnail_base64 = ?, updated_at = CURRENT_TIMESTAMP
                WHERE platform = ? AND title = ?
            ''', (data_uri, platform, title))
            conn2.commit()
            conn2.close()
            cached[title] = data_uri
        except Exception:
            pass  # 실패한 경우 썸네일 없이 표시

    return cached


# =============================================================================
# 배치 히스토리 로드
# =============================================================================

def get_rank_histories_batch(titles: list, platform: str, days: int = 30) -> dict:
    """여러 작품의 순위 히스토리를 한 번에 로드"""
    conn = get_db_connection()
    histories = {}
    for title in titles:
        df = pd.read_sql_query('''
            SELECT date, rank FROM rankings
            WHERE title = ? AND platform = ?
            ORDER BY date DESC LIMIT ?
        ''', conn, params=(title, platform, days))
        if not df.empty:
            df = df.sort_values('date')
            histories[title] = [
                {'date': row['date'], 'rank': int(row['rank'])}
                for _, row in df.iterrows()
            ]
    conn.close()
    return histories


# =============================================================================
# HTML 테이블 빌더
# =============================================================================

def build_ranking_html(df: pd.DataFrame, platform: str, thumbnails: dict,
                       platform_color: str, histories: dict,
                       title_kr_map: dict) -> str:
    """랭킹 HTML 테이블 생성 (Chart.js 모달 팝업 포함)"""

    rows_html = ""
    for _, row in df.iterrows():
        rank = int(row['rank'])
        change = int(row.get('rank_change', 0))
        title = str(row['title'])
        title_kr = str(row.get('title_kr', '') or '')
        genre = str(row.get('genre_kr', '') or row.get('genre', '') or '')
        url = str(row.get('url', '') or '')
        is_riverse = bool(row.get('is_riverse', 0))

        # 순위 스타일
        if rank <= 3:
            rank_badge = f'<span class="rank-top3">{rank}</span>'
        elif rank <= 10:
            rank_badge = f'<span class="rank-top10">{rank}</span>'
        else:
            rank_badge = f'<span class="rank-normal">{rank}</span>'

        # 썸네일
        thumb_data = thumbnails.get(title, '')
        if thumb_data:
            thumb_html = f'<img src="{thumb_data}" class="thumb" alt="">'
        else:
            thumb_html = '<div class="thumb-empty">📖</div>'

        # 변동
        if change == 999:
            change_html = '<span class="change-new">NEW</span>'
        elif change > 0:
            change_html = f'<span class="change-up">▲{change}</span>'
        elif change < 0:
            change_html = f'<span class="change-down">▼{abs(change)}</span>'
        else:
            change_html = '<span class="change-same">—</span>'

        # 작품명 (링크 + 리버스 마크)
        title_escaped = html_module.escape(title)
        riverse_mark = f' <img src="{RIVERSE_LOGO}" class="riverse-badge">' if is_riverse else ''
        if url:
            title_html = f'<a href="{html_module.escape(url)}" target="_blank" class="title-link">{title_escaped}</a>{riverse_mark}'
        else:
            title_html = f'{title_escaped}{riverse_mark}'

        # 한국어
        kr_escaped = html_module.escape(title_kr) if title_kr else ''

        # 장르
        genre_escaped = html_module.escape(genre)
        genre_html = f'<span class="genre-tag">{genre_escaped}</span>' if genre else ''

        # 추이 (모달 팝업) - data-title 속성 사용 (onclick 따옴표 충돌 방지)
        title_attr = html_module.escape(title)
        chart_html = f'<a href="#" data-title="{title_attr}" class="chart-btn">📈</a>'

        rows_html += f'''
        <tr>
            <td class="col-rank">{rank_badge}</td>
            <td class="col-thumb">{thumb_html}</td>
            <td class="col-change">{change_html}</td>
            <td class="col-title">{title_html}</td>
            <td class="col-kr">{kr_escaped}</td>
            <td class="col-genre">{genre_html}</td>
            <td class="col-chart">{chart_html}</td>
        </tr>'''

    # 히스토리 데이터를 JSON으로 임베딩
    histories_json = json.dumps(histories, ensure_ascii=False)
    title_kr_json = json.dumps(title_kr_map, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: white; }}

table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
}}
thead th {{
    position: sticky;
    top: 0;
    background: #F8F9FA;
    padding: 12px 10px;
    text-align: left;
    font-weight: 600;
    color: #374151;
    border-bottom: 2px solid #E5E7EB;
    font-size: 14px;
    white-space: nowrap;
    z-index: 10;
}}
tbody tr {{
    border-bottom: 1px solid #F3F4F6;
    transition: background 0.15s;
}}
tbody tr:hover {{
    background: #F9FAFB;
}}
td {{
    padding: 10px;
    vertical-align: middle;
}}

.col-rank {{ width: 50px; text-align: center; }}
.rank-top3 {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 50%;
    background: {platform_color}; color: white;
    font-weight: 700; font-size: 15px;
}}
.rank-top10 {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 32px; height: 32px; border-radius: 50%;
    background: #E5E7EB; color: #374151;
    font-weight: 600; font-size: 15px;
}}
.rank-normal {{ color: #6B7280; font-weight: 500; }}

.col-thumb {{ width: 56px; text-align: center; }}
.thumb {{
    width: 44px; height: 62px; object-fit: cover;
    border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.thumb-empty {{
    width: 44px; height: 62px; display: flex;
    align-items: center; justify-content: center;
    background: #F3F4F6; border-radius: 4px;
    font-size: 20px;
}}

.col-change {{ width: 64px; text-align: center; }}
.change-up {{ color: #EF4444; font-weight: 600; font-size: 14px; }}
.change-down {{ color: #3B82F6; font-weight: 600; font-size: 14px; }}
.change-new {{
    background: #FEF3C7; color: #D97706; padding: 2px 8px;
    border-radius: 10px; font-size: 12px; font-weight: 700;
}}
.change-same {{ color: #9CA3AF; }}

.col-title {{ min-width: 200px; }}
.title-link {{
    color: #1F2937; text-decoration: none; font-weight: 500;
    font-size: 15px;
}}
.title-link:hover {{
    color: {platform_color}; text-decoration: underline;
}}
.riverse-badge {{
    height: 14px; width: auto; vertical-align: middle;
    margin-left: 4px; opacity: 0.85;
}}

.col-kr {{ color: #6B7280; font-size: 14px; min-width: 120px; }}

.col-genre {{ width: 90px; }}
.genre-tag {{
    background: #F3F4F6; color: #4B5563; padding: 3px 10px;
    border-radius: 10px; font-size: 13px; white-space: nowrap;
}}

.col-chart {{ width: 48px; text-align: center; }}
.chart-btn {{
    text-decoration: none; font-size: 22px;
    cursor: pointer; opacity: 0.7;
    transition: opacity 0.15s;
}}
.chart-btn:hover {{ opacity: 1.0; }}

/* ===== 모바일 반응형 ===== */
@media (max-width: 768px) {{
    table {{ font-size: 14px; }}
    thead th {{ padding: 10px 6px; font-size: 13px; }}
    td {{ padding: 8px 6px; }}
    .col-kr, .col-genre {{ display: none; }}
    .col-title {{ min-width: 120px; }}
    .title-link {{ font-size: 14px; }}
    .thumb {{ width: 36px; height: 50px; }}
    .thumb-empty {{ width: 36px; height: 50px; }}
}}

/* 모달 */
.modal-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 1000;
    justify-content: center;
    align-items: center;
}}
.modal-overlay.active {{
    display: flex;
}}
.modal-content {{
    background: white;
    border-radius: 16px;
    padding: 24px;
    width: 90%;
    max-width: 680px;
    max-height: 85vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    position: relative;
}}
.modal-close {{
    position: absolute;
    top: 12px; right: 16px;
    font-size: 24px;
    cursor: pointer;
    color: #9CA3AF;
    background: none;
    border: none;
    line-height: 1;
}}
.modal-close:hover {{ color: #374151; }}
.modal-title {{
    font-size: 18px;
    font-weight: 700;
    color: #1F2937;
    margin-bottom: 4px;
    padding-right: 30px;
}}
.modal-subtitle {{
    font-size: 14px;
    color: #6B7280;
    margin-bottom: 16px;
}}
.chart-container {{
    width: 100%;
    height: 280px;
    margin-bottom: 16px;
}}
.stats-row {{
    display: flex;
    gap: 12px;
}}
.stat-box {{
    flex: 1;
    text-align: center;
    padding: 10px 8px;
    background: #F9FAFB;
    border-radius: 10px;
}}
.stat-label {{
    font-size: 13px;
    color: #9CA3AF;
    margin-bottom: 2px;
}}
.stat-value {{
    font-size: 20px;
    font-weight: 700;
    color: #1F2937;
}}
.no-data {{
    text-align: center;
    color: #9CA3AF;
    padding: 40px 0;
    font-size: 15px;
}}
</style>
</head>
<body>

<table>
    <thead>
        <tr>
            <th>순위</th>
            <th></th>
            <th>변동</th>
            <th>작품명</th>
            <th>한국어</th>
            <th>장르</th>
            <th>추이</th>
        </tr>
    </thead>
    <tbody>
        {rows_html}
    </tbody>
</table>

<!-- 차트 모달 -->
<div class="modal-overlay" id="chartModal">
    <div class="modal-content">
        <button class="modal-close" onclick="closeModal()">&times;</button>
        <div class="modal-title" id="modalTitle"></div>
        <div class="modal-subtitle" id="modalSubtitle"></div>
        <div class="chart-container">
            <canvas id="rankChart"></canvas>
        </div>
        <div class="stats-row" id="statsRow"></div>
        <div class="no-data" id="noData" style="display:none;">히스토리 데이터가 없습니다.</div>
    </div>
</div>

<script>
var HISTORIES = {histories_json};
var TITLE_KR = {title_kr_json};
var COLOR = '{platform_color}';

function drawChart(canvas, ranks, labels) {{
    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    var w = canvas.parentElement.clientWidth;
    var h = 260;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.scale(dpr, dpr);

    var pad = {{ top: 20, right: 20, bottom: 40, left: 45 }};
    var cw = w - pad.left - pad.right;
    var ch = h - pad.top - pad.bottom;

    // Y축 범위 (순위: 낮을수록 좋으므로 reverse)
    var minR = Math.min.apply(null, ranks);
    var maxR = Math.max.apply(null, ranks);
    if (minR === maxR) {{ minR = Math.max(1, minR - 3); maxR = maxR + 3; }}
    var yMin = Math.max(1, minR - 2);
    var yMax = maxR + 2;

    // 배경
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, w, h);

    // 그리드
    ctx.strokeStyle = '#F3F4F6';
    ctx.lineWidth = 1;
    var ySteps = [];
    for (var y = Math.ceil(yMin); y <= Math.floor(yMax); y += Math.max(1, Math.floor((yMax - yMin) / 5))) {{
        ySteps.push(y);
    }}
    if (ySteps.indexOf(Math.floor(yMax)) === -1) ySteps.push(Math.floor(yMax));

    ySteps.forEach(function(v) {{
        var py = pad.top + ch - ((v - yMin) / (yMax - yMin)) * ch;
        // 순위는 reverse이므로 반전
        py = pad.top + ((v - yMin) / (yMax - yMin)) * ch;
        ctx.beginPath();
        ctx.moveTo(pad.left, py);
        ctx.lineTo(pad.left + cw, py);
        ctx.stroke();
        // Y축 레이블
        ctx.fillStyle = '#9CA3AF';
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(v + '위', pad.left - 6, py + 4);
    }});

    // X축 레이블
    ctx.fillStyle = '#9CA3AF';
    ctx.font = '10px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    labels.forEach(function(lbl, i) {{
        var px = pad.left + (ranks.length === 1 ? cw / 2 : (i / (ranks.length - 1)) * cw);
        // 짧게 표시 (MM-DD)
        var short = lbl.substring(5);
        ctx.fillText(short, px, h - pad.bottom + 20);
    }});

    // 라인 + 영역
    if (ranks.length >= 2) {{
        // 영역 채우기
        ctx.beginPath();
        ranks.forEach(function(r, i) {{
            var px = pad.left + (i / (ranks.length - 1)) * cw;
            var py = pad.top + ((r - yMin) / (yMax - yMin)) * ch;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }});
        ctx.lineTo(pad.left + cw, pad.top + ch);
        ctx.lineTo(pad.left, pad.top + ch);
        ctx.closePath();
        ctx.fillStyle = COLOR + '15';
        ctx.fill();

        // 라인
        ctx.beginPath();
        ranks.forEach(function(r, i) {{
            var px = pad.left + (i / (ranks.length - 1)) * cw;
            var py = pad.top + ((r - yMin) / (yMax - yMin)) * ch;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }});
        ctx.strokeStyle = COLOR;
        ctx.lineWidth = 2.5;
        ctx.lineJoin = 'round';
        ctx.stroke();
    }}

    // 포인트
    ranks.forEach(function(r, i) {{
        var px = pad.left + (ranks.length === 1 ? cw / 2 : (i / (ranks.length - 1)) * cw);
        var py = pad.top + ((r - yMin) / (yMax - yMin)) * ch;
        ctx.beginPath();
        ctx.arc(px, py, 5, 0, Math.PI * 2);
        ctx.fillStyle = COLOR;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
        // 순위 텍스트
        ctx.fillStyle = '#374151';
        ctx.font = 'bold 11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(r + '위', px, py - 10);
    }});
}}

function showChart(title) {{
    var modal = document.getElementById('chartModal');
    var titleEl = document.getElementById('modalTitle');
    var subtitleEl = document.getElementById('modalSubtitle');
    var statsRow = document.getElementById('statsRow');
    var noData = document.getElementById('noData');
    var chartContainer = document.querySelector('.chart-container');

    var kr = TITLE_KR[title] || '';
    titleEl.textContent = '📈 ' + title;
    subtitleEl.textContent = kr ? kr : '';

    var data = HISTORIES[title];

    if (!data || data.length === 0) {{
        chartContainer.style.display = 'none';
        statsRow.style.display = 'none';
        noData.style.display = 'block';
    }} else {{
        chartContainer.style.display = 'block';
        statsRow.style.display = 'flex';
        noData.style.display = 'none';

        var labels = data.map(function(d) {{ return d.date; }});
        var ranks = data.map(function(d) {{ return d.rank; }});

        modal.classList.add('active');

        // 모달이 표시된 후 차트 렌더링 (크기 계산 위해)
        setTimeout(function() {{
            var canvas = document.getElementById('rankChart');
            drawChart(canvas, ranks, labels);
        }}, 50);

        // 통계
        var minR = Math.min.apply(null, ranks);
        var maxR = Math.max.apply(null, ranks);
        var avgR = (ranks.reduce(function(a,b){{ return a+b; }}, 0) / ranks.length).toFixed(1);
        statsRow.innerHTML =
            '<div class="stat-box"><div class="stat-label">최고 순위</div><div class="stat-value">' + minR + '위</div></div>' +
            '<div class="stat-box"><div class="stat-label">최저 순위</div><div class="stat-value">' + maxR + '위</div></div>' +
            '<div class="stat-box"><div class="stat-label">평균 순위</div><div class="stat-value">' + avgR + '위</div></div>' +
            '<div class="stat-box"><div class="stat-label">데이터</div><div class="stat-value">' + data.length + '일</div></div>';
        return;
    }}

    modal.classList.add('active');
}}

function closeModal() {{
    document.getElementById('chartModal').classList.remove('active');
}}

// 차트 버튼 이벤트 바인딩 (data-title 속성 사용)
document.querySelectorAll('.chart-btn').forEach(function(btn) {{
    btn.addEventListener('click', function(e) {{
        e.preventDefault();
        var title = this.getAttribute('data-title');
        showChart(title);
    }});
}});

// 오버레이 클릭으로 닫기
document.getElementById('chartModal').addEventListener('click', function(e) {{
    if (e.target === this) closeModal();
}});

// ESC 키로 닫기
document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') closeModal();
}});
</script>
</body>
</html>'''


# =============================================================================
# 메인 앱
# =============================================================================

def main():
    # 헤더
    st.markdown('''
    <div style="text-align:center; padding: 0 0 0.5rem 0;">
        <h2 style="font-size:1.3rem; font-weight:700; color:#1F2937; margin:0 0 0.1rem 0;">
            📊 일본 웹툰 플랫폼 랭킹
        </h2>
        <p style="color:#6B7280; font-size:0.8rem; margin:0;">RIVERSE Inc. — 4대 플랫폼 자동 수집 시스템</p>
    </div>
    ''', unsafe_allow_html=True)

    # 날짜 확인
    dates = get_available_dates()
    if not dates:
        st.error("랭킹 데이터가 없습니다. 크롤링을 먼저 실행해주세요.")
        st.code("python3 crawler/main.py", language="bash")
        st.stop()

    # 날짜 선택
    col_date, col_refresh, col_info = st.columns([3, 1, 2])
    with col_date:
        selected_date = st.selectbox(
            "날짜", dates,
            format_func=lambda x: f"{x} ({datetime.strptime(x, '%Y-%m-%d').strftime('%A')})",
            label_visibility="collapsed"
        )
    with col_refresh:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    with col_info:
        st.caption(f"📅 총 {len(dates)}일 데이터 수집됨")

    # 플랫폼 통계
    stats = get_platform_stats(selected_date)

    # 세션 스테이트
    if 'selected_platform' not in st.session_state:
        st.session_state.selected_platform = 'piccoma'

    # =========================================================================
    # 플랫폼 카드 (로고 이미지 + 플랫폼명 버튼 = 하나의 카드)
    # =========================================================================
    cols = st.columns(4, gap="small")
    for i, (pid, info) in enumerate(PLATFORMS.items()):
        with cols[i]:
            is_active = st.session_state.selected_platform == pid
            logo_src = PLATFORM_LOGOS.get(pid, '')
            rc = int(info['color'][1:3], 16)
            gc = int(info['color'][3:5], 16)
            bc = int(info['color'][5:7], 16)

            if is_active:
                border_css = f"3px solid {info['color']}"
                bg_css = f"rgba({rc},{gc},{bc},0.08)"
                shadow_css = f"0 4px 16px rgba({rc},{gc},{bc},0.25)"
            else:
                border_css = "2px solid #E5E7EB"
                bg_css = "white"
                shadow_css = "0 1px 3px rgba(0,0,0,0.05)"

            # 로고 이미지 (카드 — 시각적 요소, 클릭은 아래 투명 버튼이 담당)
            st.markdown(f'''
            <div class="pcard-logo" style="text-align:center; padding:14px 8px 8px; border-radius:16px;
                        border:{border_css}; background:{bg_css}; box-shadow:{shadow_css};
                        cursor:pointer;">
                <img src="{logo_src}" style="width:52px; height:52px; border-radius:12px; object-fit:cover;">
                <div style="font-size:0.9rem; font-weight:700; color:{'#1F2937' if not is_active else info['color']};
                            margin-top:6px;">{info['name']}</div>
            </div>
            ''', unsafe_allow_html=True)

            # 투명 버튼 (카드 위에 겹쳐서 클릭 영역 담당)
            if st.button(
                " ",
                key=f"btn_{pid}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state.selected_platform = pid
                st.rerun()

    # =========================================================================
    # 선택된 플랫폼 데이터
    # =========================================================================
    platform = st.session_state.selected_platform
    pinfo = PLATFORMS[platform]
    df = load_rankings(selected_date, platform)

    if df.empty:
        st.warning(f"{pinfo['name']} 데이터가 없습니다. 크롤링을 먼저 실행해주세요.")
        return

    # 필터 바
    col_title, col_filter = st.columns([3, 1])
    with col_title:
        st.markdown(f"**{pinfo['name']}** 랭킹 TOP {len(df)} — {selected_date}")
    with col_filter:
        show_riverse = st.checkbox("RIVERSE만", key="riverse_filter")

    if show_riverse:
        df = df[df['is_riverse'] == 1].reset_index(drop=True)
        if df.empty:
            st.info("리버스 작품이 아직 랭킹에 없습니다.")
            return

    # 썸네일 base64 로드 (서버사이드 캐싱)
    with st.spinner("썸네일 로딩 중..."):
        thumbnails = ensure_thumbnails_cached(platform)

    # 순위 히스토리 배치 로드 (차트 모달용)
    titles_list = df['title'].tolist()
    histories = get_rank_histories_batch(titles_list, platform)
    title_kr_map = dict(zip(df['title'], df['title_kr'].fillna('')))

    # HTML 테이블 렌더링
    table_html = build_ranking_html(df, platform, thumbnails, pinfo['color'],
                                     histories, title_kr_map)
    # 고정 뷰포트 높이 (iframe 내부 스크롤) — position:fixed 모달이 보이는 영역에 정확히 표시됨
    components.html(table_html, height=750, scrolling=True)

    # 푸터
    st.divider()
    st.caption("RIVERSE Inc. | 데이터: data/rankings.db | 매일 9:00 / 15:00 / 21:00 자동 수집")


if __name__ == "__main__":
    main()
