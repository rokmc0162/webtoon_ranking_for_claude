import type { PlatformInfo } from "./types";

export const PLATFORMS: PlatformInfo[] = [
  {
    id: "piccoma",
    name: "픽코마",
    color: "#F5C518",
    logo: "/piccoma.webp",
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
    ],
  },
];

export function getPlatformById(id: string): PlatformInfo | undefined {
  return PLATFORMS.find((p) => p.id === id);
}
