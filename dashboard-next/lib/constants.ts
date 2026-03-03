import type { PlatformInfo } from "./types";

export const PLATFORMS: PlatformInfo[] = [
  {
    id: "piccoma",
    name: "픽코마",
    color: "#F5C518",
    logo: "/piccoma.png",
    sourceUrl: "https://piccoma.com/web/ranking/S/P/0",
    genres: [
      { key: "", label: "총합" },
      { key: "ファンタジー", label: "판타지" },
      { key: "恋愛", label: "연애" },
      { key: "アクション", label: "액션" },
      { key: "ドラマ", label: "드라마" },
      { key: "ホラー・ミステリー", label: "호러/미스터리" },
      { key: "裏社会・アングラ", label: "뒷세계" },
      { key: "スポーツ", label: "스포츠" },
      { key: "グルメ", label: "요리" },
      { key: "日常", label: "일상" },
      { key: "TL", label: "TL" },
      { key: "BL", label: "BL" },
    ],
  },
  {
    id: "linemanga",
    name: "라인망가",
    color: "#06C755",
    logo: "/linemanga.png",
    sourceUrl: "https://manga.line.me/periodic/gender_ranking?gender=0",
    genres: [
      { key: "", label: "총합" },
      { key: "バトル・アクション", label: "배틀/액션" },
      { key: "ファンタジー・SF", label: "판타지/SF" },
      { key: "恋愛", label: "연애" },
      { key: "スポーツ", label: "스포츠" },
      { key: "ミステリー・ホラー", label: "미스터리/호러" },
      { key: "裏社会・アングラ", label: "뒷세계" },
      { key: "ヒューマンドラマ", label: "휴먼드라마" },
      { key: "歴史・時代", label: "역사/시대" },
      { key: "コメディ・ギャグ", label: "코미디/개그" },
      { key: "その他", label: "기타" },
    ],
  },
  {
    id: "linemanga_app",
    name: "라인망가(앱)",
    color: "#00B900",
    logo: "/linemanga.png",
    sourceUrl: "",
    badge: "APP",
    genres: [
      // 종합
      { key: "", label: "전체" },
      { key: "恋愛", label: "연애" },
      { key: "ファンタジー・SF", label: "판타지/SF" },
      { key: "ミステリー・ホラー", label: "미스터리/호러" },
      { key: "ヒューマンドラマ", label: "휴먼드라마" },
      { key: "バトル・アクション", label: "배틀/액션" },
      { key: "裏社会・アングラ", label: "뒷세계" },
      { key: "コメディ・ギャグ", label: "코미디/개그" },
      { key: "スポーツ", label: "스포츠" },
      { key: "歴史・時代", label: "역사/시대" },
      // 여성
      { key: "女性", label: "여성" },
      { key: "女性:恋愛", label: "여성·연애" },
      { key: "女性:ファンタジー・SF", label: "여성·판타지" },
      { key: "女性:ミステリー・ホラー", label: "여성·미스터리" },
      { key: "女性:ヒューマンドラマ", label: "여성·휴먼" },
      { key: "女性:バトル・アクション", label: "여성·배틀" },
      { key: "女性:裏社会・アングラ", label: "여성·뒷세계" },
      { key: "女性:コメディ・ギャグ", label: "여성·코미디" },
      { key: "女性:スポーツ", label: "여성·스포츠" },
      { key: "女性:歴史・時代", label: "여성·역사" },
      // 남성
      { key: "男性", label: "남성" },
      { key: "男性:恋愛", label: "남성·연애" },
      { key: "男性:ファンタジー・SF", label: "남성·판타지" },
      { key: "男性:ミステリー・ホラー", label: "남성·미스터리" },
      { key: "男性:ヒューマンドラマ", label: "남성·휴먼" },
      { key: "男性:バトル・アクション", label: "남성·배틀" },
      { key: "男性:裏社会・アングラ", label: "남성·뒷세계" },
      { key: "男性:コメディ・ギャグ", label: "남성·코미디" },
      { key: "男性:スポーツ", label: "남성·스포츠" },
      { key: "男性:歴史・時代", label: "남성·역사" },
    ],
  },
  {
    id: "mechacomic",
    name: "메챠코믹",
    color: "#00B4D8",
    logo: "/mechacomic.png",
    sourceUrl: "https://mechacomic.jp/sales_rankings/current",
    genres: [
      { key: "", label: "종합" },
      { key: "少女", label: "소녀" },
      { key: "女性", label: "여성" },
      { key: "少年", label: "소년" },
      { key: "青年", label: "청년" },
      { key: "ハーレクイン", label: "할리퀸" },
      { key: "TL", label: "TL" },
      { key: "BL", label: "BL" },
      { key: "オトナ", label: "오토나(어덜트)" },
    ],
  },
  {
    id: "cmoa",
    name: "코믹시모아",
    color: "#FF6B00",
    logo: "/cmoa.jpg",
    sourceUrl: "https://www.cmoa.jp/search/purpose/ranking/all/",
    genres: [
      { key: "", label: "종합" },
      { key: "少年マンガ", label: "소년만화" },
      { key: "青年マンガ", label: "청년만화" },
      { key: "少女マンガ", label: "소녀만화" },
      { key: "女性マンガ", label: "여성만화" },
      { key: "BL", label: "BL" },
      { key: "TL", label: "TL" },
      { key: "sexy", label: "어덜트" },
    ],
  },
  {
    id: "comico",
    name: "코미코",
    color: "#FF4081",
    logo: "/comico.png",
    sourceUrl: "https://www.comico.jp/menu/all_comic/ranking",
    genres: [
      { key: "", label: "종합" },
      { key: "ファンタジー", label: "판타지" },
      { key: "恋愛", label: "연애" },
      { key: "BL", label: "BL" },
      { key: "ドラマ", label: "드라마" },
      { key: "日常", label: "일상" },
      { key: "TL", label: "TL" },
      { key: "アクション", label: "액션" },
      { key: "学園", label: "학원" },
      { key: "ミステリー", label: "미스터리" },
      { key: "ホラー", label: "호러" },
    ],
  },
  {
    id: "renta",
    name: "렌타",
    color: "#E91E63",
    logo: "/renta.png",
    sourceUrl: "https://renta.papy.co.jp/renta/sc/frm/page/ranking_c.htm",
    genres: [
      { key: "", label: "종합" },
      { key: "タテコミ", label: "타테코미(웹툰)" },
    ],
  },
  {
    id: "booklive",
    name: "북라이브",
    color: "#2196F3",
    logo: "/booklive.png",
    sourceUrl: "https://booklive.jp/ranking/day",
    genres: [
      { key: "", label: "종합" },
      { key: "少年マンガ", label: "소년만화" },
      { key: "青年マンガ", label: "청년만화" },
      { key: "少女マンガ", label: "소녀만화" },
      { key: "女性マンガ", label: "여성만화" },
      { key: "BL", label: "BL" },
      { key: "TL", label: "TL" },
      { key: "ラノベ", label: "라노벨" },
    ],
  },
  {
    id: "ebookjapan",
    name: "이북재팬",
    color: "#FF5722",
    logo: "/ebookjapan.png",
    sourceUrl: "https://ebookjapan.yahoo.co.jp/ranking/",
    genres: [
      { key: "", label: "종합" },
      { key: "少女・女性", label: "소녀/여성" },
      { key: "少年・青年", label: "소년/청년" },
      { key: "ファンタジー", label: "판타지" },
      { key: "BL", label: "BL" },
      { key: "TL", label: "TL" },
    ],
  },
  {
    id: "lezhin",
    name: "레진코믹스",
    color: "#9C27B0",
    logo: "/lezhin.png",
    sourceUrl: "https://lezhin.jp/ranking",
    genres: [
      { key: "", label: "종합" },
      { key: "少年マンガ", label: "소년만화" },
      { key: "青年マンガ", label: "청년만화" },
      { key: "少女マンガ", label: "소녀만화" },
      { key: "女性マンガ", label: "여성만화" },
      { key: "BL", label: "BL" },
      { key: "TL", label: "TL" },
    ],
  },
  {
    id: "beltoon",
    name: "벨툰",
    color: "#673AB7",
    logo: "/beltoon.png",
    sourceUrl: "https://www.beltoon.jp/app/all/ranking",
    genres: [
      { key: "", label: "종합" },
      { key: "ロマンス", label: "로만스" },
    ],
  },
  {
    id: "unext",
    name: "U-NEXT",
    color: "#00BCD4",
    logo: "/unext.png",
    sourceUrl: "https://video.unext.jp/book/ranking/comic",
    genres: [
      { key: "", label: "종합" },
    ],
  },
  {
    id: "asura",
    name: "Asura Scans",
    color: "#9333EA",
    logo: "/asura.png",
    sourceUrl: "https://asuracomic.net",
    genres: [
      { key: "all", label: "All-time" },
      { key: "weekly", label: "Weekly" },
      { key: "monthly", label: "Monthly" },
    ],
  },
];

export function getPlatformById(id: string): PlatformInfo | undefined {
  return PLATFORMS.find((p) => p.id === id);
}

/** 영어 전용 플랫폼 ID 목록 */
export const ENGLISH_PLATFORMS = new Set(["asura"]);

/** 일본어 플랫폼인지 여부 (asura 제외 나머지 전부) */
export function isJapanesePlatform(platformId: string): boolean {
  return !ENGLISH_PLATFORMS.has(platformId);
}

/** 플랫폼 정렬: 일본 플랫폼 우선 → 영어 플랫폼 뒤로 */
export function sortPlatformsJPFirst<T extends { platform: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aJP = isJapanesePlatform(a.platform) ? 0 : 1;
    const bJP = isJapanesePlatform(b.platform) ? 0 : 1;
    if (aJP !== bJP) return aJP - bJP;
    return a.platform.localeCompare(b.platform);
  });
}
